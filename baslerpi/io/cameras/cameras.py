__author__ = "antonio"

import logging
import logging.config
import time
import math

logger = logging.getLogger(__name__)

from baslerpi.utils import read_config_yaml

# config = read_config_yaml("scripts/logging.yaml")
# logging.config.dictConfig(config)

# Tell pylint everything here is abstract classes
# pylint: disable=W0223


class BaseCamera:
    def __init__(
        self,
        width=1280,
        height=960,
        framerate=30,
        exposure=15000,
        iso=0,
        drop_each=1,
        use_wall_clock=False,
        timeout=30000,
        preview=False,
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
        is_open()
        is_last_frame()

        Derived classes can define
        restart



        :param drop_each: keep only ``1/drop_each``'th frame
        :param args: additional arguments
        :param kwargs: additional keyword arguments
        """

        self._width = width
        self._height = height
        self._iso = iso
        self.stopped = False
        self._frame_idx = 0
        self._shape = (None, None)
        self._use_wall_clock = use_wall_clock
        self._start_time = None
        self._target_framerate = framerate
        self._computed_framerate = 0
        self._framerate = 0
        self._target_exposuretime = exposure
        self._exposuretime = 0
        self._drop_each = drop_each
        self._timeout = timeout
        self._count = 0
        self._preview = preview
        self.failed_count = 0

    def time_stamp(self):
        if self._start_time is None:
            return 0
        elif self._use_wall_clock:
            return time.time()
        else:
            now = time.time()
            return now - self._start_time

    def __exit__(self):  # pylint: disable=unexpected-special-method-signature
        logger.info("Closing camera")
        self.close()

    def __str__(self):
        template = "%s: %s FPS, ET %s ms (target %s FPS, %s ms)"
        return template % (
            self.__class__.__name__,
            str(self._framerate).zfill(4),
            str(self._exposuretime).zfill(8),
            str(self._target_framerate).zfill(4),
            str(self._target_exposuretime).zfill(8),
        )

    def __iter__(self):
        """
        Iterate thought consecutive frames of this camera.

        :return: the time (in ms) and a frame (numpy array).
        :rtype: (int, :class:`~numpy.ndarray`)
        """
        at_least_one_frame = False

        while not self.stopped:
            if self.is_last_frame() or not self.is_open():
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
                self._count += 1
                yield t_ms, out

    @property
    def computed_framerate(self):
        return self._computed_framerate

    def _next_time_image(self):
        timestamp = self.time_stamp()
        image = self._next_image()
        self._frame_idx += 1
        return timestamp, image

    def _load_message(self):
        print(f"Initialized {self.__class__.__name__}")
        self._report()

    def report(self):
        logger.debug(f"Actual framerate = {self.framerate}")
        logger.debug(f"Actual exposure time = {self.exposuretime}")

    def is_last_frame(self):
        raise NotImplementedError

    def _next_image(self):
        raise NotImplementedError

    def is_open(self):
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


class ExtendableBaseCamera(BaseCamera):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
