__author__ = "antonio"

import time
import logging
from abc import abstractmethod
from baslerpi.io.cameras.plugins import ROISMixin, CameraUtils
from baslerpi.class_utils.time import TimeUtils

class AbstractCamera:
    def __init__(
        self,
        start_time=None,
        width=None,
        height=None,
        framerate=30,
        exposure=15000,
        iso=0,
        drop_each=1,
        use_wall_clock=False,
        timeout=30000,
        duration=None,
        resolution_decrease=1.0,
        rois=None,
        idx=0,
    ):
        """
        Abstract camera class template
        Inspired by the Ethoscope project.
        """


        self._target_width = width
        self._target_height = height
        self._target_exposure = exposure
        self._target_framerate = framerate
        self._target_iso = iso
        self._use_wall_clock = use_wall_clock
        self._drop_each = drop_each
        self._timeout = timeout
        self._duration = duration
        self._rois = rois
        self._time_s = None

        self._last_offset = 0
        self._frames_this_second = 0
        self._frame_idx = 0
        
        self.idx = idx
        self.start_time = start_time or time.time()
        self.stopped = False
        self.isColor = False

        if resolution_decrease != 1.0:
            logging.warning("Resolution decrease is not implemented. Ignoring")

    @property
    @abstractmethod
    def running_for_seconds(self):
        raise NotImplementedError


    @abstractmethod
    def is_open(self):
        raise NotImplementedError

    @abstractmethod
    def open(self):
        raise NotImplementedError

    @abstractmethod
    def close(self):
        raise NotImplementedError

    @abstractmethod
    def restart(self):
        raise NotImplementedError

    @abstractmethod
    def is_last_frame(self):
        raise NotImplementedError

    @abstractmethod
    def _next_image_default(self):
        raise NotImplementedError

    @abstractmethod
    def _next_image_rois(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def width(self):
        return NotImplementedError

    @property
    @abstractmethod
    def height(self):
        return NotImplementedError

    @property
    def computed_framerate(self):
        return self._frames_this_second


    @property
    def resolution(self):
        r"""
        Convenience function to return resolution of camera.
        Resolution = (number_horizontal_pixels, number_vertical_pixels)
        """
        return (
            self.width,
            self.height,
        )
        
    @property
    def shape(self):
        r"""
        Convenience function to return shape of camera
        Shape = (number_vertical_pixels, number_horizontal_pixels, number_channels)
        """
        
        if self.isColor:
            return (
                self.height,
                self.width,
                3
            )
        else:
            return (
                self.height,
                self.width
            )


    def is_last_frame(self):
        if self._duration is None:
            return False
        return self._duration < self.running_for_seconds
 

    def _next_image(self):
        # NOTE
        # Forcing here _next_image_rois() 
        if self._rois is None:# and False:
            return self._next_image_default()
        else:
            return self._next_image_rois()


    def _init_read(self):
        """
        Try reading a frame and check its resolution
        """
        status, img = self._next_image_default()

        if status and img is not None:

            logging.info(f"P{self} opened successfully")
            logging.info(
                "Resolution of incoming frames: %dx%d",
                img.shape[1],
                img.shape[0],
            )
        else:
            raise Exception("The initial grab did not work")


    def time_stamp(self):
        if self.start_time is None:
            return 0
        elif self._use_wall_clock:
            self._time_s = time.time()
        else:
            now = time.time()
            self._time_s = now - self.start_time

        return self._time_s

    def _next_time_image(self):
        timestamp = self.time_stamp()
        status, image = self._next_image()
        if image is not None:
            self._frame_idx += 1

        return timestamp, image

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):  
        self.close()
   
    def __iter__(self):
        """
        Iterate thought consecutive frames of this camera.

        Returns:
        
            * t_ms (int): time of the frame in ms
            * out (np.ndarray): frame
        """
        
        try:
            while not self.stopped:
                time_s, out = self._next_time_image()

                if out is None:
                    break

                t_ms = int(1000 * time_s)
                yield t_ms, out

        except KeyboardInterrupt:
            self.close()


class BaseCamera(AbstractCamera, TimeUtils, ROISMixin, CameraUtils):
    pass

class CV2Compatible(BaseCamera):
    """
    Make the camera behave like a cv2.VideoCapture object
    for 'duck-typing' compatibility
    """

    def read(self):
        return self._next_image()

    def release(self):
        return self.close()

    def set(self, key, value):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError
