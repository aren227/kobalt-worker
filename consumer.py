import traceback

import aio_pika
import json
import socket

from compile_request import CompileRequest
from exception import CompileError, LanguageNotFoundError, InvalidRequestError
from language import Language


class Consumer:

    def __init__(self, ws_server, session_manager):
        self.ws_server = ws_server
        self.session_manager = session_manager

        self.host = socket.gethostbyname_ex(socket.gethostname())[-1][-1]

    async def consume(self):
        connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")

        channel = await connection.channel()

        queue = await channel.declare_queue('compile')

        await channel.set_qos(prefetch_count=1)

        async def process_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    request = json.loads(str(message.body, encoding='utf8'))

                    print(request)

                    if not isinstance(request['language'], str) or not isinstance(request['code'], str):
                        raise InvalidRequestError()

                    language = Language.get(request['language'])

                    if language is None:
                        raise LanguageNotFoundError()

                    compile_request = CompileRequest(language, request['code'])

                    session = self.session_manager.create(compile_request)

                    session.compile()

                    response = {
                        'result': 'success',
                        'address': self.ws_server.get_address(),
                        'session_id': str(session.id),
                    }

                except CompileError:
                    response = {'result': 'compile_error'}
                    await session.close()
                except:
                    response = {'result': 'invalid_request'}

                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=bytes(json.dumps(response), encoding='utf8'),
                        correlation_id=message.correlation_id
                    ),
                    routing_key=message.reply_to,
                )

        await queue.consume(process_message)
