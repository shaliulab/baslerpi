import socket
import threading
import queue
import logging
import time
import selectors
import types

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class TCPClient(threading.Thread):

    _num_conns = 3
    _CHUNK_SIZE = 1024*10
    #_num_conns = 1

    def __init__(self, ip, port, *args, parallel = True, **kwargs):
        self._ip = ip
        self._port = port
        self._parallel = parallel
        self._encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._count = 0

        super().__init__(*args, **kwargs)


    def queue(self, frame):
        logger.debug("Queuing frame in TCP client")
        self._queue.put(frame)

    def encode(self, frame):
        result, imgencode = cv2.imencode('.jpg', frame, self._encode_param)
        data = np.array(imgencode)
        stringData = data.tostring()
        return stringData

    def stream(self, frame):

        stringData = self.encode(frame)
        header = str(len(stringData)).ljust(16)
        logger.debug("Sending frame to TCP server")
        try:
            sock = socket.create_connection((self._ip, self._port))
        except ConnectionRefusedError as error:
            logger.warning("Connection refused")
            return None

        sock.send(header.encode("utf-8"));
        sock.send(stringData);
        sock.close()
        return 0

    @property
    def messages(self):
        return self._messages

    @messages.setter
    def messages(self, message):
        self._messages.append(message)

    def start_connections(self, host, port, messages, num_conns=1):
        server_addr = (host, port)
        for i in range(0, num_conns):
            connid = i + 1
            logger.debug("connection (%s) OPEN", connid)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            sock.connect_ex(server_addr)
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
            print(len(messages[0]))
            data = types.SimpleNamespace(
                    connid=connid,
                    #msg_total=sum(len(m) for m in messages),
                    msg_total=len(messages[i]),
                    recv_total = 0,
                    messages=messages,
                    outb=b'')

            self._selector.register(sock, events, data=data)

    def service_connection(self, key, mask):
        
        sock = key.fileobj
        data = key.data
        #print("--")
        #print(mask & selectors.EVENT_READ)
        #print(mask)
        #print(selectors.EVENT_READ)
        #print("--")

        if mask & selectors.EVENT_READ:
            try:
                recv_data = sock.recv(self._CHUNK_SIZE)
            except Exception as error:
                logger.warning(error)
                logger.warning("Could not receive confirmation from server")
                return 1

            if recv_data:
                data.recv_total += len(recv_data)
                logger.debug("Serving read connection to %s", sock.getpeername()[1])
                logger.debug("Length of received data %s", len(recv_data))
                logger.debug("Length of missing data %s", data.msg_total - data.recv_total)

            if not recv_data or data.recv_total == data.msg_total:
                logger.debug("connection (%s) CLOSE", data.connid)
                #if not recv_data:
                #    print("No more data is received")
                #if data.recv_total == data.msg_total:
                #    print("Received amount of data is the expected")

                self._selector.unregister(sock)
                sock.close()

            #else:
            #    if recv_data:
            #        print("I am still receiving data")
            #        print(recv_data)
            #    if data.recv_total != data.msg_total:
            #        print("I still have not received everything back")
            #        print(data.recv_total)
            #        print(data.msg_total)

        if mask & selectors.EVENT_WRITE:
        
            #print("Messages left")
            #print(len(data.messages))
            #print(sock._closed)
            if not data.outb and data.messages:
                data.outb = data.messages.pop(0)

            if len(data.outb) != 0:
                logger.debug("Sending to connection %d", data.connid)
                try:
                    sent = sock.send(data.outb)
                except Exception:
                    # TODO Exit at some point, dont keep trying
                    print("Server is closed")
                    sock.close()
                    return 1
                logger.debug("Length of sent data %s", sent)
                data.outb = data.outb[sent:]
                logger.debug("Length of remaining data %s", len(data.outb))

                if len(data.outb) == 0:
                    self._count += 1


    def get_messages(self):
        messages = [self._queue.get(timeout=2) for i in range(self._num_conns)]
        for i, msg in enumerate(messages):
            messages[i] = self.encode(msg)
        return messages


    def _run_multi_threaded(self):

        self._selector = selectors.DefaultSelector()
        #self._messages = [bytes(f"Hello World {i}", "utf-8") for i in range(self._num_conns)]
        messages = self.get_messages()
        self.start_connections(self._ip, self._port, messages, self._num_conns)
        loop = 0

        try:
            while not self._stop.is_set():
                loop += 1
                #if loop == 9999:
                #    break
                events = self._selector.select(timeout=1)
                if events:
                    for key, mask in events:
                        self.service_connection(key, mask)
                else:
                    print("Negative events")
                    print(events)

                selector_map = self._selector.get_map()
                if not selector_map:
                    #print("Selector map is negative")
                    #print(selector_map)
                    ##break
                    print("I am fetching more messages")
                    messages = self.get_messages()
                    self.start_connections(self._ip, self._port, messages, self._num_conns)
                else:
                    pass
                    #print("Selector map is positive")
                    #print(selector_map)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()
            self._selector.close()


    def _run_single_threaded(self):

        while not self._stop.is_set():
            frame = self._queue.get()
            data = self.stream(frame)


    def run(self):
        if self._parallel:
            self._run_multi_threaded()
        else:
            self._run_single_threaded()


    def stop(self):
        logger.debug("Stopping TCP client")
        self._stop.set()

if __name__ == "__main__":
    frame = np.random.randint(255, size=(900,800,3),dtype=np.uint8)
    TCP_IP = '10.43.207.46'
    TCP_PORT = 8082

    client = TCPClient(TCP_IP, TCP_PORT)
    client.queue(frame)
    client.start()
    client.stop()


