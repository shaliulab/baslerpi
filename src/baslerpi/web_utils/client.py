import socket
import threading
import queue
import logging
import time

import cv2
import numpy as np

class TCPClient(threading.Thread):

    def __init__(self, ip, port, *args, **kwargs):
        self._ip = ip
        self._port = port
        self._encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
        self._sock = socket.socket()
        self._sock.connect((self._ip, self._port))
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()

        super().__init__(*args, **kwargs)

    def queue(self, frame):
        self._queue.put(frame)

    def stream(self, frame):
        result, imgencode = cv2.imencode('.jpg', frame, self._encode_param)
        data = np.array(imgencode)
        stringData = data.tostring()
        send1 = str(len(stringData)).ljust(16)
        self._sock.send(send1.encode("utf-8"));
        self._sock.send(stringData);
        return data

    def run(self):

        while not self._stop.is_set():
            frame = self._queue.get()
            data = self.stream(frame)
            decimg=cv2.imdecode(data,1)
            cv2.imshow('CLIENT',decimg)
            cv2.waitKey(1)

        self.close()

    def close(self):
        logging.info("Closing")
        sock.close()

    def stop(self):
        logging.info("Stopping")
        self._stop.set()

if __name__ == "__main__":
    frame = np.random.randint(255, size=(900,800,3),dtype=np.uint8)
    TCP_IP = '10.43.207.46'
    TCP_PORT = 8082

    client = TCPClient(TCP_IP, TCP_PORT)
    client.queue(frame)
    client.run()
    time.sleep(1)
    cliet.stop()


