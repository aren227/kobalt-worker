import json


class WebSocketClient:

    def __init__(self, session, websocket):
        self.session = session
        self.websocket = websocket

    async def send_stdout(self, msg):
        await self.websocket.send(
            json.dumps({
                'type': 'stdout',
                'out': msg
            })
        )

    async def send_terminated(self, code):
        await self.websocket.send(
            json.dumps({
                'type': 'terminated',
                'code': code
            })
        )

    async def send_timeout(self):
        await self.websocket.send(
            json.dumps({
                'type': 'timeout'
            })
        )

    async def close(self):
        await self.websocket.close()

    async def listen_loop(self):
        # Force break when socket is closed by session but still receiving
        # websockets.exceptions.ConnectionClosedOK
        try:
            while not self.websocket.closed:
                packet = json.loads(await self.websocket.recv())
                if packet['type'] == 'stdin':
                    self.session.write_to_stdin(packet['in'])
        except:
            pass
