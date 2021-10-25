import asyncio

from consumer import Consumer
from session_manager import SessionManager
from ws_server import WebSocketServer


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    session_manager = SessionManager(loop)

    ws_server = WebSocketServer(session_manager)

    consumer = Consumer(ws_server, session_manager)

    loop.run_until_complete(ws_server.serve())
    loop.run_until_complete(consumer.consume())

    loop.run_forever()
