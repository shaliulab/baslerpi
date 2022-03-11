__author__ = "antonio"

import time
from abc import abstractmethod
from baslerpi.io.cameras.plugins import ROISMixin, CameraUtils

class BaseCamera(ROISMixin, CameraUtils):
    def __init__(
        self,
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
        is_open()
        is_last_frame()

        Derived classes can define
        restart



        :param drop_each: keep only ``1/drop_each``'th frame
        :param args: additional arguments
        :param kwargs: additional keyword arguments
        """

        self.idx = idx

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
        
        self.start_time = time.time()
        self.stopped = False


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
        """
        Restarts a camera (also resets time).
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    def is_last_frame(self):
        raise NotImplementedError
   

    @abstractmethod
    def _next_image(self):
        raise NotImplementedError

    @property
    def computed_framerate(self):
        return self._frames_this_second


    @property
    def resolution(self):
        r"""
        Convenience function to return resolution of camera.
        Resolution = (number_horizontal_pixels, number_vertical_pixels)
        """
        return (self.width,
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


    @property
    def rois(self):
        if self._rois is None:
            try:
                return [(0, 0, *self.resolution)]
            except:
                raise Exception(
                    "Please open the camera before asking for its resolution"
                )
        else:
            return self._rois


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

        :return: the time (in ms) and a frame (numpy array).
        :rtype: (int, :class:`~numpy.ndarray`)
        """
        at_least_one_frame = False
          

        try:
            while not self.stopped:
                if self.is_last_frame():
                    if not at_least_one_frame:
                        raise Exception(
                            "Camera could not read the first frame"
                        )
                    break

                time_s, out = self._next_time_image()

                if out is None:
                    break

                t_ms = int(1000 * time_s)
                at_least_one_frame = True

                yield t_ms, out

        except KeyboardInterrupt:
            self.close()


class CV2Compatible(BaseCamera):

    def read(self):
        return self._next_image()

    def release(self):
        return self.close()

    def set(self, key, value):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError
