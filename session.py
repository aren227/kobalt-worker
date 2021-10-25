import asyncio
import io
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

        self.language = compile_request.language
        self.code = compile_request.code

        self.process = None

        self.dir = os.getcwd() + '/kobalt-worker/{}'.format(self.id)
        self.code_file_name = 'code' + self.language.file_ext

        self.stdout_buffer = None

        self.execution_timestamp = 0
        self.max_execution_time = 60

        self.loop_delay = 0.2

        self.attached_websocket = None

        os.makedirs(self.dir, exist_ok=True)

        print('Session {} created.'.format(self.id))

    def compile(self):
        f = open('{}/{}'.format(self.dir, self.code_file_name), 'w')
        f.write(self.code)
        f.close()

        self.process = subprocess.Popen(
            self.language.get_compile_cmd(self.code_file_name),
            cwd=self.dir
        )
        return_code = self.process.wait()

        if return_code != 0:
            raise CompileError()

    def execute(self):
        self.process = subprocess.Popen(
            self.language.get_execute_cmd(),
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            cwd=self.dir,
            shell=True
        )

        os.set_blocking(self.process.stdout.fileno(), False)

        self.stdout_buffer = io.BufferedReader(self.process.stdout)

        self.execution_timestamp = time()

    def write_to_stdin(self, message):
        try:
            self.process.stdin.write(bytes(message, encoding='utf8'))
            self.process.stdin.flush()
        except:
            pass

    def read_from_stdout(self):
        return self.stdout_buffer.read1()

    async def main_loop(self):
        try:
            while not self.attached_websocket.closed:
                if self.process.poll() is not None:
                    out = str(self.read_from_stdout(), encoding='utf8')
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

                if time() > self.execution_timestamp + self.max_execution_time:
                    msg = {
                        'type': 'timeout'
                    }
                    await self.attached_websocket.send(json.dumps(msg))
                    break

                out = str(self.read_from_stdout(), encoding='utf8')
                if len(out) > 0:
                    await self.attached_websocket.send(
                        json.dumps({
                            'type': 'stdout',
                            'out': out
                        })
                    )

                await asyncio.sleep(self.loop_delay)
        except:
            pass

        await self.close()

    async def listen_loop(self, websocket):
        try:
            while not self.attached_websocket.closed and \
                    self.process is not None and self.process.poll() is None:
                packet = json.loads(await websocket.recv())
                if packet['type'] == 'stdin':
                    self.write_to_stdin(packet['in'])
        except:
            pass

    async def attach_websocket(self, websocket):
        if self.attached_websocket is not None:
            raise Exception('Invalid request')

        self.attached_websocket = websocket

        self.execute()

        self.loop.create_task(self.listen_loop(websocket))

        await self.main_loop()

    async def close(self):
        if self.attached_websocket is not None:
            await self.attached_websocket.close()

        if self.process is not None:
            self.process.kill()

        if self.stdout_buffer is not None:
            self.stdout_buffer.close()

        shutil.rmtree(self.dir)

        print('Session {} closed.'.format(self.id))
