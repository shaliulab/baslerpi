import math
import threading
import time
import logging
import tqdm
import numpy as np

from baslerpi.io.recorders.mixins import (
    OpenCVMixin,
    FFMPEGMixin,
    ImgstoreMixin,
)
from baslerpi.web_utils.sensor import QuerySensor

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

logger.info("Loading recorder... ")

from baslerpi.io.cameras import BaslerCamera


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
        duration=300,
        maxframes=math.inf,
        verbose=False,
        encoder="libx264",
        crf="18",
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

    def writeFrame(frame, timestamp):
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


def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser()

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
    gp = ap.add_mutually_exclusive_group()
    gp.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Camera fetches this amount of frames at max",
    )
    gp.add_argument(
        "--maxframes",
        type=int,
        default=math.inf,
        help="Camera fetches frames (s)",
    )
    ap.add_argument("--encoder", type=str)
    ap.add_argument("--crf", type=int)
    ap.add_argument(
        "--recorder", choices=list(RECORDERS.keys()), default="ImgStore"
    )
    ap.add_argument(
        "--verbose", dest="verbose", action="store_true", default=False
    )
    return ap


def setup_sensor(args):
    if args.sensor is None:
        sensor = None
    else:
        sensor = QuerySensor(args.sensor)
    return sensor


def setup_recorder(args):

    RecorderClass = RECORDERS[args.recorder]
    sensor = setup_sensor(args)

    recorder = RecorderClass(
        camera,
        framerate=args.fps,
        duration=args.duration,
        maxframes=args.maxframes,
        sensor=sensor,
        crf=args.crf,
        encoder=args.encoder,
        verbose=args.verbose,
    )

    return recorder


def main(args=None, ap=None):

    if args is None:
        ap = get_parser(ap)
        args = ap.parse_args()

    output = args.output

    recorder = setup_recorder(args)
    recorder.open(path=output)
    recorder.start()
    recorder.join()
    recorder.close()


if __name__ == "__main__":
    main()
