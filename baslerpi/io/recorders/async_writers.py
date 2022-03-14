import chunk
import logging
import os.path
import threading
import imgstore
import collections
import time
import traceback
import sys
import queue
import multiprocessing

import numpy as np
import cv2
import tqdm
from baslerpi.exceptions import ServiceExit

logger = logging.getLogger(__name__)
run_logger = logging.getLogger(f"{__name__}.run")
run_logger.setLevel(logging.WARNING)

class ImgStoreAsyncWriter(threading.Thread):
    """
    Asynchronous writer of frames using the imgstore module
    """

    def __init__(
        self,
        data_queue,
        stop_queue,
        path,
        framerate,
        chunksize,
        format,
        idx=0,
        imgdtype = np.uint8,
        resolution=None,
        make_tqdm=False,
        info_frequency=2,
        roi=None
    ):

        self._resolution = resolution
        imgshape = resolution[::-1]

        self._format = format
        self._path = path
        self._framerate = framerate
        self._imgshape = imgshape
        self._chunksize = chunksize
        self._imgdtype = imgdtype
        self._video_writer = imgstore.new_for_format(
            mode="w",
            fmt=format,
            framerate=framerate,
            basedir=path,
            imgshape=imgshape,
            chunksize=chunksize,
            imgdtype=imgdtype,
        )

        self._data_queue = data_queue
        self._stop_queue = stop_queue
        self._stop_event = multiprocessing.Event()
        self._stop_time = None
        self._roi = roi
        
        self._current_chunk = -1
        self._n_saved_frames = 0
        self._time_s = 0
        self._write_latency = collections.deque([], int(framerate*10))
        self._file_size = collections.deque([], int(framerate*10))
        self._last_info_tick = 0

        self._make_tqdm = make_tqdm
        self.idx = idx

        self.buffer_size = self._data_queue._maxsize
        self.buffer_usage = 0
        self.info_frequency = info_frequency

        if make_tqdm:
            self._tqdm = tqdm.tqdm(
                position=self.idx,
                total=self.buffer_size,
                unit="",
                desc=f"{self.name} - {self.idx}" + r" % Buffer usage",
            )

        super().__init__()

    @property
    def n_saved_frames(self):
        return self._n_saved_frames


    @property
    def ready(self):
        # logger.debug(f"stop_event.is_set: {self._stop_event.is_set()}")
        ready = self.is_alive() and not self._stop_event.is_set()
        logger.debug(f"async_writer.ready = {ready}")
        return ready

    @property
    def finished(self):
        finished = not self.is_alive() and self._stop_event.is_set()
        logger.debug(f"async_writer.finished = {finished}")
        return finished



    @property
    def path(self):
        return self._path

    # def __str__(self):
    #     return self.name

    @property
    def name(self):
        return f"Async writer - {self.idx}"


    @property
    def timestamp(self):
        return self._time_s

    def is_full(self):
        return self._data_queue.full()

    def _need_to_run(self):
        queue_is_empty = self._data_queue.qsize() == 0

        if not self._stop_event.is_set():
            result = not queue_is_empty
        else:
            result = not queue_is_empty

        return result


    def _write(self, timestamp, i, frame):
        self._video_writer.add_image(frame, i, timestamp)
        self._n_saved_frames += 1
    

    def _has_new_chunk(self):
        current_chunk = self._video_writer._chunk_n
        if current_chunk > self._current_chunk:
            self._current_chunk = current_chunk
            return True
        else:
            return False

    def _save_first_frame_of_chunk(self, frame=None):

        last_shot_path = os.path.join(
            self._path, str(self._current_chunk).zfill(6) + ".png"
        )
        cv2.imwrite(last_shot_path, frame)

    def _handle_data_queue(self):
        try:
            data = self._data_queue.get(False)
        except queue.Empty:
            # ignore empty queues
            return 0
        except ServiceExit as error:
            logger.warning(error)
            self.close()
            return 1
        except Exception as error:
            logger.error(error)
            logger.error(traceback.print_exc())
            self.close()
            return 1
        else:
            if data is None:
                return None
            else:
                timestamp, i, frame = data
                self._time_s = timestamp
                
                run_logger.debug("_write")
                before = time.time()
                self._write(timestamp, i, frame)
                after = time.time()

                ms_to_write = (after - before) * 1000
                bytes = sys.getsizeof(frame)
                MB = round(bytes / 1024, ndigits=2)
                self._file_size.append(MB)
                self._write_latency.append(ms_to_write)

                if self._has_new_chunk():
                    self._save_first_frame_of_chunk(frame)

                return data

    def _handle_stop_queue(self):
        if self._stop_queue.empty():
            msg = None
        else:
            msg = self._stop_queue.get()
        if msg == "STOP":
            logger.debug("async_writer.close")
            self.close()

    def _run(self):
        # runs until a STOP message is detected in the stop_queue
        while not self._stop_event.is_set():
            run_logger.debug("_handle_data_queue")
            data = self._handle_data_queue()
            if data is None:
                logger.warning("None received")
            run_logger.debug("_handle_stop_queue")
            self._handle_stop_queue()

        
        while True:
            logger.debug("_handle_data_queue finishing")
            data = self._handle_data_queue()
            if data is None:
                break

        
    def _clear(self):
        
        qsize = self._data_queue.qsize()
        while not self._data_queue.empty():
            self._data_queue.get(block=False)
            time.sleep(.1)

        qsize = self._data_queue.qsize()
        logger.debug(f"_clear finished. qsize = {qsize}")


    def run(self):
        logger.debug("_run")
        try:
            logger.debug("_run")
            self._run()
        except ServiceExit:
            print("Service Exit received. Please wait")
        except Exception as error:
            logger.error(error)
            logger.error(traceback.print_exc())
        finally:
            logger.debug("_video_writer.close")
            self._video_writer.close()
            # give a bit of time to the video writer to actually close
            self._clear()
            return 0

    def close(self):

        if self._make_tqdm:
            self._tqdm.close()
        self._stop_event.set()

    def _report(self, target):
        if (self._last_info_tick + self.info_frequency) < self._time_s:
            self._check_io_benchmark()
            self._check_data_queue(target=target)
            self._last_info_tick = self._time_s

    def _check_io_benchmark(self):

        logger.debug("_check_io_benchmark")
        ms_latency_mean = np.array(self._write_latency).mean()
        print(f"Average write time: {ms_latency_mean:.2f} ms")
        file_size_mean = np.array(self._file_size).mean()
        print(f"Average file size: {file_size_mean:.2f} MB")


    def _check_data_queue(self, target=0):

        buffer_usage = self._data_queue.qsize()
        if buffer_usage != target:

            if self._make_tqdm:
                self._tqdm.n = int(self.buffer_usage)
                self._tqdm.refresh()
            else:

                print(
                    f"Buffer: {buffer_usage} / {self.buffer_size}"
                )

        self.buffer_usage = buffer_usage
        return self.buffer_usage == target