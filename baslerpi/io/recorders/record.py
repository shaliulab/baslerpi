import sys
import queue
import argparse
import datetime
import math
import multiprocessing
import threading
import time
import logging

from baslerpi.io.recorders.mixins import (
    FFMPEGMixin,
    ImgStoreMixin,
)

from baslerpi.exceptions import ServiceExit

logger = logging.getLogger("baslerpi.io.record")

logger.setLevel(logging.INFO)


LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}


# class BaseRecorder(threading.Thread):
class BaseRecorder(multiprocessing.Process):
    """
    Take an iterable source object which returns (timestamp, frame)
    in every iteration and save to a path determined in the open() method
    """

    EXTRA_DATA_FREQ = 5  # s
    INFO_FREQ = 1  # s

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
        roi=None,
        stop_queue=None,
        **kwargs,
    ):
        """
        Initialize a recorder with framerate equal to FPS of source
        or alternatively provide a custom framerate
        """

        self._data_queue = source
        self._stop_queue = stop_queue

        self._n_passed_frames = 0
        self._framerate = framerate
        self._duration = duration

        if maxframes == 0:
            maxframes = math.inf
        self._maxframes = math.inf

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
        self._roi = roi
        self._start_time = None
        self._last_tick = 0
        self._last_update = 0
        self._async_writer = None

        super().__init__()
        self.daemon = True

    @property
    def all_queues_have_been_emptied(self):
        return self._data_queue.qsize() == self._stop_queue.qsize() == 0

    def clock(self):
        if self._start_time is None:
            return 0
        else:
            return time.time() - self._start_time

    @property
    def reads_from_queue(self):
        return self._data_queue.__class__.__name__ == "Queue"

    @property
    def framerate(self):
        if self.reads_from_queue:
            framerate = self._framerate
        else:
            framerate = self._data_queue.framerate

        self._framerate = framerate
        return framerate

    @property
    def imgshape(self):
        if self.reads_from_queue:
            imgshape = self._roi[3:1:-1]
        else:
            imgshape = self.resolution[3 : 1 - 1]

        self._imgshape = imgshape
        return imgshape

    @property
    def resolution(self):
        """Resolution in widthxheight pixels"""
        if self.reads_from_queue:
            resolution = self._resolution
        else:
            resolution = self._data_queue.resolution

        self._resolution = resolution
        return resolution

    @property
    def name(self):

        if self.reads_from_queue:
            name = self._data_queue.name
        else:
            name = self._data_queue.__str__()

        return name

    def write(self, frame, framecount, timestamp):
        """
        Implemented in subclass or mixin
        """
        raise NotImplementedError

    def report_info(self):
        raise NotImplementedError

    def save_extra_data(self, *args, **kwargs):
        return None

    def __str__(self):
        return f"Recorder {self.idx} on {self._data_queue.name} ({self._data_queue.qsize()}/{self._stop_queue.qsize()})"

    def report_cache_usage(self):
        return self._async_writer._report_cache_usage()

    def run(self):
        """
        Collect frames from the source and write them to the video
        Periodically log #frames saved
        """

        self._start_time = time.time()

        try:
            self._run()
        except ServiceExit:
            self._run()
        finally:
            self._async_writer._close()

            if self._data_queue.qsize() != 0:
                print(self, " has not terminated successfully")
                sys.exit(1)
            else:
                print(self, " has terminated successfully")
                return 0

    def _run(self):
        while self._async_writer._need_to_run():
            time.sleep(0.1)

        time.sleep(2)
        self._async_writer.start()

        while self._async_writer.is_alive():
            self.report_cache_usage()
            self.save_extra_data(self._async_writer.timestamp)
            time.sleep(0.1)
            if self.should_stop():
                time.sleep(3)
                if self.should_stop():
                    break

        self._async_writer._close()
        print("Waiting for async writer to finish")
        print(self._async_writer)
        self._async_writer.join()

    def _close_source(self):
        if not self.reads_from_queue:
            camera = self._data_queue
            camera.close()

    def should_stop(self):

        duration_reached = self.running_for_seconds >= self._duration
        result = (
            duration_reached
            or self.max_frames_reached
            or self._stop_event.is_set()
        )

        if result:
            print("SHOULD STOP!")

        return result

    @property
    def running_for_seconds(self):
        return time.time() - self._start_time

    @property
    def max_frames_reached(self):
        return self.n_saved_frames >= self._maxframes


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


class ImgStoreRecorder(ImgStoreMixin, BaseRecorder):
    def __init__(self, *args, **kwargs):
        self._lost_frames = 0
        super().__init__(*args, **kwargs)

    @property
    def buffered_frames(self):
        self._check_data_queue_is_busy()
        return self._cache_size


RECORDERS = {
    "FFMPEGRecorder": FFMPEGRecorder,
    "ImgStoreRecorder": ImgStoreRecorder,
    "OpenCVRecorder": BaseRecorder,
}


def setup(args, recorder_name, source, sensor=None, idx=0, **kwargs):

    RecorderClass = RECORDERS[recorder_name]

    framerate = getattr(args, "framerate", kwargs.pop("framerate", 30))
    maxframes = getattr(args, "maxframes", 0)
    preview = getattr(args, "preview", False)

    recorder = RecorderClass(
        source,
        framerate=framerate,
        duration=args.duration,
        maxframes=maxframes,
        sensor=sensor,
        crf=args.crf,
        encoder=args.encoder,
        preview=preview,
        verbose=args.verbose,
        idx=idx,
        **kwargs,
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
        default="ImgStoreRecorder",
    )
    ap.add_argument(
        "--verbose", choices=list(LEVELS.keys()), default="WARNING"
    )
    return ap


def main(args=None):

    output = "trash.avi"

    import numpy as np

    if args is None:
        ap = get_parser()
        args = ap.parse_args()

    data_queue = multiprocessing.Queue(maxsize=0)
    stop_queue = multiprocessing.Queue(maxsize=1)
    for i in range(10):
        data_queue.put(
            (time.time(), np.uint8(np.random.randint(0, 255, (100, 100))))
        )

    recorder = setup(
        args,
        recorder_name="ImgStoreRecorder",
        source=data_queue,
        stop_queue=stop_queue,
        roi=(0, 0, 100, 100),
        resolution=(100, 100),
        framerate=30,
    )
    recorder.open(path=output, fmt=args.fmt)
    recorder.start()
    time.sleep(1)
    print("Started")
    while not data_queue.empty():
        print(data_queue.qsize())
        if (time.time() - recorder._start_time) > 3:
            print(data_queue.get())

    recorder.close()
    print("Done")
    print(data_queue.qsize())
    print(stop_queue.qsize())
    # recorder.join()
    # recorder.terminate()
    import sys

    sys.exit(0)


if __name__ == "__main__":
    main()
