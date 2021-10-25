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

        self.max_execution_time = 60

        self.loop_delay = 0.2

        self.attached_websocket = None

        self.close_signal = False

        os.makedirs(self.dir, exist_ok=True)

        print('Session {} created.'.format(self.id))

    async def compile(self):
        f = open('{}/{}'.format(self.dir, self.code_file_name), 'w')
        f.write(self.code)
        f.close()

        compile_process = subprocess.Popen(
            self.language.get_compile_cmd(self.code_file_name),
            cwd=self.dir
        )
        return_code = compile_process.wait()

        if return_code != 0:
            await self.close()

            raise CompileError()

        self.state = SessionState.READY

    async def run(self):
        try:
            await self._main_loop()
        except Exception as e:
            print(e)
            pass
        await self.close()

    def _execute(self):
        if self.state != SessionState.READY:
            return

        self.state = SessionState.RUNNING

        self.process = subprocess.Popen(
            self.language.get_execute_cmd(),
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            cwd=self.dir,
            shell=True
        )

        os.set_blocking(self.process.stdout.fileno(), False)

        self.stdout_buffer = io.BufferedReader(self.process.stdout)

    def _write_to_stdin(self, message):
        self.process.stdin.write(bytes(message, encoding='utf8'))
        self.process.stdin.flush()

    def _read_from_stdout(self):
        return self.stdout_buffer.read1()

    async def _main_loop(self):
        start_timestamp = time()

        while not self.close_signal:
            # TODO: Temporary
            if self.process is not None and self.process.poll() is not None:
                out = str(self._read_from_stdout(), encoding='utf8')
                if self.attached_websocket is not None:
                    if len(out) > 0:
                        await self.attached_websocket.send(
                            json.dumps({
                                'type': 'stdout',
                                'out': out
                            })
                        )

                    msg = {
                        'type': 'terminated',
                        'code': self.process.poll()
                    }
                    await self.attached_websocket.send(json.dumps(msg))
                break

            if time() > start_timestamp + self.max_execution_time:
                if self.attached_websocket is not None:
                    msg = {
                        'type': 'timeout'
                    }
                    await self.attached_websocket.send(json.dumps(msg))
                break

            if self.process is not None and self.attached_websocket is not None:
                out = str(self._read_from_stdout(), encoding='utf8')

                if len(out) > 0:
                    await self.attached_websocket.send(
                        json.dumps({
                            'type': 'stdout',
                            'out': out
                        })
                    )

            await asyncio.sleep(self.loop_delay)

    async def _listen_loop(self):
        # Force break when session is closed but still receiving
        # websockets.exceptions.ConnectionClosedOK
        try:
            while not self.attached_websocket.closed:
                packet = json.loads(await self.attached_websocket.recv())
                if packet['type'] == 'stdin':
                    self._write_to_stdin(packet['in'])
        except:
            pass

        self.close_signal = True

    async def attach_websocket(self, websocket):
        if self.attached_websocket is not None:
            raise Exception('Invalid request')

        self._execute()

        self.attached_websocket = websocket

        await self._listen_loop()

    async def close(self):
        if self.state == SessionState.TERMINATED:
            return

        self.state = SessionState.TERMINATED

        if self.attached_websocket is not None:
            await self.attached_websocket.close()

        if self.process is not None:
            self.process.kill()

        if self.stdout_buffer is not None:
            self.stdout_buffer.close()

        shutil.rmtree(self.dir)

        print('Session {} closed.'.format(self.id))


class SessionState(Enum):
    COMPILE = 1
    READY = 2
    RUNNING = 3
    TERMINATED = 4
