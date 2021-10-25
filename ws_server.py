import websockets
import socket


class WebSocketServer:

    def __init__(self, session_manager):
        self.session_manager = session_manager

        self.host = 'localhost'
        self.port = 5050
        self.server = None

    async def serve(self):
        async def accept(websocket, path):
            if websocket.request_headers is None or not path.startswith('/') or len(path) <= 1:
                websocket.close()
                return

            session_id = path[1:]
            session = self.session_manager.get(session_id)

            if session is None:
                await websocket.close()
                return

            await session.attach_websocket(websocket)

        self.server = await websockets.serve(accept, "0.0.0.0", self.port)

    def get_address(self):
        return 'ws://{}:{}/'.format(self.host, self.port)
