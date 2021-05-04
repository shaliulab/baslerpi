import socket
import threading
import queue
import logging
import time
import selectors
import types
import multiprocessing

import cv2
import numpy as np

logger = logging.getLogger(__name__)
networking_logger = logging.getLogger(__name__ + ".networking")
encoding_logger = logging.getLogger(__name__ + ".encoding")

class TCPClient:

    _num_conns = 1
    #_num_conns = 1
    _ENCODE_PARAM=[int(cv2.IMWRITE_JPEG_QUALITY),90]

    def __init__(self, ip, port, *args, parallel = True, **kwargs):
        self._ip = ip
        self._port = port
        self._count = 0
        super().__init__(*args, **kwargs)


    def encode(self, frame):
        bef = time.time()
        result, imgencode = cv2.imencode('.jpg', frame, self._ENCODE_PARAM)
        aft = time.time()
        encoding_logger.debug(f"Elapsed time encoding frame: {aft-bef}")
 
        data = np.array(imgencode)
        stringData = data.tostring()
        return stringData

    @staticmethod
    def stream(ip, port, stringData):
        CHUNK_SIZE = 1024*10
        header = str(len(stringData)).ljust(16)
        logger.debug("Sending frame to TCP server")
        try:
            sock = socket.create_connection((ip, port))
        except ConnectionRefusedError as error:
            logger.warning("Connection refused")
            return None

        sock.send(header.encode("utf-8"));

        bef = time.time()
        sock.send(stringData);
        aft = time.time()
        networking_logger.debug(f"Elapsed time sending data: {aft-bef}")

        received = 0
        while received < len(stringData):
            #print(received)
            recv_data = sock.recv(CHUNK_SIZE)
            received += len(recv_data)
        sock.close()
        return 0
    
    def _get_and_encode(self):
        frame = self.in_q.get()
        frame = self.encode(frame)
        return frame

    def has_stopped(self):
        raise NotImplementedError


class TCPClientBasic(threading.Thread, TCPClient):
    def __init__(self, *args, **kwargs):

        self._manager = None
        self.in_q = queue.Queue()
        super().__init__(*args, **kwargs)

    def stop(self):
        logger.debug("Stopping TCP client")
        self._stop_event.set()

    def has_stopped(self):
        return self._stop_event.is_set()

    def run(self):
        while not self.has_stopped():
            frame = self._get_and_encode()
            data = self.stream(self._ip, self._port, frame)


class TCPClientThread(threading.Thread, TCPClient):

    def get_messages(self):
        messages = [self.in_q.get(timeout=2) for i in range(self._num_conns)]
        for i, msg in enumerate(messages):
            messages[i] = self.encode(msg)
        return messages

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
            #print(len(messages[0]))
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

        if mask & selectors.EVENT_READ:
            try:
                bef = time.time()
                recv_data = sock.recv(self._CHUNK_SIZE)
                aft = time.time()
                networking_logger.debug(f"Elapsed time receiving recv_data: {aft-bef}")
 
            except Exception as error:
                logger.warning(error)
                logger.warning("Could not receive confirmation from server")
                return 1

            if recv_data:
                data.recv_total += len(recv_data)
                networking_logger.debug("Serving read connection to %s", sock.getpeername()[1])
                networking_logger.debug("Length of received data %s", len(recv_data))
                networking_logger.debug("Length of missing data %s", data.msg_total - data.recv_total)

            if not recv_data or data.recv_total == data.msg_total:
                logger.debug("connection (%s) CLOSE", data.connid)
                if not recv_data:
                    networking_logger.debug("No more data is received")
                if data.recv_total == data.msg_total:
                    networking_logger.debug("Received amount of data is the expected")

                self._selector.unregister(sock)
                sock.close()

            else:
                if recv_data:
                    networking_logger.debug("I am still receiving data")
                    networking_logger.debug(recv_data)
                if data.recv_total != data.msg_total:
                    networking_logger.debug("I still have not received everything back")
                    networking_logger.debug(data.recv_total)
                    networking_logger.debug(data.msg_total)

        if mask & selectors.EVENT_WRITE:
        
            if not data.outb and data.messages:
                data.outb = data.messages.pop(0)

            if len(data.outb) != 0:
                logger.debug("Sending to connection %d", data.connid)
                try:
                    bef = time.time()
                    print(len(data.outb))
                    sent = sock.send(data.outb)
                    aft = time.time()
                    networking_logger.debug(f"Elapsed time sending data.outb: {aft-bef}")
                except Exception as error:
                    logger.warning(error)
                    # TODO Exit at some point, dont keep trying
                    print("Server is closed")
                    sock.close()
                    return 1
                logger.debug("Length of sent data %s", sent)
                data.outb = data.outb[sent:]
                logger.debug("Length of remaining data %s", len(data.outb))

                if len(data.outb) == 0:
                    self._count += 1

    def run(self):

        self._selector = selectors.DefaultSelector()
        #self._messages = [bytes(f"Hello World {i}", "utf-8") for i in range(self._num_conns)]
        messages = self.get_messages()
        self.start_connections(self._ip, self._port, messages, self._num_conns)
        loop = 0

        try:
            while not self.has_stopped():
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
                    #print("I am fetching more messages")
                    messages = self.get_messages()
                    self.start_connections(self._ip, self._port, messages, self._num_conns)
                else:
                    pass
                    #print("Selector map is positive")
                    #print(selector_map)
                    
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_event.set()
            self._selector.close()


