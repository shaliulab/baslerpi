import logging
import os.path
import time
import traceback

import cv2

# Local library
from baslerpi.decorators import drive_basler
from baslerpi.io.cameras.cameras import BaseCamera

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

logger.info("Loading... ")

class OpenCVCamera(BaseCamera):

    def __init__(self, *args, video_path=None, wrap=False, greyworld=True, **kwargs):

        self._wrap = wrap
        self._time_s = 0
        self._wrap_s = 0

        if video_path is None or not os.path.isfile(video_path):
            self._video_path = 0 # capture from a webcam
        else:
            self._video_path = video_path

        self._greyworld = greyworld

        super().__init__(*args, **kwargs)


    def is_last_frame(self):
        return False

    def _time_stamp(self):

        if self._video_path == 0 or self._use_wall_clock:
            now = time.time()
            self._time_s = now - self._start_time
        else:
            self._time_s = self.camera.get(cv2.CAP_PROP_POS_MSEC) / 1000

        # add wrap_s if it's running in wrap mode
        # wrap_s will be n x the number of seconds of the video
        # where n is the number of times it's already been looped over
        return self._time_s + self._wrap_s

    def is_opened(self):
        return self.camera.isOpened()

    def _next_image(self):
        ret, img = self.camera.read()
        # logger.debug("FPS of input is %s", str(self.camera.get(cv2.CAP_PROP_FPS)))
        if self._wrap and not ret:
            self._wrap_s += self._time_s
            logger.info("Rewinding video to the start")
            self.camera.set(cv2.CAP_PROP_POS_MSEC, 0)
            ret, img = self.camera.read()

        #self._validate(img)
        return img

    def open(self):
        try:
            logger.debug('OpenCV camera opening')
            self.camera = cv2.VideoCapture(self._video_path)
        except Exception as error:
            logger.error(error)
            logger.error(traceback.print_exc())
            self.reset()

    def close(self):
        logger.info("Quitting camera...")
        self.camera.release()

    def restart(self):
        self.close()
        self.open()

    @property
    def framerate(self):
        return self._framerate

    @framerate.getter
    def framerate(self):
        # self._settings["framerate"] = self.camera.get(5)
        return self._framerate

    @framerate.setter
    def framerate(self, framerate):
        # logger.debug("Setting framerate %d" % framerate)
        self.camera.set(5, framerate)
        self._framerate = framerate

    @property
    def resolution(self):
        return self._resolution

    @resolution.getter
    def resolution(self):
        # TODO Is int needed here?
        self._resolution = (int(self.camera.get(3)), int(self.camera.get(4)))
        return self._resolution


    @resolution.setter
    def resolution(self, resolution):
        # TODO Is int needed here?
        self._resolution = resolution
        pass
        # self.camera.set(3, resolution[0])
        # self.camera.set(4, resolution[1])

    @property
    def exposuretime(self):
        return self._exposuretime

    @exposuretime.setter
    def exposuretime(self, exposuretime):
        self.camera.set(cv2.CAP_PROP_EXPOSURE, exposuretime)
        self._exposuretime = exposuretime

    @exposuretime.getter
    def exposuretime(self):
        exposuretime = self.camera.get(cv2.CAP_PROP_EXPOSURE)
        self._exposuretime = exposuretime
        return self._exposuretime

    @property
    def shape(self):
        return int(self.camera.get(4)), int(self.camera.get(3))


if __name__ == "__main__":
    import ipdb; ipdb.set_trace()
