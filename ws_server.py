import websockets
import socket


class WebSocketServer:

    def __init__(self):
        self.port = 0
        self.server = None
        pass

    async def serve(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))

        self.port = sock.getsockname()[1]

        print('WebSocket port:', self.port)

        async def accept(websocket, path):
            if path != '/':
                websocket.close()

            while True:
                data = await websocket.recv()
                print(data)

        self.server = await websockets.serve(accept, sock=sock)
