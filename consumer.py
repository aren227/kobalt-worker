import aio_pika


class Consumer:

    def __init__(self):
        pass

    async def consume(self):
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")

        channel = await connection.channel()

        queue = await channel.declare_queue('compile')

        await channel.set_qos(prefetch_count=1)

        async def process_message(message: aio_pika.IncomingMessage):
            async with message.process():
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=b'{"result": "SUCCESS"}',
                        correlation_id=message.correlation_id
                    ),
                    routing_key=message.reply_to,
                )

        await queue.consume(process_message)
