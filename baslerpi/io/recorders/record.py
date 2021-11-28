import argparse
import datetime
import math
import threading
import time
import logging

import cv2

from baslerpi.utils import document_for_reproducibility

from baslerpi.io.recorders.mixins import (
    FFMPEGMixin,
    ImgstoreMixin,
)

logger = logging.getLogger("baslerpi.io.record")
LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}


class BaseRecorder(threading.Thread):
    """
    Take an iterable camera object which returns (timestamp, frame)
    in every iteration and save to a path determined in the open() method
    """

    EXTRA_DATA_FREQ = 5000  # ms
    INFO_FREQ = 60  # s

    def __init__(
        self,
        camera,
        *args,
        sensor=None,
        compressor=None,
        framerate=None,
        duration=math.inf,
        maxframes=math.inf,
        verbose=False,
        encoder="libx264",
        crf="18",
        preview=False,
        idx=0,
        **kwargs
    ):
        """
        Initialize a recorder with framerate equal to FPS of camera
        or alternatively provide a custom framerate
        """

        self._camera = camera
        if framerate is None:
            framerate = camera._framerate
        self._framerate = framerate
        self._framecount = 0
        self._duration = duration

        self._video_writer = None
        self._maxframes = maxframes
        self._compressor = compressor
        self._verbose = verbose
        self._stop_event = threading.Event()
        self._pipeline = []
        self._sensor = sensor

        # only for FFMPEGRecorder
        self._encoder = encoder
        self._crf = crf
        self._preview = preview
        self.idx = idx

        self.last_tick = 0
        super().__init__(*args, **kwargs)

    @property
    def camera(self):
        return self._camera

    @property
    def resolution(self):
        """Resolution in widthxheight pixels"""
        return self._camera.resolution

    def write(self, frame, framecount, timestamp):
        """
        Implemented in subclass or mixin
        """
        raise NotImplementedError

    def _info(self):
        raise NotImplementedError

    def save_extra_data(self, *args, **kwargs):
        return None

    def writeFrame(self, frame, timestamp):
        self.write(frame, self._framecount, timestamp)
        self._framecount += 1

    def run(self):
        """
        Collect frames from the camera and write them to the video
        Periodically log #frames saved
        """

        self._start_time = time.time()

        for timestamp, frame in self.camera:

            if self.should_stop:
                break

            if self._preview:
                cv2.imshow("Frame", frame)
                if cv2.waitKey(1) == ord("q"):
                    break

            self.save_extra_data(timestamp)
            self.writeFrame(frame, timestamp)
            if self._framecount % (self.INFO_FREQ) == 0 and self._verbose:
                self._info()

    @property
    def should_stop(self):

        duration_reached = self.running_for_seconds >= self._duration
        return (
            duration_reached
            or self.max_frames_reached
            or self._stop_event.is_set()
        )

    @property
    def running_for_seconds(self):
        return time.time() - self._start_time

    @property
    def max_frames_reached(self):
        return self._framecount >= self._maxframes

    def build_pipeline(self, *args):
        messg = "Defined pipeline:\n"
        for cls in args:
            self._pipeline.append(cls())
            messg += "%s\n" % cls.__name__

        print(messg)

    def pipeline(self, frame):
        if len(self._pipeline) == 0:
            return frame
        else:
            for step in self._pipeline:
                frame = step.apply(frame)
        return frame


class FFMPEGRecorder(FFMPEGMixin, BaseRecorder):
    @property
    def outputdict(self):
        return {
            "-r": str(self._framerate),
            "-crf": str(self._crf),
            "-vcodec": str(self._encoder),
        }

    @property
    def inputdict(self):
        return {"-t": str(self._duration)}


class ImgstoreRecorder(ImgstoreMixin, BaseRecorder):
    def __init__(self, *args, **kwargs):
        self._lost_frames = 0
        super().__init__(*args, **kwargs)


RECORDERS = {
    "FFMPEG": FFMPEGRecorder,
    "ImgStore": ImgstoreRecorder,
    "OpenCV": BaseRecorder,
}


def setup(args, camera, sensor, idx=0):

    RecorderClass = RECORDERS[args.recorder]

    recorder = RecorderClass(
        camera,
        framerate=int(camera.framerate),
        duration=args.duration,
        maxframes=args.maxframes,
        sensor=sensor,
        crf=args.crf,
        encoder=args.encoder,
        preview=args.preview,
        verbose=args.verbose,
        idx=idx,
    )

    return recorder


def run(recorder, **kwargs):

    kwargs.update(document_for_reproducibility(recorder))
    # print("Opening recorder")
    recorder.open(**kwargs)
    # print("Starting recorder")

    try:
        recorder.start()
        recorder.join()
    except KeyboardInterrupt:
        pass
    recorder.close()


def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser(conflict_handler="resolve")

    ap.add_argument(
        "--config",
        help="Config file in json format",
        default="/etc/flyhostel.conf",
    )
    ap.add_argument(
        "--output",
        default=datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        help="Path to output video (directory for ImgStore). It will be placed in the video folder as stated in the config file. See --config",
    )
    ap.add_argument(
        "--fps",
        type=int,
        help="Frames Per Second of the video",
        required=False,
    )
    ap.add_argument("--sensor", type=int, default=None)
    ap.add_argument("--duration", type=int, default=math.inf)
    ap.add_argument("--encoder", type=str)
    ap.add_argument("--fmt", type=str, default="mjpeg/avi")
    ap.add_argument("--crf", type=int)
    ap.add_argument(
        "--recorder", choices=list(RECORDERS.keys()), default="ImgStore"
    )
    ap.add_argument(
        "--verbose", choices=list(LEVELS.keys()), default="WARNING"
    )
    return ap
