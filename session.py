import asyncio
import io
from enum import Enum
from time import time
from uuid import uuid4
import os
import subprocess
import shutil
import json
import platform
import resource

from close_reason import ClosedByProgramTermination, ClosedBySessionTimeout, ClosedByWebSocketConnectionTimeout
from ws_client import WebSocketClient

if 'win' in platform.system().lower():
    import msvcrt

    from ctypes import windll, byref, wintypes, WinError
    from ctypes.wintypes import HANDLE, BOOL, LPDWORD

    PIPE_NOWAIT = wintypes.DWORD(0x00000001)

from exception import CompileError


class Session:

    def __init__(self, compile_request, loop):
        self.id = uuid4()
        self.loop = loop

        self.state = SessionState.COMPILE

        self.language = compile_request.language
        self.code = compile_request.code

        self.process = None

        self.dir = os.getcwd() + '/kobalt-worker/{}'.format(self.id)
        self.code_file_name = 'code' + self.language.file_ext

        self.stdout_buffer = None

        self.max_connection_accept_time = 5
        self.max_execution_time = 60
        self.max_memory = 64 * 1024 * 1024

        self.loop_delay = 0.2

        self.ws_client = None

        self.close_signal = False

        os.makedirs(self.dir, exist_ok=True)

        print('Session {} created.'.format(self.id))

    async def compile(self):
        f = open('{}/{}'.format(self.dir, self.code_file_name), 'w')
        f.write(self.code)
        f.close()

        compile_process = subprocess.Popen(
            self.language.get_compile_cmd(self.code_file_name),
            stderr=subprocess.PIPE,
            cwd=self.dir
        )

        os.set_blocking(compile_process.stderr.fileno(), False)

        stderr_buffer = io.BufferedReader(compile_process.stderr)

        return_code = compile_process.wait()

        if return_code != 0:
            await self.close(None)

            raise CompileError(str(stderr_buffer.read1(), encoding='utf8'))

        self.state = SessionState.READY

    async def run(self):
        close_reason = None
        try:
            close_reason = await self._main_loop()
        except Exception as e:
            print(e)
            pass
        await self.close(close_reason)

    def _execute(self):
        if self.state != SessionState.READY:
            return

        self.state = SessionState.RUNNING

        def limit_virtual_memory():
            # The tuple below is of the form (soft limit, hard limit). Limit only
            # the soft part so that the limit can be increased later (setting also
            # the hard limit would prevent that).
            resource.setrlimit(resource.RLIMIT_AS, (self.max_memory, self.max_memory))

        self.process = subprocess.Popen(
            self.language.get_execute_cmd(),
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            cwd=self.dir,
            shell=True,
            preexec_fn=limit_virtual_memory,
        )

        os.set_blocking(self.process.stdout.fileno(), False)

        self.stdout_buffer = io.BufferedReader(self.process.stdout)

    def write_to_stdin(self, message):
        self.process.stdin.write(bytes(message, encoding='utf8'))
        self.process.stdin.flush()

    def _read_from_stdout(self):
        return self.stdout_buffer.read1()

    async def send_stdout(self):
        if self.process is None:
            return

        out = str(self._read_from_stdout(), encoding='utf8')
        if len(out) == 0:
            return

        await self.ws_client.send_stdout(out)

    async def _main_loop(self):
        start_timestamp = time()

        while not self.close_signal and self.state in [SessionState.READY, SessionState.RUNNING]:
            if self.process is not None and self.process.poll() is not None:
                return ClosedByProgramTermination(self.process.poll())

            if self.state == SessionState.READY and time() > start_timestamp + self.max_connection_accept_time:
                return ClosedByWebSocketConnectionTimeout()

            if time() > start_timestamp + self.max_execution_time:
                return ClosedBySessionTimeout()

            await self.send_stdout()

            await asyncio.sleep(self.loop_delay)

        return None

    async def attach_websocket(self, websocket):
        if self.ws_client is not None:
            return

        self.ws_client = WebSocketClient(self, websocket)

        self._execute()

        await self.ws_client.listen_loop()

        self.close_signal = True

    async def close(self, reason):
        if self.state == SessionState.TERMINATED:
            return

        self.state = SessionState.TERMINATED

        if self.ws_client is not None:
            # Send remained buffer
            await self.send_stdout()

            if reason is not None:
                await self.ws_client.send(reason.get_message())

            await self.ws_client.close()

        if self.process is not None:
            self.process.kill()

        if self.stdout_buffer is not None:
            self.stdout_buffer.close()

        shutil.rmtree(self.dir)

        print('Session {} closed (reason: {}).'.format(self.id, reason.__class__.__name__))


class SessionState(Enum):
    COMPILE = 1
    READY = 2
    RUNNING = 3
    TERMINATED = 4
