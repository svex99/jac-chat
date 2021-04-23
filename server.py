import logging
import threading

import zmq


logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)
session_file = 'server_session.json'


class Server:

    def __init__(self, name, interface, port, num_workers):
        self.name = name
        self.interface = interface
        self.port = port

        self.num_workers = num_workers
        self.stop_workers = threading.Event()   # pill for kill worker's thread
        self.workers_pool = []

        self.context = zmq.Context()
        self.clients_socket = self.context.socket(zmq.ROUTER)
        self.workers_socket = self.context.socket(zmq.DEALER)

        self.clients_lock = threading.Lock()   # lock for sync changes in the list of clients
        self.clients = []

    def worker(self):
        """
        Worker that processes pending requests in queue.
        1. Gets the request from the queue.
        2. Sends the request to all clients (except the original sender).
        """
        thread_name = threading.current_thread().name
        socket = self.context.socket(zmq.DEALER)
        socket.connect('inproc://workers')

        # handle requests while main thread keeps running
        while not self.stop_workers.is_set():
            try:
                event = socket.poll(timeout=1000)
            except zmq.error.ContextTerminated:
                break
            else:
                if event == 0:
                    continue

            client_id = socket.recv()

            data = {k: v for k, v in socket.recv_json().items()}
            logging.info(f'[{thread_name}] data received from [{client_id}] : {data}')

            is_auth = data.get('auth', None)
            joined = None

            self.clients_lock.acquire()

            if is_auth == 1 or (is_auth is None and client_id not in self.clients):
                self.clients.append(client_id)
                joined = True
                socket.send(client_id, zmq.SNDMORE)
                socket.send_json(
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
                    logging.warning(f'[{thread_name}] disconnected client of previous session.')
                    pass

            self.clients_lock.release()

            if joined is not None:
                msg = f'{data["name"]} {"joined" if joined else "left"} the room. ' \
                    f'{len(self.clients)} online.'

                join_data = {
                    'name': self.name,
                    'text': msg + '\n'
                }
                for client in self.clients:
                    if client != client_id:
                        socket.send(client, zmq.SNDMORE)
                        socket.send_json(join_data)

                logging.info(msg)

            if is_auth is None:
                count = 0
                for client in self.clients:
                    if client != client_id:
                        socket.send(client, zmq.SNDMORE)
                        socket.send_json(data)
                        count += 1

                logging.info(f'[{thread_name}] delivered data from [{client_id}] to {count} clients.')

        socket.close(linger=1)
        logging.info(f'Stopped {thread_name}')

    def start(self):
        clients_conn = f'tcp://{self.interface}:{self.port}'
        self.clients_socket.bind(clients_conn)
        logging.info(f'[{self.name}] binded to {clients_conn}')

        workers_conn = 'inproc://workers'
        self.workers_socket.bind(workers_conn)

        # launch pool of working threads
        for i in range(self.num_workers):
            thread = threading.Thread(target=self.worker, name=f'worker{i}')
            self.workers_pool.append(thread)
            thread.start()
            logging.info(f'Started worker{i}')

        zmq.device(zmq.QUEUE, self.clients_socket, self.workers_socket)

    def disconnect(self):
        # notify clients that server is going off
        for client in self.clients:
            self.clients_socket.send(client, zmq.SNDMORE)
            self.clients_socket.send_json({
                "name": self.name,
                "text": 'Server is off.\n'
            })

        # close clients socket
        self.clients_socket.close(linger=1)
        logging.info('Closed clients socket')

        # close workers socket
        self.workers_socket.close(linger=1)
        logging.info('Closed workers socket')

        # stop workers
        logging.info('Stopping workers...')
        self.stop_workers.set()

        # end context
        self.context.term()

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('--name', type=str, default='server', help='Server name')
    parser.add_argument('--inter', default='*', help='Server interface to bind. Use \'all\' for *')
    parser.add_argument('--port', type=int, help='Server port')
    parser.add_argument('--numw', type=int, default=3, help='Number of worker threads')

    args = parser.parse_args()
    args.inter = '*' if args.inter == 'all' else args.inter

    server = Server(
        name=args.name,
        interface=args.inter,
        port=args.port,
        num_workers=args.numw
    )

    try:
        server.start()
    except KeyboardInterrupt:
        server.disconnect()
