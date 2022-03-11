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
        self._encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        super().__init__(*args, **kwargs)

    def connect(self):
        logger.debug("Opening socket")
        self._sock = socket.create_connection((self._ip, self._port))
        # self._sock = socket.socket()
        # self._sock.connect((self._ip, self._port))

    def queue(self, frame):
        logger.debug("Queuing frame in TCP client")
        self._queue.put(frame)

    def stream(self, frame):
        result, imgencode = cv2.imencode(".jpg", frame, self._encode_param)
        # data = np.array(imgencode)
        data = imgencode
        stringData = data.tostring()
        header = str(len(stringData)).ljust(16)
        logger.debug("Sending frame to TCP server")
        try:
            self.connect()
        except ConnectionRefusedError as error:
            logger.warning("Connection refused")
            return None

        self._sock.send(header.encode("utf-8"))
        self._sock.send(stringData)
        self.close()
        return data

    def run(self):

        while not self._stop.is_set():
            frame = self._queue.get()
            data = self.stream(frame)
            # decimg=cv2.imdecode(data,1)

    def close(self):
        logger.debug("Closing socket")
        self._sock.close()


# def encode(frame):
#
#    encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
#    bef = time.time()
#    result, imgencode = cv2.imencode('.jpg', frame, encode_param)
#    aft = time.time()
#    encoding_logger.debug(f"Elapsed time encoding frame: {aft-bef}")
#
#    data = np.array(imgencode)
#    stringData = data.tostring()
#    return stringData
#
#
# def parallel_encoding(in_q, out_q):
#    while True:
#        frame = in_q.get()
#        encoded_frame = encode(frame)
#        out_q.put(encoded_frame)


class FastTCPClient(TCPClient):
    def __init__(self, in_q, *args, **kwargs):
        self.manager = multiprocessing.Manager()
        # in_q = self.manager.Queue(maxsize=1)
        out_q = self.manager.Queue(maxsize=1)
        self.in_q = in_q
        self.out_q = out_q
        self._stop_event = multiprocessing.Event()
        # self._streamingThread = threading.Thread(target=self.streaming_thread_worker)
        # self._streamingThread.start()
        super().__init__(*args, **kwargs)

    @staticmethod
    def encode(frame, *args):

        try:
            if frame.dtype == np.uint8:
                pass
            else:
                raise Exception("Passed frame type is not np.uint8")
        except AttributeError as error:
            # print(frame)
            raise error

        bef = time.time()
        result, imgencode = cv2.imencode(".jpg", frame, *args)
        aft = time.time()
        encoding_logger.debug(f"Elapsed time encoding frame: {aft-bef}")
        data = np.array(imgencode)
        stringData = data.tostring()
        return stringData

    @staticmethod
    def parallel_encoding(
        in_q, out_q, ip, port, stream, encode, chunk_size, *args
    ):
        current_process = multiprocessing.current_process().name
        logger.info(f"{current_process}: Starting...")

        count = 0
        last_tick = 0
        now = time.time()
        while True:
            print(f"Getting frame at {time.time() - now}")
            t_ms, frame = in_q.get(block=True, timeout=2)
            if (t_ms + 50) < (time.time() * 1000):
                print("Removing frame")
                del frame
            else:
                print(t_ms + 50)
                print(time.time())
                print(f"Encoding frame at {time.time() - now}")
                encoded_frame = encode(frame, *args)
                networking_logger.debug(f"{current_process}: Streaming frame")
                print(f"Streaming frame at {time.time() - now}")
                try:
                    stream(ip, port, encoded_frame, chunk_size)
                except Exception as error:
                    print(error)
                    print("Some problem happened during streaming. See error")
                print(f"Done at {time.time() - now}")
                count += 1
                if (t_ms - last_tick) > 1000:
                    last_tick = t_ms
                    logger.info(f"{current_process} framerate: {count}")
                    count = 0
                # out_q.put(encoded_frame)

    @staticmethod
    def dummy(in_q, *args):
        current_process = multiprocessing.current_process().name
        logger.info(f"{current_process}: Starting...")

        while True:
            t_ms, frame = in_q.get(block=True, timeout=2)
            time.sleep(1)
        # current_process = multiprocessing.current_process().name
        # logger.info(f"{current_process}: Starting...")

    def run(self):
        processes = 1
        args = (
            self.in_q,
            self.out_q,
            self._ip,
            self._port,
            self.stream,
            self.encode,
            self._CHUNK_SIZE,
            self._ENCODE_PARAM,
        )

        frames_available = self.in_q.qsize()
        while frames_available == 0:
            time.sleep(1)
            frames_available = self.in_q.qsize()

        with multiprocessing.Pool(processes=processes) as pool:
            # workers = pool.apply(self.parallel_encoding, args)
            workers = [
                pool.apply_async(self.parallel_encoding, args)
                for i in range(processes)
            ]
            # workers = [pool.apply(self.dummy, args) for i in range(processes)]
            [w.get() for w in workers]

    def has_stopped(self):
        return self._stop_event.is_set()

    def stop(self):
        logger.debug("Stopping TCP server")
        self._stop.set()
        time.sleep(1)
        self.close()


if __name__ == "__main__":
    frame = np.random.randint(255, size=(900, 800, 3), dtype=np.uint8)
    TCP_IP = "10.43.207.46"
    TCP_PORT = 8082

    client = TCPClient(TCP_IP, TCP_PORT)
    client.queue(frame)
    client.start()
    client.stop()
