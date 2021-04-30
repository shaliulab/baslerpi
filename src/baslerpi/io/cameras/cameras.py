__author__ = 'antonio'

import logging
import logging.config
import time
logger = logging.getLogger(__name__)

from baslerpi.utils import read_config_yaml

#config = read_config_yaml("scripts/logging.yaml")
#logging.config.dictConfig(config)

# Tell pylint everything here is abstract classes
# pylint: disable=W0223


class BaseCamera:

    def __init__(self, width=1280, height=960, drop_each=1, colfx="128:128", max_duration=None,
        use_wall_clock=True, framerate=30, shutter=15000, iso=None, timeout=5000, wait_timeout=30000
    ):
        """
        The template class to generate and use video streams.
        Inspired by the Ethoscope project.


        Define:
        __iter__: Make the class interable by calling _next_time_image in a smart way
        __exit__: Calls the close method of derived classes
        _next_time_image

        Derived classes must define

        open()
        close()
        _load_message()
        _next_image()
        is_opened()
        is_last_frame()

        Derived classes can define
        restart



        :param drop_each: keep only ``1/drop_each``'th frame
        :param max_duration: stop the video stream if ``t > max_duration`` (in seconds).
        :param args: additional arguments
        :param kwargs: additional keyword arguments
        """

        self._max_duration = max_duration
        self.stopped = False
        self._frame_idx = 0
        self._shape = (None, None)
        self._use_wall_clock = use_wall_clock
        self._start_time = None
        self._framerate = framerate
        self._exposuretime = shutter
        self._drop_each = drop_each
        self._timeout = wait_timeout
        self._recording_timeout = timeout


    def time_stamp(self):
        if self._start_time is None:
            return 0
        else:
            now = time.time()
            return now - self._start_time

    def __exit__(self): # pylint: disable=unexpected-special-method-signature
        logger.info("Closing camera")
        self.close()

    def __str__(self):
        template = '%s running %s FPS, ET %s ms'
        return template % (
            self.__class__.__name__,
            str(self.framerate).zfill(4),
            str(self.exposuretime).zfill(8)
        )

    # def __getattr__(self, key):

    #     if key in self._settings.keys():
    #         return self._settings[key]
    #     elif hasattr(self, key):
    #         return getattr(self, key)
    #     else:
    #         logger.warning("Attribute %s not found", key)

    # def __setattr__(self, key, value):
    #     if key in self._settings.keys():
    #         self._settings[key] = value
    #     elif hasattr(self, key):
    #         setattr(self, key, value)
    #     else:
    #         logger.warning("Attribute %s not found", key)

    def __iter__(self):
        """
        Iterate thought consecutive frames of this camera.

        :return: the time (in ms) and a frame (numpy array).
        :rtype: (int, :class:`~numpy.ndarray`)
        """
        at_least_one_frame = False
        while not self.stopped:
            if self.is_last_frame() or not self.is_opened():
                if not at_least_one_frame:
                    raise Exception("Camera could not read the first frame")
                break
            time_s, out = self._next_time_image()
            if out is None:
                break
            t_ms = int(1000 * time_s)
            at_least_one_frame = True

            if (self._frame_idx % self._drop_each) == 0:
                logger.debug("Yielding frame")
                logger.debug("Time: %s, Framerate: %s", t_ms, self.framerate)
                yield t_ms, out

            if (self._recording_timeout is not None and self._recording_timeout != 0) and t_ms > self._recording_timeout:
                logger.debug(f"Timeout ({self._recording_timeout}) ms reached. Terminating camera...")
                break

    def _next_time_image(self):
        timestamp = self.time_stamp()
        image = self._next_image()
        self._frame_idx += 1
        return timestamp, image

    def _load_message(self):
        print(f"Initialized {self.__class__.__name__}")
        self._report()

    def _report(self):
        print(f"Framerate = {self.framerate}")
        print(f"Exposure time = {self.exposuretime}")

    def is_last_frame(self):
        raise NotImplementedError

    def _next_image(self):
        raise NotImplementedError

    def is_opened(self):
        raise NotImplementedError

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def restart(self):
        """
        Restarts a camera (also resets time).
        :return:
        """
        raise NotImplementedError
