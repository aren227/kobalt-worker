from session import Session


class SessionManager:

    def __init__(self, loop):
        self.loop = loop

        self._sessions = {}

    def create(self, compile_request):
        session = Session(compile_request, self.loop)

        self._sessions[str(session.id)] = session

        return session

    def get(self, session_id):
        return self._sessions.get(str(session_id))

    def close(self):
        for session in self._sessions.values():
            session.close()
