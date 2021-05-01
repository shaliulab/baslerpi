#!/usr/bin/python
import socket
import threading
import queue
import time
import sys
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class TCPServer(threading.Thread):
    """
    Receive TCP requests in the background
    """

    def __init__(self, ip, port, *args, **kwargs):

        self._ip = ip
        self._port = port

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind((self._ip, self._port))
        self._sock.listen(True)
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        super().__init__(*args, **kwargs)

    @staticmethod
    def recvall(sock, count):
        buf = b''
        while count:
            newbuf = sock.recv(count)
            if not newbuf: return None
            buf += newbuf
            count -= len(newbuf)
        return buf


    def run(self):
        while not self._stop.is_set():
            success, frame = self.receive()
            if success:
                self._queue.put(frame)

    def receive(self):
        logger.debug("Receiving frame")
        conn, addr = self._sock.accept()
        length = self.recvall(conn, 16)
        try:
            stringData = self.recvall(conn, int(length))
            data = np.frombuffer(stringData, dtype='uint8')
        except TypeError:
            return False, None
        decimg = cv2.imdecode(data, 1)
        logger.debug("Received frame was decoded successfully")
        return True, decimg

    def dequeue(self):
        success = False
        try:
            frame = self._queue.get(block=False)
            logger.debug("Dequed a received frame")
            success = True
        except queue.Empty:
            frame = None
        return success, frame

    def stop(self):
        self._stop.set()
        time.sleep(1)
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

