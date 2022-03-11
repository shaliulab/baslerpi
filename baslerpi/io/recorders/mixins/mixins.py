import logging
import os.path

import skvideo.io
import cv2

logger = logging.getLogger(__name__)

FMT_TO_CODEC = {"h264/avi": "libx264"}


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

        self._video_writer = skvideo.io.FFmpegWriter(**kwargs, verbosity=1)

    def write(self, frame, i, timestamp):
        frame = self.pipeline(frame)
        self._video_writer.writeFrame(frame)

    def close(self):
        self._video_writer.close()


class OpenCVMixin:
    """
    Teach a Recorder class how to use OpenCV to write a video
    """

    def open(self, path, maxframes=None, **kwargs):
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
        os.makedirs(self._output_dir, exist_ok=True)

        # Initialize video writer
        self._video_writer = cv2.VideoWriter(
            path,
            # cv2.VideoWriter_fourcc(*"DIVX"),
            cv2.VideoWriter_fourcc(*"XVID"),
            int(self._framerate),
            self.resolution,
        )

    def write(self, frame, i, timestamp):
        frame = self.pipeline(frame)
        cv2.imwrite(frame, os.path.join(self._path, f"{str(i).zfill(10)}.png"))

    def close(self):
        """
        Close the cv2.VideoWriter
        """
        self._video_writer.release()
