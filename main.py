import asyncio

from consumer import Consumer
from session_manager import SessionManager


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    session_manager = SessionManager(loop)

    consumer = Consumer(session_manager)

    loop.run_until_complete(consumer.consume())

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(session_manager.close())
