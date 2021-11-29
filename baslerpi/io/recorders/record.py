import argparse
import datetime
import math
import multiprocessing
import threading
import time
import logging

from baslerpi.io.recorders.mixins import (
    FFMPEGMixin,
    ImgstoreMixin,
)

logger = logging.getLogger("baslerpi.io.record")
LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}


class BaseRecorder(multiprocessing.Process):
    """
    Take an iterable source object which returns (timestamp, frame)
    in every iteration and save to a path determined in the open() method
    """

    EXTRA_DATA_FREQ = 5000  # ms
    INFO_FREQ = 60  # s

    def __init__(
        self,
        source,
        *args,
        sensor=None,
        compressor=None,
        framerate=None,
        resolution=None,
        duration=math.inf,
        maxframes=math.inf,
        verbose=False,
        encoder="libx264",
        crf="18",
        preview=False,
        idx=0,
        **kwargs,
    ):
        """
        Initialize a recorder with framerate equal to FPS of source
        or alternatively provide a custom framerate
        """

        self._source = source

        self._framecount = 0
        self._framerate = framerate
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
        self._resolution = resolution

        self.last_tick = 0
        
        super().__init__(*args, **kwargs)

    
    @property
    def source(self):
        return self._source

    
    @property
    def framerate(self):
        if isinstance(self.source, multiprocessing.Queue):
            framerate = self._framerate
        else:
            framerate = self.source.framerate

        self._framerate = framerate
        return framerate
    
    
    @property
    def imgshape(self):
        if isinstance(self.source, multiprocessing.Queue):
            imgshape = self.resolution[3:1-1]
        else:
            data = self.source.get()
            if len(data) == 1 and data == "STOP":
                self.close()
            else:
                timestamp, frame = data
                imgshape = frame.shape

        
        self._imgshape = imgshape
        return imgshape


    @property
    def resolution(self):
        """Resolution in widthxheight pixels"""
        if isinstance(self.source, multiprocessing.Queue):
            resolution = self._resolution
        else:
            resolution = self.source.resolution
        
        self._resolution = resolution
        return resolution

    def write(self, frame, framecount, timestamp):
        """
        Implemented in subclass or mixin
        """
        raise NotImplementedError

    def report_info(self):
        raise NotImplementedError

    def save_extra_data(self, *args, **kwargs):
        return None

    def writeFrame(self, frame, timestamp):
        self.write(frame, self._framecount, timestamp)
        self._framecount += 1

    def __str__(self):
        return f"Recorder {self.idx} on {self.source}"

    # def run_preview(self, frame):

    #     if self._preview:
    #         cv2.imshow(f"Feed from {self}", frame)
    #         if cv2.waitKey(1) == ord("q"):
    #             return "quit"
    #         else:
    #             return

    def run(self):
        """
        Collect frames from the source and write them to the video
        Periodically log #frames saved
        """

        self._start_time = time.time()

        if isinstance(self.source, multiprocessing.Queue):
            self.run_queue(self.source)
        else:
            self.run_camera(self.source)

    def run_queue(self, queue):

        while not queue.empty():
            
            data = queue.get()
            if len(data) == 1 and data == "STOP":
                break
            else:
                timestamp, frame = data
                status = self._run(timestamp, frame)
                if status == "STOP":
                    break


    def run_camera(self, camera):

        for timestamp, frame in camera:
            status = self._run(timestamp, frame)
            if status == "STOP":
                    break


    def _run(self, timestamp, frame):

        if self.should_stop:
            return "STOP"

        # answer = self.run_preview(frame)

        self.save_extra_data(timestamp)
        self.writeFrame(frame, timestamp)
        self.report_info()
        # return answer


    def close_source(self):
        if isinstance(self.source, multiprocessing.Queue):
            self.source.put("STOP")
        else:
            self.source.close()


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
    "OpenCV": BaseRecorder
}


def setup(args, source, sensor, idx=0):

    RecorderClass = RECORDERS[args.recorder]

    recorder = RecorderClass(
        source,
        framerate=int(source.framerate),
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
        "--recorder",
        choices=list(RECORDERS.keys()),
        default="MultiImgstoreRecorder",
    )
    ap.add_argument(
        "--verbose", choices=list(LEVELS.keys()), default="WARNING"
    )
    return ap
