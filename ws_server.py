import websockets
import socket


class WebSocketServer:
    host = 'localhost'
    port = 5050

    def __init__(self, session_manager):
        self.session_manager = session_manager

        self.server = None

    async def serve(self):
        async def accept(websocket, path):
            if websocket.request_headers is None or not path.startswith('/') or len(path) <= 1:
                await websocket.close()
                return

            session_id = path[1:]
            session = self.session_manager.get(session_id)

            if session is None:
                await websocket.close()
                return

            await session.attach_websocket(websocket)

        self.server = await websockets.serve(accept, "0.0.0.0", self.port)

    @staticmethod
    def get_address():
        return 'ws://{}:{}/'.format(WebSocketServer.host, WebSocketServer.port)
