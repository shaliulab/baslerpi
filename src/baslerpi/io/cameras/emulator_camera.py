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

    def _next_image(self):

        frame = np.random.randint(0, 255, (self._height, self._width))
        return frame

    def is_opened(self):
        return True

    def is_last_frame(self):
        return False

