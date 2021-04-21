import logging

import zmq


logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)
session_file = 'server_session.json'


class Server:

    def __init__(self, name, port, ip):
        self.name = name
        self.addr = (ip, port)
        self.socket = zmq.Context().socket(zmq.ROUTER)
        self.clients = []

    def start(self):
        self.socket.bind(f'tcp://*:{self.addr[1]}')
        logging.info(f'[{self.name}] binded to {self.addr}')

        while True:
            client_id = self.socket.recv()

            print('-' * 30)

            data = {k: v for k, v in self.socket.recv_json().items()}
            logging.info(f'Data received from [{client_id}] {data}')

            is_auth = data.get('auth', None)
            joined = None
            if is_auth == 1 or (is_auth is None and client_id not in self.clients):
                self.clients.append(client_id)
                joined = True
                self.socket.send(client_id, zmq.SNDMORE)
                self.socket.send_json(
                    {
                        'name': self.name,
                        'text': f'You are now online. {len(self.clients)} online.\n'
                    }
                )
            elif is_auth == 0:
                try:
                    self.clients.remove(client_id)
                    joined = False
                except ValueError:
                    logging.warning('Disconnected client of previous session.')
                    pass

            if joined is not None:
                msg = f'{data["name"]} {"joined" if joined else "left"} the room. ' \
                    f'{len(self.clients)} online.'

                join_data = {
                    'name': self.name,
                    'text': msg + '\n'
                }
                for client in self.clients:
                    if client != client_id:
                        self.socket.send(client, zmq.SNDMORE)
                        self.socket.send_json(join_data)

                logging.info(msg)

            if is_auth is None:
                count = 0
                for client in self.clients:
                    if client != client_id:
                        self.socket.send(client, zmq.SNDMORE)
                        self.socket.send_json(data)
                        count += 1

                logging.info(f'Delivered data from [{client_id}] to {count} clients.')

    def disconnect(self):
        for client in self.clients:
            self.socket.send(client, zmq.SNDMORE)
            self.socket.send_json({
                "name": self.name,
                "text": 'Server is off.\n'
            })
        self.socket.close(linger=1)


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('--port', type=int, help='Server port')
    parser.add_argument('--ip', default='*', help='Server IP. Use \'all\' for *')
    parser.add_argument('--name', type=str, default='server', help='Server name')

    args = parser.parse_args()
    args.ip = '*' if args.ip == 'all' else args.ip

    server = Server(
        name=args.name,
        port=args.port,
        ip=args.ip
    )

    try:
        server.start()
    except KeyboardInterrupt:
        server.disconnect()
        logging.info('Server stopped by user!')
