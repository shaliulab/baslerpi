import threading
import traceback
import logging
import os
import os.path
import queue

import numpy as np
import tqdm
import imgstore
import cv2
import time
import multiprocessing

from baslerpi.exceptions import ServiceExit

logger = logging.getLogger(__name__)


class AsyncWriter(threading.Thread):
    """
    Asynchronous writer of frames using the imgstore module
    """

    def __init__(
        self, fmt, data_queue, stop_queue, logging_level=30, *args, **kwargs
    ):
        # Initialize video writer
        self._data_queue = data_queue
        self._stop_queue = stop_queue
        self._stop_event = threading.Event()
        self._stop_time = None
        self._fmt = fmt
        self._video_writer = imgstore.new_for_format(fmt=fmt, **kwargs)
        self._current_chunk = 0
        self._n_saved_frames = 0
        self._logging_level = logging_level
        self._timestamp = 0
        super().__init__(*args)

    @property
    def n_saved_frames(self):
        return self._n_saved_frames

    @property
    def timestamp(self):
        return self._timestamp

    def _write(self, timestamp, i, frame):
        if self._logging_level <= 10:
            print("Async writer writing to video")
        self._video_writer.add_image(frame, i, timestamp)
        self._n_saved_frames += 1

    def _handle_data_queue(self):
        try:
            data = self._data_queue.get(False)
        except queue.Empty:
            pass
        except ServiceExit:
            self._handle_stop_queue()
        else:
            timestamp, i, frame = data
            self._timestamp = timestamp
            self._write(timestamp, i, frame)
            if self._has_new_chunk():
                self._save_first_frame_of_chunk(frame)

    def _handle_stop_queue(self):
        if self._stop_queue.empty():
            return None
        else:
            return self._stop_queue.get()

    def _need_to_run(self):
        queue_condition = (
            self._stop_queue.empty() or not self._data_queue.empty()
        )
        event_condition = (
            not self._stop_event.is_set() and not self._data_queue.empty()
        )
        return queue_condition and event_condition

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

    def run(self):

        while self._need_to_run():
            self._handle_data_queue()
            # if self._logging_level <= 10:
            #     print("I will continue the while loop: ", self._need_to_run())
            msg = self._handle_stop_queue()
            if msg == "STOP" and not self._need_to_run():
                logger.info("CMD STOP received. Stopping recording!")
                self._stop_event.set()
                break

        self._handle_stop_queue()
        # wait for the handling to be finished
        # by the queue thread and then close the queue!
        time.sleep(1)
        print("Closing video writer")
        self._video_writer.close()
        # give a bit of time to the video writer to actually close
        time.sleep(2)
        print("Async writer has terminated successfully")
        return 0

    def _close(self):
        logger.info("Quiting recorder...")
        self._stop_queue.put("STOP")


class ImgStoreMixin:
    """
    Teach a Recorder class how to use Imgstore to write a video
    """

    _CHUNK_DURATION_SECONDS = 300
    _dtype = np.uint8
    # look here for possible formats:
    # Video -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L932
    # Images -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L805
    _asyncWriterClass = AsyncWriter
    # if you dont have enough RAM, you dont want to make this number huge
    # otherwise you will run out of RAM
    _CACHE_SIZE = int(500)

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
            self.self._last_tick + self.EXTRA_DATA_FREQ
        ):
            environmental_data = self._sensor.query(timeout=1)
            if environmental_data is not None:
                self._save_extra_data(
                    temperature=environmental_data["temperature"],
                    humidity=environmental_data["humidity"],
                    light=environmental_data["light"],
                    time=timestamp,
                )
            self.self._last_tick = timestamp

        else:
            self._save_extra_data(
                temperature=np.nan,
                humidity=np.nan,
                light=np.nan,
                time=timestamp,
            )

    def open(self, path, logging_level=30, **kwargs):

        self._current_chunk = -1
        self._logging_level = logging_level

        self._path = path
        self._chunksize = self._CHUNK_DURATION_SECONDS * self._framerate

        async_writer_kwargs = {
            "framerate": self._framerate,
            "mode": "w",
            "basedir": self._path,
            # reverse order so it becomes nrows x ncols i.e. height x width
            "imgshape": self.imgshape,
            "imgdtype": self._dtype,
            "chunksize": self._chunksize,
            "roi": self._roi,
        }

        kwargs.update(async_writer_kwargs)

        self._async_writer = self._asyncWriterClass(
            data_queue=self._data_queue,
            stop_queue=self._stop_queue,
            logging_level=logging_level,
            **kwargs,
        )
        self._show_initialization_info()

        self._tqdm = tqdm.tqdm(
            position=self.idx,
            total=self._CACHE_SIZE,
            unit="",
            desc=f"{self.name} - {self.idx}" + r" % Buffer usage",
        )
        self._cache_size = 0

    def _show_initialization_info(self):
        logger.info("Initializing Imgstore video with following properties:")
        logger.info("  Resolution: %dx%d", *self.resolution)
        logger.info("  Path: %s", self._path)
        logger.info("  Format (codec): %s", self._async_writer._fmt)
        logger.info("  Chunksize: %s", self._chunksize)

    def _report_cache_usage(self):
        self._check_data_queue_is_busy()
        self._tqdm.n = int(self._cache_size)
        self._tqdm.refresh()

    def _check_data_queue_is_not_full(self):

        if self._self._data_queue.full():
            self._lost_frames += 1
            logger.warning("Lost %5.d frames" % self._lost_frames)

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

    def write(self, frame, i, timestamp):

        self._check_data_queue_is_not_full()
        if self._logging_level <= 10:
            print(self._async_writer.is_alive())
        self._self._data_queue.put((frame, i, timestamp))
        self._check_data_queue_is_busy()
        if self._has_new_chunk():
            self._save_first_frame_of_chunk(frame)

    def close(self):
        self._stop_queue.put("STOP")
        self._close_source()  # only does something when running with a camera