#def encode(frame):
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
#def parallel_encoding(in_q, out_q):
#    while True:
#        frame = in_q.get()
#        encoded_frame = encode(frame)
#        out_q.put(encoded_frame)


class FastTCPClient(TCPClient):

    def __init__(self, in_q, *args, **kwargs):
        self.manager = multiprocessing.Manager()
        #in_q = self.manager.Queue(maxsize=1)
        out_q=self.manager.Queue(maxsize=1) 
        self.in_q = in_q
        self.out_q = out_q
        self._stop_event = multiprocessing.Event()
        #self._streamingThread = threading.Thread(target=self.streaming_thread_worker)
        #self._streamingThread.start()
        super().__init__(*args, **kwargs)

    @staticmethod
    def encode(frame, *args):

        try:
            if frame.dtype == np.uint8:
                pass
            else:
                raise Exception("Passed frame type is not np.uint8")
        except AttributeError as error:
            #print(frame)
            raise error
                
        bef = time.time()
        result, imgencode = cv2.imencode('.jpg', frame, *args)
        aft = time.time()
        encoding_logger.debug(f"Elapsed time encoding frame: {aft-bef}")
        data = np.array(imgencode)
        stringData = data.tostring()
        return stringData
    
    @staticmethod
    def parallel_encoding(in_q, out_q, ip, port, stream, encode, *args):
        current_process = multiprocessing.current_process().name
        logger.info(f"{current_process}: Starting...")

        count=0
        last_tick = 0
        while True:
            t_ms, frame = in_q.get(block=True, timeout=2)

            encoded_frame = encode(frame, *args)
            networking_logger.debug(f"{current_process}: Streaming frame")
            stream(ip, port, encoded_frame)
            count+=1
            if (t_ms - last_tick) > 1000:
                last_tick = t_ms
                logger.info(f"{current_process} framerate: {count}")
                count = 0


            #out_q.put(encoded_frame)


    @staticmethod
    def dummy(in_q, *args):
        current_process = multiprocessing.current_process().name
        logger.info(f"{current_process}: Starting...")

        while True:
            t_ms, frame = in_q.get(block=True, timeout=2)
            time.sleep(1)
        #current_process = multiprocessing.current_process().name
        #logger.info(f"{current_process}: Starting...")

    def run(self):
        processes=6
        args = (self.in_q, self.out_q, self._ip, self._port,self.stream,  self.encode, self._ENCODE_PARAM)
        
        #processes_dict={}
        #for i in range(processes):
        #    #p=multiprocessing.Process(target=self.parallel_encoding, args=args)
        #    p=multiprocessing.Process(target=self.dummy, args=args)
        #    p.start()
        #    processes_dict[i]=p

        with multiprocessing.Pool(processes=processes) as pool:
           #workers = pool.apply(self.parallel_encoding, args)
           workers = [pool.apply_async(self.parallel_encoding, args) for i in range(processes)]
           #workers = [pool.apply(self.dummy, args) for i in range(processes)]
           [w.get() for w in workers]

    def has_stopped(self):
        return self._stop_event.is_set()

    def stop(self):
        self._stop_event.set()

    def start(self):
        self.run()

#    def streaming_thread_worker(self):
#        while not self.has_stopped():
#            frame = self.out_q.get(timeout=2)
#            self._count += 1
#            self.stream(frame)

if __name__ == "__main__":
    frame = np.random.randint(255, size=(900,800,3),dtype=np.uint8)
    TCP_IP = '10.43.207.46'
    TCP_PORT = 8082

    client = TCPClient(TCP_IP, TCP_PORT)
    client.queue(frame)
    client.start()
    client.stop()


