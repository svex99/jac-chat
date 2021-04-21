import logging
import asyncio
import random

import zmq
import zmq.asyncio

from utils import ainput


logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)


class Client:

    def __init__(self, name, port, ip):
        self.name = name
        self.addr = (ip, port)
        self.socket = zmq.asyncio.Context().socket(zmq.DEALER)

        self.socket.connect(f'tcp://{ip}:{port}')
        logging.info('Connection ready.')

    async def run_sender(self):
        while True:
            text = await ainput('')
            await self.socket.send_json(
                {
                    'name': self.name,
                    'text': text
                }
            )

    async def run_receiver(self):
        self.socket.send_json(
            {
                'auth': 1,
                'name': self.name
            }
        )

        while True:
            data = await self.socket.recv_json()
            print(f' [{data["name"]}] {data["text"]}', end='', flush=True)

    async def disconnect(self):
        await self.socket.send_json(
            {
                'auth': 0,
                'name': self.name
            }
        )

    def start(self, loop):
        loop.create_task(self.run_receiver())
        loop.create_task(self.run_sender())


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('--port', help='Server port')
    parser.add_argument('--ip', default='localhost', help='Server IP')
    parser.add_argument('--name', default='server', help='Client name')
    args = parser.parse_args()

    client = Client(
        name=args.name,
        port=args.port,
        ip=args.ip
    )

    try:
        loop = asyncio.get_event_loop()
        client.start(loop)
        loop.run_forever()
    except KeyboardInterrupt:
        asyncio.run(client.disconnect())
        logging.info('Stopped by user!')
