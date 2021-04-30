import socket
import threading
import queue
import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class TCPClient(threading.Thread):

    def __init__(self, ip, port, *args, **kwargs):
        self._ip = ip
        self._port = port
        self._encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self.connect()
        super().__init__(*args, **kwargs)


    def connect(self):
        logger.debug("Opening socket")
        self._sock = socket.socket()
        self._sock.connect((self._ip, self._port))

    def queue(self, frame):
        logger.debug("Queuing frame in TCP client")
        self._queue.put(frame)

    def stream(self, frame):
        result, imgencode = cv2.imencode('.jpg', frame, self._encode_param)
        data = np.array(imgencode)
        stringData = data.tostring()
        send1 = str(len(stringData)).ljust(16)
        logger.debug("Sending frame to TCP server")
        try:
            self._sock.send(send1.encode("utf-8"));
            self._sock.send(stringData);
        except (ConnectionResetError, BrokenPipeError):
            self.close()
            self.connect()
        return data

    def run(self):

        while not self._stop.is_set():
            frame = self._queue.get()
            data = self.stream(frame)
            #decimg=cv2.imdecode(data,1)
        self.close()

    def close(self):
        logger.debug("Closing socket")
        self._sock.close()

    def stop(self):
        logger.debug("Stopping TCP server")
        self._stop.set()
        time.sleep(1)
        self.close()

if __name__ == "__main__":
    frame = np.random.randint(255, size=(900,800,3),dtype=np.uint8)
    TCP_IP = '10.43.207.46'
    TCP_PORT = 8082

    client = TCPClient(TCP_IP, TCP_PORT)
    client.queue(frame)
    client.start()
    client.stop()


