import logging
import time

import numpy as np

from .cameras import BaseCamera

logger = logging.getLogger(__name__)


class EmulatorCamera(BaseCamera):
    """
    A class to yield random RGB images
    """

    def open(self):
        self._start_time = time.time()
        logger.debug("Opening emulator camera")

    def close(self):
        logger.debug("Closing emulator camera")

    def _load_message(self):
        pass

    def is_open(self):
        return True

    def _next_image(self):
        time.sleep(1 / self._target_framerate)

    def is_last_frame(self):
        return False


class RandomCamera(EmulatorCamera):
    def _next_image(self):
        logger.debug("Generating new frame")
        super()._next_image()
        frame = np.random.randint(
            0, 255, (self._height, self._width), dtype=np.uint8
        )
        return frame


class DeterministicCamera(EmulatorCamera):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._frame = np.random.randint(
            0, 255, (self._height, self._width), dtype=np.uint8
        )

    def _next_image(self):
        logger.debug("Generating new frame")
        super()._next_image()
        return self._frame
