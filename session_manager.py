import asyncio

from close_reason import ClosedBySessionTimeout
from exception import CompileError
from session import Session


class SessionManager:

    def __init__(self, loop):
        self.loop = loop
        self.semaphore = asyncio.Semaphore(10)  # Max session count
        self._sessions = {}

    async def compile_and_run(self, consumer, target_queue, target_id, compile_request):
        session = Session(consumer, target_queue, target_id, self.loop)
        self._sessions[session.target_id] = session

        if session is None:
            return

        async with self.semaphore:
            await session.compile_and_run(compile_request)

        self._sessions.pop(session.target_id)

    def get(self, target_id):
        return self._sessions.get(target_id)

    async def close(self):
        for session in self._sessions.values():
            await session.close(ClosedBySessionTimeout())
