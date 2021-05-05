#!/usr/bin/python
import socket
import threading
import queue
import time
import sys
import logging
import selectors
import types

import cv2
import numpy as np

logger = logging.getLogger(__name__)

selected_socket = None

class TCPServer(threading.Thread):
    """
    Receive TCP requests in the background
    """

    _TICK_PERIOD = 1000
    _CHUNK_SIZE = 1024*100

    def __init__(self, ip, port, *args, parallel=True, **kwargs):

        self._ip = ip
        self._port = port
        self._parallel = parallel
        self._sock = self.open()
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._count = 0
        self._start_time = time.time()
        self._last_tick = self._start_time
        self._data = {}
        self._until_the_end_data = {}
        self._lengths = {}
        self._complete = {}

        if self._parallel:
            self._selector = selectors.DefaultSelector()
            self._sock.setblocking(False)
            self._selector.register(self._sock, selectors.EVENT_READ, data=None)
 
        super().__init__(*args, **kwargs)

    def open(self):
        """
        Open and register a TCP listening socket
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self._ip, self._port))
        sock.listen(True)
        print("Listening on ", (self._ip, self._port))
        return sock

    @staticmethod
    def recvall(sock, count):
        buf = b''
        while count:
            newbuf = sock.recv(count)
            if not newbuf: return None
            buf += newbuf
            count -= len(newbuf)
        return buf
    
    def accept_wrapper(self, sock):

        conn, addr = sock.accept()
        logger.debug("connection ACCEPT %s", addr)
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self._selector.register(conn, events, data=data)
        return 0

    def close_socket(self, sock):
        sock.close()
        del self._data[sock]
        del self._lengths[sock]
        del self._until_the_end_data[sock]
 
    
    def service_connection(self, key, mask):

        global selected_socket
        sock = key.fileobj
        if selected_socket is None:
            selected_socket = sock
        if selected_socket._closed:
            selected_socket = sock

        #print(self._data.keys())
        #for k in self._data:
        #    print(len(self._data[k]))

        data = key.data
        # the socket is ready to read
        if mask & selectors.EVENT_READ:
            try:
                recv_data = sock.recv(self._CHUNK_SIZE)
                if recv_data:
                    logger.debug("Serving read connection from %s", data.addr)
                    data.outb += recv_data
                    #print(f"Adding to the stored data {len(recv_data)}")
                    if sock in self._data:
                        self._data[sock] += recv_data
                        self._until_the_end_data[sock] += recv_data
                    else:
                        length = recv_data[:16]
                        self._lengths[sock] = length
                        recv_data=recv_data[16:]
                        self._data[sock] = recv_data
                        self._until_the_end_data[sock] = recv_data

                    logger.debug("Length of received data %d", len(data.outb))
                    if sock == selected_socket:
                        pass
                        # print(len(data.outb))
                        # print(len(self._data[sock]))
     
                else:
                    logger.debug("connection CLOSE %s", data.addr)
                    self._selector.unregister(sock)
                    if sock == selected_socket:
                        pass
                        # print(len(data.outb))
                        # print(len(self._data[sock]))

                    #img = self.decode(data.outb)
                    length = self._lengths[sock]
                    encoded_frame = self._until_the_end_data[sock]
                    try:
                        assert int(length.decode("utf-8")) == len(encoded_frame)
                    except AssertionError as error:
                        print(length)
                        print(len(encoded_frame))
                        raise error
                    self._complete[sock] = True

                    img = self.decode(encoded_frame)
                    if img is None:
                        pass
                        #logger.warning("Decoded image is empty")
                        raise Exception("Decoded image is empty")
                    else:
                        self._queue.put(img)

                    if selected_socket == sock:
                        selected_sock = None
                    self.close_socket(sock)

                    self._count += 1
    
            except ConnectionResetError:
                print("Client is closed")
                sock.close()


        if mask & selectors.EVENT_WRITE:
            #if data.outb:

            if sock in self._data:
                #print("Echoing to ", data.addr)
                logger.debug("Serving write connection from %s", data.addr)
                try:
                    #if len(self._data[sock]) != len(self._lengths[sock]) and sock in self._complete:
                    #     pass
                    #else:
                    #     return

                    original_length = len(self._data[sock])
                    sent = sock.send(self._lengths[sock])
                    sent = sock.send(self._data[sock])
                    #print(f"Removing from the stored data {sent}")
                    self._data[sock] = self._data[sock][sent:]
                    #data.outb = data.outb[sent:]
                    logger.debug("Length of sent data %s", sent)
                    #print(sent)
                    if len(self._data[sock]) == 0 and sent == original_length:
                        logger.debug("Success in echoing")

                    if len(self._data[sock]) == 0 and sent != 0:
                        pass


                except Exception as error:
                    logger.warning(error)
                    logger.warning("Could not echo data back to client")
                    raise error
                    

    def _run_multi_threaded(self):

        try:
            while not self._stop.is_set():
                events = self._selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        self.accept_wrapper(key.fileobj)
                    else:
                        self.service_connection(key, mask)

        except KeyboardInterrupt:
            self._stop.set()
        finally:
            self._selector.close()


    def _run_single_threaded(self):
        while not self._stop.is_set():
            success, frame = self.receive()
            if success:
                self._count += 1
                self._queue.put(frame)

            if (time.time() - self._last_tick) > (self._TICK_PERIOD / 1000):
                self._last_tick = time.time()
                logger.info(f"Computed framerate {self._count / (self._TICK_PERIOD / 1000)}")
                self._count = 0

    def run(self):
        if self._parallel:
            self._run_multi_threaded()
        else:
            self._run_single_threaded()

    @staticmethod
    def decode(stringData):
        #print(stringData)
        try:
            data = np.frombuffer(stringData, dtype='uint8')
        except TypeError:
            return None

        if len(data) == 0:
            return None
        decimg = cv2.imdecode(data, 1)
        return decimg
 

    def receive(self):
        logger.debug("Receiving frame")
        conn, addr = self._sock.accept()
        length = self.recvall(conn, 16)
        stringData = self.recvall(conn, int(length))
        if len(stringData) == 0:
            return False, None
        decimg = self.decode(stringData)
        if decimg is None:
            return False, None

        logger.debug("Received frame was decoded successfully")
        conn.close()
        return True, decimg

    def dequeue(self):
        success = False
        try:
            frame = self._queue.get(block=True)
            logger.debug("Dequed a received frame")
            success = True
        except queue.Empty:
            frame = None
        return success, frame

    def stop(self):
        self._stop.set()
        self.close()

    def close(self):
        self._sock.close()

if __name__ == "__main__":

    TCP_IP = '0.0.0.0'
    TCP_PORT = 8084

    tcp_server = TCPServer(TCP_IP, TCP_PORT)
    tcp_server.daemon = True
    tcp_server.start()
    try:
        while True:
            success, frame = tcp_server.dequeue()
            if success:
                print(frame.shape)

    except KeyboardInterrupt:
        tcp_server.stop()
        cv2.destroyAllWindows()

    sys.exit(0)

