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
import pyseccomp

from close_reason import ClosedByProgramTermination, ClosedBySessionTimeout, \
    ClosedByCompileError, ClosedByClientDisconnect, ClosedByInvalidRequest
from language import Language

if 'win' in platform.system().lower():
    import msvcrt

    from ctypes import windll, byref, wintypes, WinError
    from ctypes.wintypes import HANDLE, BOOL, LPDWORD

    PIPE_NOWAIT = wintypes.DWORD(0x00000001)

from exception import CompileError


class Session:

    def __init__(self, consumer, target_queue, target_id, loop):
        self.consumer = consumer

        self.target_queue = target_queue
        self.target_id = target_id

        self.loop = loop

        self.state = SessionState.COMPILE

        self.language = None
        self.code = None

        self.process = None

        self.dir = os.getcwd() + '/kobalt-worker/{}'.format(self.target_id)
        self.code_file_name = None

        self.stdout_buffer = None

        self.max_execution_time = 60
        self.max_memory = 64 * 1024 * 1024

        self.loop_delay = 0.2

        os.makedirs(self.dir, exist_ok=True)

        print('Session {} created.'.format(self.target_id))

    async def compile_and_run(self, compile_request):
        if compile_request.get('language') is None or compile_request.get('code') is None \
                or Language.get(str(compile_request.get('language'))) is None:
            await self.close(ClosedByInvalidRequest())
            return

        self.language = Language.get(str(compile_request.get('language')))
        self.code = str(compile_request.get('code'))

        self.code_file_name = 'code' + self.language.file_ext

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
            compiler_out = str(stderr_buffer.read1(), encoding='utf8')

            await self.close(ClosedByCompileError(compiler_out))

            return

        await self.send_message({'type': 'compile_success', 'queue': self.consumer.queue})

        await self._run()

    async def send_message(self, message):
        await self.consumer.send(self, message)

    async def handle_message(self, message):
        try:
            if message['type'] == 'stdin':
                self.write_to_stdin(message['in'])
            elif message['type'] == 'closed':
                await self.close(ClosedByClientDisconnect())
        except:
            pass

    async def _run(self):
        self.state = SessionState.RUNNING

        def setup():
            # Limit memory
            resource.setrlimit(resource.RLIMIT_AS, (self.max_memory, self.max_memory))

            filt = pyseccomp.SyscallFilter(pyseccomp.KILL)

            whitelist = [
                "exit_group", "uname", "fstat", "read", "lseek", "close", "getdents64", "readlink", "mmap",
                "write", "rt_sigaction", "mprotect", "munmap", "brk", "access", "sysinfo", "arch_prctl", "getrandom",
                "clock_gettime", "clone",
            ]
            for syscall in whitelist:
                filt.add_rule_exactly(pyseccomp.ALLOW, syscall)

            # Only allow read (O_RDONLY = 0)
            filt.add_rule_exactly(pyseccomp.ALLOW, "openat", pyseccomp.Arg(2, pyseccomp.MASKED_EQ, 0b11, 0))

        self.process = subprocess.Popen(
            self.language.get_execute_cmd(),
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            cwd=self.dir, preexec_fn=setup
        )

        os.set_blocking(self.process.stdout.fileno(), False)

        self.stdout_buffer = io.BufferedReader(self.process.stdout)

        close_reason = None
        try:
            close_reason = await self._main_loop()
        except Exception as e:
            print(e)
            pass
        await self.close(close_reason)

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

        await self.send_message({'type': 'stdout', 'out': out})

    async def _main_loop(self):
        start_timestamp = time()

        while self.state == SessionState.RUNNING:
            if self.process is not None and self.process.poll() is not None:
                return ClosedByProgramTermination(self.process.poll())

            if time() > start_timestamp + self.max_execution_time:
                return ClosedBySessionTimeout()

            await self.send_stdout()

            await asyncio.sleep(self.loop_delay)

        return None

    async def close(self, reason):
        if self.state == SessionState.TERMINATED:
            return

        self.state = SessionState.TERMINATED

        await self.send_stdout()

        if reason and reason.get_message():
            await self.send_message(reason.get_message())

        await self.send_message({'type': 'closed'})

        if self.process is not None:
            self.process.kill()

        if self.stdout_buffer is not None:
            self.stdout_buffer.close()

        shutil.rmtree(self.dir)

        print('Session {} closed (reason: {}).'.format(self.target_id, reason.__class__.__name__))


class SessionState(Enum):
    COMPILE = 1
    RUNNING = 2
    TERMINATED = 3
