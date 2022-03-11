import sys
import threading
import traceback
import logging
import os
import os.path
import queue
import collections

import numpy as np
import tqdm
import imgstore
import cv2
import time
import multiprocessing

from baslerpi.exceptions import ServiceExit
from baslerpi.decorators import timing

logger = logging.getLogger(__name__)


class AsyncWriter(threading.Thread):
    """
    Asynchronous writer of frames using the imgstore module
    """

    _CACHE_SIZE = int(500)
    INFO_FREQ = 10000 # ms

    def __init__(
        self,
        fmt,
        data_queue,
        stop_queue,
        path,
        framerate,
        logging_level=30,
        make_tqdm=False,
        idx=0,
        *args,
        **kwargs,
    ):
        # Initialize video writer
        self._data_queue = data_queue
        self._stop_queue = stop_queue
        self._stop_event = threading.Event()
        self._stop_time = None
        self._fmt = fmt
        self._video_writer = imgstore.new_for_format(fmt=fmt, framerate=framerate, **kwargs)
        self._current_chunk = -1
        self._n_saved_frames = 0
        self._logging_level = logging_level
        self._timestamp = 0
        self._last_tick = 0
        self._cache_size = 0
        self._write_latency = collections.deque([], int(framerate*10))
        self._file_size = collections.deque([], int(framerate*10))

        self._path = path
        self._make_tqdm = make_tqdm
        self.idx = idx

        if make_tqdm:
            self._tqdm = tqdm.tqdm(
                position=self.idx,
                total=self._CACHE_SIZE,
                unit="",
                desc=f"{self.name} - {self.idx}" + r" % Buffer usage",
            )

        super().__init__(*args)

    def __str__(self):
        return f"{self._data_queue.name} - {self.idx}"

    @property
    def n_saved_frames(self):
        return self._n_saved_frames

    @property
    def name(self):

        return self._data_queue.__str__()

    @property
    def timestamp(self):
        return self._timestamp

    def _write(self, timestamp, i, frame):
        if self._logging_level <= 10:
            print("Async writer writing to video")
        self._video_writer.add_image(frame, i, timestamp)
        self._n_saved_frames += 1

    def is_alive(self):
        # print(f"{self} is alive: {not self._stop_event.is_set()}")
        return not self._stop_event.is_set()

    def _handle_data_queue(self):
        try:
            self._report_cache_usage()
            data = self._data_queue.get(False)
        except queue.Empty:
            pass
        except ServiceExit:
            self._handle_stop_queue()
        except Exception as error:
            logger.error(error)
            logger.error(traceback.print_exc())
        else:
            timestamp, i, frame = data
            self._timestamp = timestamp
            # print("Writing data to video imgstore writer")

            before = time.time()
            self._write(timestamp, i, frame)
            after = time.time()

            ms_to_write = (after - before) * 1000
            bytes = sys.getsizeof(frame)
            MB = round(bytes / 1024, ndigits=2)
            self._file_size.append(MB)
            self._write_latency.append(ms_to_write)
            
            # print("Checking if a new chunk is produced")
            if self._has_new_chunk():
                self._save_first_frame_of_chunk(frame)

    def _handle_stop_queue(self):
        if self._stop_queue.empty():
            return None
        else:
            return self._stop_queue.get()

    def _need_to_run(self):
        queue_is_empty = self._data_queue.qsize() == 0
        # print(f"""
        # Exit while loop because need_to_run:
        # {self._stop_event.is_set()} and queue is empty: {queue_is_empty}
        # """)

        if not self._stop_event.is_set():
            result = not queue_is_empty
        else:
            result = not queue_is_empty

        # print("Need to run: ", result)
        # print(result)

        return result

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

    def _run(self):
        print("While loop")
        while True:
            # print("Handling data queue...")
            self._handle_data_queue()

            # print("Checking if we need to run...")
            if not self._need_to_run():
                time.sleep(5)
                if not self._need_to_run():
                    # print("I dont need to run anymore")
                    break


            msg = self._handle_stop_queue()
            if msg == "STOP":
                print("CMD STOP received. Stopping recording!")
                print(f"Setting {self} stop event")
                self._stop_event.set()
                while not self._data_queue.empty():
                    self._handle_data_queue()
                    if self._data_queue.empty():
                        time.sleep(1)

        print("While loop exit")

    def run(self):
        try:
            print(f"{self}: First call to self._run")
            self._run()
            print(f"{self}: End of first call to self._run")
        except ServiceExit:
            print("Service Exit received. Please wait")
            self._run()
        except Exception as error:
            print(error)
            print(traceback.print_exc())
        finally:
            self._handle_stop_queue()
            # wait for the handling to be finished
            # by the queue thread and then close the queue!
            time.sleep(1)
            print("Closing video writer")
            self._video_writer.close()
            # give a bit of time to the video writer to actually close
            time.sleep(2)
            print("Async writer has terminated successfully")
            self._stop_event.set()
            return 0

    def _close(self):
        logger.info("Quiting recorder...")
        if self._make_tqdm:
            self._tqdm.close()

        print(f"Setting {self} stop event")
        self._stop_event.set()

    def _check_data_queue_is_busy(self):
        try:
            cache_size = self._data_queue.qsize()
        except Exception as error:
            print(error)
            self._cache_size = 0
        else:
            if cache_size != self._cache_size:
                logger.info(
                    f"{cache_size} frames are accumulated in the cache (max {self._CACHE_SIZE} frames)"
                )
                self._cache_size = cache_size

    def _report_cache_usage(self):
        self._check_data_queue_is_busy()
        if (self._last_tick + self.INFO_FREQ) < self._timestamp:
            if self._make_tqdm:
                self._tqdm.n = int(self._cache_size)
                self._tqdm.refresh()
            else:
                print(
                    self,
                    f" {self._cache_size}/{self._CACHE_SIZE} of buffer in use",
                )

                ms_latency_mean = np.array(self._write_latency).mean()
                print(f"Average write time: {ms_latency_mean:.2f} ms")
                file_size_mean = np.array(self._file_size).mean()
                print(f"Average file size: {file_size_mean:.2f} MB")

            self._last_tick = self._timestamp


