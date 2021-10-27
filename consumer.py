import traceback

import aio_pika
import json
import socket

from exception import CompileError, LanguageNotFoundError, InvalidRequestError
from language import Language


class Consumer:

    def __init__(self, session_manager):
        self.session_manager = session_manager

        self.channel = None

        self.queue = None

    async def consume(self):
        connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")

        self.channel = await connection.channel()

        await self.consume_compile_queue(self.channel)

        await self.consume_exclusive_queue(self.channel)

    async def consume_compile_queue(self, channel):
        queue = await channel.declare_queue('compile')

        await channel.set_qos(prefetch_count=1)

        async def process_message(message: aio_pika.IncomingMessage):
            # Ack first
            await message.ack()

            request = json.loads(str(message.body, encoding='utf8'))

            print(request)

            await self.session_manager.compile_and_run(self, message.reply_to, message.correlation_id, request)

        await queue.consume(process_message)

    async def consume_exclusive_queue(self, channel):
        queue = await channel.declare_queue(None, exclusive=True)

        self.queue = queue.name

        print('Queue {} created.'.format(self.queue))

        async def process_message(message: aio_pika.IncomingMessage):
            request = json.loads(str(message.body, encoding='utf8'))

            session = self.session_manager.get(message.correlation_id)

            if session is not None:
                await session.handle_message(request)\

        await queue.consume(process_message, no_ack=True)

    async def send(self, session, message):
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=bytes(json.dumps(message), encoding='utf8'),
                correlation_id=session.target_id
            ),
            routing_key=session.target_queue,
        )
