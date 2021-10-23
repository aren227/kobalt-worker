import asyncio

from consumer import Consumer
from ws_server import WebSocketServer


if __name__ == '__main__':
    ws_server = WebSocketServer()
    consumer = Consumer()

    loop = asyncio.get_event_loop()

    loop.run_until_complete(ws_server.serve())
    loop.run_until_complete(consumer.consume())

    loop.run_forever()
