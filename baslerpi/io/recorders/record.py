import math
import threading
import time
import logging
import tqdm
import numpy as np

from .mixins import OpenCVMixin, FFMPEGMixin, ImgstoreMixin

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

    def __init__(self, camera, *args, sensor=None, compressor=None, framerate=None, duration=300, maxframes=math.inf, verbose=False, **kwargs):
        """
        Initialize a recorder with framerate equal to FPS of camera
        or alternatively provide a custom framerate
        """

        self._camera = camera
        if framerate is None:
            framerate = camera._framerate
            print(framerate)
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
        super().__init__(*args, **kwargs)

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

    def add_extra_data(self, *args, **kwargs):
        return None

    def run(self):
        """
        Collect frames from the camera and write them to the video
        Periodically log #frames saved
        """

        self._start_time = time.time()
        last_tick = 0


        for timestamp, frame in self._camera:

            if not self._sensor is None and timestamp > (last_tick + 5000):
                environmental_data = self._sensor.query(timeout=1)
                if not environmental_data is None:
                    self.add_extra_data(
                            temperature=environmental_data["temperature"],
                            humidity=environmental_data["humidity"],
                            light=environmental_data["light"],
                            time=timestamp
                    )
                last_tick = timestamp

            else:
                self.add_extra_data(
                        temperature=np.nan,
                        humidity=np.nan,
                        light=np.nan,
                        time=timestamp
                )


            if self._stop_event.is_set():
                break

            self.write(frame, self._framecount, timestamp)

            self._framecount += 1


            if self._framecount % (1*60) == 0 and self._verbose:
                #logger.info("Saved %d frames", self._framecount)
                self._info()

            running_for_seconds = time.time() - self._start_time

            if self._duration < running_for_seconds:
                break

            if self._framecount == self._maxframes or self._stop_event.is_set():
                break

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

    def __init__(self, *args, encoder="libx264", crf="18", **kwargs):

        self._encoder = encoder
        self._crf = crf
        super().__init__(*args, **kwargs)

    @property
    def outputdict(self):
        return {
            "-r": str(self._framerate),
            "-crf": str(self._crf),
            "-vcodec": str(self._encoder)
        }

    @property
    def inputdict(self):
        return {
           "-t": str(self._duration)
        }

class ImgstoreRecorder(ImgstoreMixin, BaseRecorder):
    def __init__(self, *args, **kwargs):
        self._lost_frames = 0
        super().__init__(*args, **kwargs)

if __name__ == "__main__":

    import argparse
    import datetime
    import os.path

    ap = argparse.ArgumentParser()

    ap.add_argument("--output-dir", type=str, default="/1TB/Cloud/Lab/Projects/FlyBowl/videos")
    ap.add_argument("--duration", type=int, help = "(s)")
    ap.add_argument("--encoder", type=str)
    ap.add_argument("--crf", type=int)

    args = vars(ap.parse_args())

    output_dir = args["output_dir"]
    crf = args["crf"]
    encoder = args["encoder"]
    duration = args["duration"]

    recorder_kwargs = {k: args[k] for k in args.keys() if k in ["duration", "encoder", "crf"] and args[k] is not None}
    print(recorder_kwargs)

    filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    print(filename)

    camera = BaslerCamera(framerate=30)
    camera.open()
    print(camera)
    recorder = FFMPEGRecorder(camera, **recorder_kwargs)
    recorder.open(
        path = os.path.join(output_dir, f"{filename}.avi")
    )
    try:
        recorder.start()
        recorder.join()
    except KeyboardInterrupt:
        recorder._stop_event.set()
        logger.info("Quitting...")

    recorder.close()
    camera.close()

