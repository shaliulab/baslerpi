
import logging
import datetime
import time
import threading
import queue
import inspect


logger = logging.getLogger(__name__)

import numpy as np
import tqdm
import skvideo.io
import cv2
import imgstore

FMT_TO_CODEC = {
    "h264/avi": "libx264"
}

class FFMPEGMixin:
    """
    Teach a Recorder class how to use FFMPEG to write a video
    """

    def open(self, **kwargs):

        self._path = kwargs["path"]

        # skvideo.io.FFmpegWriter expects kwarg named filename
        # but this Python module names this argument throught the code path
        kwargs["filename"] = kwargs.pop("path")


        # Report information to user
        logger.info("Initializing FFMPEG video with following properties:")
        logger.info("  Framerate: %d", self._framerate)
        logger.info("  Resolution: %dx%d", *self.resolution)
        logger.info("  Path: %s", self._path)

        # Initialize video writer
        if "inputdict" not in kwargs.keys():
            logger.info("Using default inputdict")
            kwargs["inputdict"] = self.inputdict

        if "outputdict" not in kwargs.keys():
            logger.info("Using default outputdict")
            kwargs["outputdict"] = self.outputdict

        if "fmt" in kwargs:
            fmt = kwargs.pop("fmt")
            kwargs["outputdict"]["-c:v"] = FMT_TO_CODEC[fmt]


        self._video_writer = skvideo.io.FFmpegWriter(
            **kwargs, verbosity=1
        )

    def write(self, frame, i, timestamp):
        frame = self.pipeline(frame)
        self._video_writer.writeFrame(frame)

    def close(self):
        self._video_writer.close()

class OpenCVMixin:
    """
    Teach a Recorder class how to use OpenCV to write a video
    """
    def open(self, path, maxframes=None):
        """
        Open a cv2.VideoWriter to the specified path
        Only .avi supported
        If output folder does not exist, it is created on the spot

        path: str encoding a filename with our without folder path
        maxframes: int or None with maximum number of frames to fetch
        """
        assert path.split(".")[-1] == "avi"

        self._path = path
        self._maxframes = maxframes

        # Report information to user
        logger.info("Initializing OpenCV video with following properties:")
        logger.info("  Framerate: %d", self._framerate)
        logger.info("  Resolution: %dx%d", *self.resolution)
        logger.info("  Path: %s", self._path)

        # Create folder if required
        if len(self._path.split("/")[-1].split(".")) != 1:
            output_dir = os.path.dirname(self._path)
        else:
            output_dir = self._path

        self._output_dir = output_dir
        if not os.path.isdir(self._output_dir) and self._debug:
                os.mkdir(self._output_dir)

        # Initialize video writer
        self._video_writer = cv2.VideoWriter(
            path,
            #cv2.VideoWriter_fourcc(*"DIVX"),
            cv2.VideoWriter_fourcc(*"XVID"),
            int(self._framerate),
            self.resolution
        )


    def write(self, frame, i, timestamp):
        frame = self.pipeline(frame)
        cv2.imwrite(frame, os.path.join(self._path, f"{str(i).zfill(10)}.png"))

    def close(self):
        """
        Close the cv2.VideoWriter
        """
        self._video_writer.release()



class AsyncWriter(threading.Thread):
    """
    Asynchronous writer of frames using the imgstore module
    """

    def __init__(self, fmt, queue, stop_queue, *args, **kwargs):
        # Initialize video writer
        self._queue = queue
        self._stop_queue = stop_queue
        #keys = list(inspect.signature(imgstore.new_for_format).parameters.keys())
        #imgstore_kwargs = {k: kwargs.pop(k) for k in keys if k in kwargs}
        #print(imgstore_kwargs)
        self._video_writer = imgstore.new_for_format(fmt=fmt, **kwargs)
        self._framecount = 0
        super().__init__(*args)

    def _write(self, frame, i, timestamp):
        self._video_writer.add_image(frame, i, timestamp)

    def run(self):
        while self._stop_queue.empty():
            # if _queue is empty, it waits in an efficient way
            frame, i, timestamp = self._queue.get()
            self._write(frame, i, timestamp)

        cmd = self._stop_queue.get()
        if cmd == "STOP":
            logger.info("CMD STOP received. Stopping recording!")
            self._close()
        else:
            logger.warning(f"CMD {cmd} not understood. Treating as STOP")
            # TODO implement response to other commands if needed here
            self._close()

    def _close(self):
        self._video_writer.close()

class ImgstoreMixin:
    """
    Teach a Recorder class how to use Imgstore to write a video
    """

    _dtype = np.uint8
    _chunksize = 9000
    # look here for possible formats:
    # Video -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L932
    # Images -> https://github.com/loopbio/imgstore/blob/d69035306d816809aaa3028b919f0f48455edb70/imgstore/stores.py#L805
    _asyncWriterClass = AsyncWriter
    _CACHE_SIZE = 1e4


    def open(self, path, fmt="h264/avi", maxframes=None):

        self._path = path
        self._fmt = fmt

        # Report information to user
        logger.info("Initializing Imgstore video with following properties:")
        logger.info("  Resolution: %dx%d", *self.resolution)
        logger.info("  Path: %s", self._path)
        logger.info("  Format (codec): %s", self._fmt)

        kwargs = {"framerate": self._framerate,
                  "mode": 'w',
                  "basedir": self._path,
                  "imgshape": self.resolution[::-1], # reverse order so it becomes nrows x ncols i.e. height x width
                  "imgdtype": self._dtype,
                  "chunksize": self._chunksize
                  }

        self._queue = queue.Queue(maxsize=self._CACHE_SIZE)
        self._stop_queue = queue.Queue()
        self._async_writer = AsyncWriter(self._fmt, self._queue, self._stop_queue, **kwargs)
        self._async_writer.start()
        self._tqdm = tqdm.tqdm(position=1, total=100, unit="")

    @property
    def usage(self):
        return 100 * self._queue.qsize() / self._CACHE_SIZE

    def _info(self):
         # logger.info("Usage: {self.usage}%")
         self._tqdm.n = int(self.usage)
         self._tqdm.refresh()

    def write(self, frame, i, timestamp):
        frame = self.pipeline(frame)
        if self._queue.full():
            self._lost_frames += 1
            logger.warning("Lost %5.d frames" % self._lost_frames)
        self._queue.put((frame, i, timestamp))
        #self._async_writer.write(frame, i)

    def close(self):
        logger.info("Quiting recorder...")
        self._stop_queue.put("STOP")
        #self._video_writer.close()