class ImgStoreMixin:
    """
    Teach a Recorder class how to use Imgstore to write a video
    """

    _CHUNK_DURATION_SECONDS = 300 # seconds
    EXTRA_DATA_FREQ = 60000  # ms
    _dtype = np.uint8
    # look here for possible formats:
    # Video -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L932
    # Images -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L805
    _asyncWriterClass = AsyncWriter
    # if you dont have enough RAM, you dont want to make this number huge
    # otherwise you will run out of RAM

    @property
    def n_saved_frames(self):
        if self._async_writer is not None:
            return self._async_writer.n_saved_frames
        else:
            return 0

    def _save_extra_data(self, **kwargs):
        store = self._async_writer._video_writer
        logger.info("Writing environmental data")
        try:
            store.add_extra_data(**kwargs)
        except ValueError as error:
            logger.error(
                f"Cannot save extra data on chunk {store._chunk_n}. See more details following this message. I will try to recover from it"
            )
            logger.error(error)
            logger.error(traceback.print_exc())
        except Exception as error:
            logger.error(
                "Unknown error. See more details following this message"
            )
            logger.error(error)
            logger.error(traceback.print_exc())

        return 0

    def save_extra_data(self, timestamp):

        if self._sensor is not None and timestamp > (
            (self._last_update + self.EXTRA_DATA_FREQ)
        ):
                # timestamp comes in ms
            # print("Full tick")
            # print(f"Last update: {self._last_update}")
            # print(f"EXTRA_DATA_FREQ: {self.EXTRA_DATA_FREQ}")
            # print(f"Timestamp: {timestamp}")
            # print(self._last_update + self.EXTRA_DATA_FREQ)

            environmental_data = self._sensor.query(timeout=1)
            if environmental_data is not None:
                print("Saving environmental data")
                print(environmental_data)
                self._save_extra_data(
                    temperature=environmental_data["temperature"],
                    humidity=environmental_data["humidity"],
                    light=environmental_data["light"],
                    time=timestamp,
                )
            self._last_update = timestamp

        else:
            pass
            # self._save_extra_data(
            #     temperature=np.nan,
            #     humidity=np.nan,
            #     light=np.nan,
            #     time=timestamp,
            # )

    def open(self, path, logging_level=30, **kwargs):

        self._current_chunk = -1
        self._logging_level = logging_level

        self._path = path
        self._chunksize = self._CHUNK_DURATION_SECONDS * self._framerate
        print(f"Framerate: {self._framerate}")

        async_writer_kwargs = {
            "framerate": self._framerate,
            "mode": "w",
            "basedir": self._path,
            # reverse order so it becomes nrows x ncols i.e. height x width
            "imgshape": self.imgshape,
            "imgdtype": self._dtype,
            "chunksize": self._chunksize,
            "roi": self._roi,
            "path": self._path,
            "logging_level": logging_level,
        }

        kwargs.update(async_writer_kwargs)

        self._async_writer = self._asyncWriterClass(
            data_queue=self._data_queue,
            stop_queue=self._stop_queue,
            make_tqdm=False,
            idx=self.idx,
            **kwargs,
        )
        self._show_initialization_info()

    def _show_initialization_info(self):
        logger.info("Initializing Imgstore video with following properties:")
        logger.info("  Resolution: %dx%d", *self.resolution)
        logger.info("  Path: %s", self._path)
        logger.info("  Format (codec): %s", self._async_writer._fmt)
        logger.info("  Chunksize: %s", self._chunksize)

    def _check_data_queue_is_not_full(self):

        if self._data_queue.full():
            self._lost_frames += 1
            logger.warning("Lost %5.d frames" % self._lost_frames)

    #@timing
    def write(self, frame, i, timestamp):

        self._check_data_queue_is_not_full()
        if self._logging_level <= 10:
            print(self._async_writer.is_alive())
        self._data_queue.put((frame, i, timestamp))
        self._timestamp = timestamp
        self._check_data_queue_is_busy()
        if self._has_new_chunk():
            self._save_first_frame_of_chunk(frame)

    def close(self):
        self._stop_queue.put("STOP")
        self._close_source()  # only does something when running with a camera
        # super().close()
