FROM python:3.8

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install websockets aio_pika

EXPOSE 5050

CMD ["python", "main.py"]