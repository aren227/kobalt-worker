import asyncio

from exception import CompileError
from session import Session
from ws_server import WebSocketServer


class SessionManager:

    def __init__(self, loop):
        self.loop = loop
        self.semaphore = asyncio.Semaphore(10)  # Max session count
        self._sessions = {}

    async def compile_and_run(self, compile_request, compile_response_callback):
        async with self.semaphore:
            session = Session(compile_request, self.loop)

            self._sessions[str(session.id)] = session

            try:
                await session.compile()
            except CompileError:
                await compile_response_callback({'result': 'compile_error'})
                return
            except:
                await compile_response_callback({'result': 'internal_error'})
                return

            await compile_response_callback({
                'result': 'success',
                'address': WebSocketServer.get_address(),
                'session_id': str(session.id),
            })

            await session.run()

            self._sessions.pop(str(session.id))

    def get(self, session_id):
        return self._sessions.get(str(session_id))

    def close(self):
        for session in self._sessions.values():
            session.close()
