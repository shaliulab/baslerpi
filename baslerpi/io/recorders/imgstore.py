import traceback
import queue
import logging
import time
import multiprocessing
from baslerpi.exceptions import ServiceExit


import numpy as np

from baslerpi.io.recorders.core import BaseRecorder
from baslerpi.io.recorders.async_writers import ImgStoreAsyncWriter
from baslerpi.decorators import timing
from baslerpi.constants import ENCODER_FORMAT_CPU

logger = logging.getLogger(__name__)

class ImgStoreRecorder(BaseRecorder):

    _asyncWriterClass = ImgStoreAsyncWriter
    _dtype = np.uint8
        
    # look here for possible formats:
    # Video -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L932
    # Images -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L805
    # if you dont have enough RAM, you dont want to make this number huge
    # otherwise you will run out of RAM

    def __init__(self, *args, format=ENCODER_FORMAT_CPU, chunk_duration_s = 300, buffer_size=500, info_frequency=2, extra_data_frequency=60000, **kwargs):
        super(ImgStoreRecorder, self).__init__(*args, **kwargs)

        self._lost_frames = 0
        self._current_chunk = -1
        self.extra_data_freq_ms = extra_data_frequency
        self.chunk_duration_s = chunk_duration_s
        self._chunksize = self.chunk_duration_s * self._framerate
        self._buffer_usage = 0
        self._info_frequency = info_frequency
        self._format = format
        self._start_event = multiprocessing.Event()

        self._data_queue = multiprocessing.Queue(maxsize=buffer_size)
        self._stop_queue = multiprocessing.Queue(1)
        self._init_async_writer()
        self._show_initialization_info()

    @property
    def n_saved_frames(self):
        if self._async_writer is not None:
            return self._async_writer.n_saved_frames
        else:
            return 0


    @property
    def buffer_usage(self):
        return self._buffer_usage
    
    @property
    def needs_refresh(self):
        return self._sensor is not None and self._time_s > (self._last_update + self.EXTRA_DATA_FREQ)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return f"ImgStore - {self.idx}"


    def _init_async_writer(self):
        async_writer_kwargs = {
            "framerate": self._framerate,
            "path": self._path,
            "resolution": self.resolution,
            "imgdtype": self._dtype,
            "chunksize": self._chunksize,
            "roi": self._roi,
        }

        self._async_writer = self._asyncWriterClass(
            data_queue=self._data_queue,
            stop_queue=self._stop_queue,
            make_tqdm=False,
            idx=self.idx,
            format=self._format,
            info_frequency=self._info_frequency,
            **async_writer_kwargs
        )

    def _save_extra_data(self, **kwargs):
        store = self._async_writer._video_writer
        try:
            store.add_extra_data(**kwargs)
            return 0
        except Exception as error:
            logger.error(
                "Unknown error. See more details following this message"
            )
            logger.error(error)
            logger.error(traceback.print_exc())
            return 1


    def _get_environmental_data(self):
        return self.sensor.query(timeout=1)


    def save_extra_data(self, timestamp):

        self._time_s = timestamp
        code = 0

        if self.needs_refresh:      

            logger.debug("_get_environmental_data")
            environmental_data = self._get_environmental_data()

            if environmental_data is None:
                logger.warning("Could not fetch environmental data")
            else:
                print(environmental_data)
                logger.debug("_save_extra_data")
                code = self._save_extra_data(
                    temperature=environmental_data["temperature"],
                    humidity=environmental_data["humidity"],
                    light=environmental_data["light"],
                    time=timestamp,
                )
            self._last_update = timestamp

        return code


    def open(self, path):

        if path != self._async_writer.path:
            self._async_writer._video_writer.close()
            self._path = path
            self._init_async_writer()

        logger.debug("Starting async writer")
        self._async_writer.start()
        self.start_time = time.time()


    def _show_initialization_info(self):
        logger.info("Initializing Imgstore video with following properties:")
        logger.info("  Resolution: %dx%d", *self.resolution)
        logger.info("  Path: %s", self._path)
        logger.info("  Format (codec): %s", self._async_writer._format)
        logger.info("  Chunksize: %s", self._chunksize)
        logger.info("  Framerate: %s", self._framerate)


    def terminate(self):
    
        self.close()
        time.sleep(1)
        super(ImgStoreRecorder, self).terminate()
        time.sleep(1)


    def put(self, data):

        if self._async_writer.is_full():
            self._lost_frames += 1
            if self._lost_frames % 100 == 0 or self._async_writer._n_saved_frames % 100 == 0:
                logger.warning(
                    "Data queue is full!"\
                    f" Wrote {self._async_writer._n_saved_frames} frames."\
                    f" Lost {self._lost_frames} frames"
                )
            self._data_queue.get()

        self._data_queue.put(data)


    def write(self, timestamp, i, frame):

        if not self._async_writer._stop_event.is_set():
            self.put((timestamp, i, frame))
            self._timestamp = timestamp
            if self._async_writer._has_new_chunk():
                self._async_writer._save_first_frame_of_chunk(frame)

    def close(self):
        # to tell the async writer the recorder is finished
        self._stop_queue.put("STOP")
        self._async_writer._stop_event.wait(.1)
        # so the async writer knows when there will be for sure no more data coming
        self._data_queue.put(None)

    def run(self):
        """
        Collect frames from the source and write them to the video
        Periodically log #frames saved
        """
        logger.debug("first line of imgstore.run")

        self._start_event.set()

        try:
            logger.debug("before call to imgstore._run")
            self._run()
            logger.debug("after call to imgstore._run")
    
        except ServiceExit:
            print(f"ServiceExit detected by {self}. Please wait")
        except Exception as error:
            logger.error(error)
            logger.error(traceback.print_exc())

        finally:
            logger.debug("_async_writer.join")
            self._async_writer.join()
            logger.debug("_async_writer.joined")
            # to avoid hanging
            self._exit_gracefully()
            # TODO 
            # Comment when using multiprocessing.Process
            # self.exitcode = code
            logger.debug("imgstore finishing")
            logger.debug(
                "Queues: "\
                f" data_queue: {self._data_queue.qsize()}"\
                f" stop_queue: {self._stop_queue.qsize()}"\
            )
            logger.debug(
                f"async_writer: {self._async_writer.is_alive()}"
            )
            return 


    def _exit_gracefully(self):
        assert self._async_writer._check_data_queue(target=0), f"Buffer usage {self._async_writer.buffer_usage} != 0"
        assert self._stop_queue.empty()
        return 0


    def _wait_for_async_writer(self):
        while not self._async_writer.ready and not self._async_writer.finished:
            time.sleep(0.1)


        logger.debug("_wait_for_async_writer out of while")

        if self._async_writer.finished:
            logger.debug("async_writer is finished")
        else:
            logger.debug("async_writer is ready")


    def _run(self):
        logger.debug("inside call to imgstore._run")
        logger.debug("imgstore._wait_for_async_writer")
        self._wait_for_async_writer()
        logger.debug(f"{self}._run.while")      
        while self._async_writer.is_alive():
            self._async_writer._report(self._buffer_usage)
            self.save_extra_data(self._async_writer._time_s)
            if self.should_stop():
                break

        logger.debug(f"async_writer is alive: {self._async_writer.is_alive()}")
        logger.debug(f"should stop: {self.should_stop()}")
  
    # def safe_join(self, timeout):
    #     rc = self._tstate_lock.acquire(True, timeout)

    #     if rc:
    #         exitcode = 0
    #     else:
    #         import ipdb; ipdb.set_trace()
    #         exitcode = 1

    #     return exitcode

    def safe_join(self, timeout):
        self.join(timeout=timeout)
        if self.exitcode is None:
            return 1
        else:
            return self.exitcode


    def should_stop(self):

        result = (
            self.duration_reached
            or self.max_frames_reached
        )

        return result