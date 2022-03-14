import logging

import skvideo.io
from baslerpi.constants import FMT_TO_CODEC

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
        logging.info("Initializing FFMPEG video with following properties:")
        logging.info("  Framerate: %d", self._framerate)
        logging.info("  Resolution: %dx%d", *self.resolution)
        logging.info("  Path: %s", self._path)

        # Initialize video writer
        if "inputdict" not in kwargs.keys():
            logging.info("Using default inputdict")
            kwargs["inputdict"] = self.inputdict

        if "outputdict" not in kwargs.keys():
            logging.info("Using default outputdict")
            kwargs["outputdict"] = self.outputdict

        if "format" in kwargs:
            format = kwargs.pop("format")
            kwargs["outputdict"]["-c:v"] = FMT_TO_CODEC[format]

        self._video_writer = skvideo.io.FFmpegWriter(**kwargs, verbosity=1)

    def write(self, frame, i, timestamp):
        self._video_writer.writeFrame(frame)

    def close(self):
        self._video_writer.close()

