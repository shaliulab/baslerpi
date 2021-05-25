# Standard library
import logging
import os
import os.path
import time
import traceback
import math

# Optional modules
from pypylon import pylon
import cv2

# Local library
from baslerpi.decorators import drive_basler
from baslerpi.io.cameras.cameras import BaseCamera
from baslerpi.io.cameras.dlc_camera import Camera as DLCCamera

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

class BaslerCamera(BaseCamera):

    _max_failed_count = 5

    r"""
    Drive a Basler camera using pypylon.

    Methods:

    _open():        Turn on the camera. Called by the __init__ method of abstract class
    _next_image(): Fetch next frame. Called by the __iter__ method of abstract class
    close():       Close the camera
    """

    def __init__(self, *args, init_now=True, **kwargs):     
        if init_now:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        super().__init__(*args, **kwargs)

    def is_last_frame(self):
        # TODO
        return False

    def is_open(self):
        """
        Return True if camera is opened
        """
        return self.camera.IsOpen()

    def configure(self):
        self.exposuretime = self._target_exposuretime
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        time.sleep(1)
        self.framerate = self._target_framerate
        self._report()

    def open(self, maxframes=None, buffersize=5):
        """
        Detect a Basler camera using pylon
        Assign it to the camera slot and try to open it
        Try to fetch a frame
        """
        try:

            self.camera.Open()
            self.configure()
            # Print the model name of the camera.
            logger.info("Using device %s", self.camera.GetDeviceInfo().GetModelName())

            if maxframes is None:
                pass
            else:
                self.camera.StartGrabbingMax(maxframes) # if we want to limit the number of frames

            self.camera.MaxNumBuffer = buffersize
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            grabResult = self.camera.RetrieveResult(self._timeout, pylon.TimeoutHandling_ThrowException)
            image = grabResult.Array

            logger.info("Pylon camera opened successfully")
            self._start_time = time.time()
            logger.info("Resolution of incoming frames: %dx%d", image.shape[1], image.shape[0])
            self.configure()

        except Exception as error:
            logger.error("Cannot open camera. See error trace below")
            logger.error(error)
            logger.warning(traceback.print_exc())

        return True


    def _next_image(self):
        """
        Try to get the next frame
        up to _max_failed_count times in a row
        Return a np.array of the image
        """
        failed_count = 0
        # this while loop is designed to try several times,
        # not to be run continuosly
        # i.e. in normal conditions, it should be broken every time
        # the continously running loop is implemented BaseCamera.__iter__

        while self.camera.IsGrabbing() and failed_count < self._max_failed_count:

            grabResult = None

            # logger.warning('Input framerate is %s', str(self.framerate))
            try:
                grabResult = self.camera.RetrieveResult(self._timeout, pylon.TimeoutHandling_ThrowException)
                status = grabResult.GrabSucceeded()

            except KeyboardInterrupt:
                return 0

            except Exception as error:
                logger.error(error)
                logger.warning(traceback.print_exc())
                failed_count += 1
                status = False

            if status:
                #image = self._converter.Convert(grabResult)
                #img = image.GetArray()
                img = grabResult.Array
                grabResult.Release()
                return img

            else:
                failed_count += 1
                logger.debug("Pylon could not fetch next frame. Trial no %d", failed_count)
                if grabResult:
                    grabResult.Release()


        if failed_count >= self._max_failed_count:
            message = f"Tried reading next frame {self._max_failed_count} times and none worked. Exiting."
            logger.warning(message)
            self.close()


    # called by BaseCamera.__exit__()
    def close(self):
        self.stopped = True
        self.camera.Close()

#    @property
#    @drive_basler
#    def resolution(self):
#        r"""
#        Convenience function to return resolution of camera.
#        Resolution = (number_horizontal_pixels, number_vertical_pixels)
#        """
#        self._resolution = (self.camera.Width.GetValue(), self.camera.Height.GetValue())
#        return self._resolution

    @property
    @drive_basler
    def shape(self):
        r"""
        Convenience function to return shape of camera
        Shape = (number_vertical_pixels, number_horizontal_pixels, number_channels)
        """
        # TODO Return number of channels!
        return (self.camera.Height.GetValue(), self.camera.Width.GetValue(), 1)


    @property
    def framerate(self):
        return self._framerate

    @framerate.getter
    @drive_basler
    def framerate(self):
        self._framerate = float(self.camera.AcquisitionFrameRate.GetValue())
        return self._framerate

    @framerate.setter
    @drive_basler
    def framerate(self, framerate):
        # logger.info("Setting framerate to %s", str(framerate))
        try:
            self.camera.AcquisitionFrameRate.SetValue(framerate)
            self._framerate = framerate
        except Exception as error:
            logger.warning("Error in framerate setter")
            logger.warning(error)
            logger.debug(traceback.print_exc())


    @property
    @drive_basler
    def exposuretime(self):
        return self._exposuretime


    @exposuretime.getter
    @drive_basler
    def exposuretime(self):
        float(self.camera.ExposureTime.GetValue())
        return self._exposuretime

    @exposuretime.setter
    @drive_basler
    def exposuretime(self, exposuretime):
        try:
            self.camera.ExposureTime.SetValue(exposuretime)
            self._exposuretime = exposuretime
            logger.info("Setting exposure time to %3.f", exposuretime)

        except Exception as error:
            logger.warning(error)
            logger.debug(traceback.print_exc())
            logger.warning("Error in exposuretime setter")


class BaslerCameraDLC(BaslerCamera, DLCCamera):
    """
    A clone of BaslerCamera where its arguments are explicit and not inherited from abstract classes
    """

    def __init__(self, *args, id=0, resolution="2592x1944", exposure=15000, gain=0,rotate=0, crop=None, fps=None, use_tk_display=False, display_resize=1.0,
            drop_each=1, max_duration=None, use_wall_clock=True, timeout=5000, count=math.inf, wait_timeout=3000, annotator=None, **kwargs):

        print("Loading camera...")

        resolution = resolution.split("x")

        DLCCamera.__init__(self, id, resolution=resolution, exposure=exposure, gain=gain, rotate=rotate, crop=crop, fps=fps, use_tk_display=use_tk_display, display_resize=display_resize)

        # this bypasses the __init__ method of BaslerCamera
        # de facto making the BaslerCamera part a composition, not an inheritance
        super(BaslerCamera, self).__init__(
            *args, drop_each=drop_each, max_duration=max_duration, use_wall_clock=use_wall_clock, timeout=timeout, count=count,
            wait_timeout=wait_timeout, **kwargs
        )


class BaslerCameraDLCCompatibility(BaslerCameraDLC):

    def __init__(self, *args, **kwargs):

        if "framerate" in kwargs:
            kwargs["fps"] = int(kwargs.pop("framerate") or 30)

        if "height" in kwargs and "width" in kwargs:
            kwargs["resolution"] = "x".join([str(kwargs.pop("width") or 2592), str(kwargs.pop("height" or 1944))])

        if "shutter" in kwargs:
            kwargs["exposure"] = int(kwargs.pop("shutter", 15000))


        if "iso" in kwargs:
            kwargs["gain"] = int(kwargs.pop("iso") or 0)
        
        #
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        
        super().__init__(*args, **kwargs)

    def __getstate__(self):
        d=self.__dict__
        attrs = dict(d)
        camera=attrs.pop("camera", None)
        return attrs

    def __setstate__(self, d):
        self.__dict__ = d

    def configure(self):
        super().configure()
        return True

    def set_capture_device(self):
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        return self.open()

    def close_capture_device(self):
        return self.close()

    @staticmethod
    def arg_restrictions():
        arg_restrictions = {"use_wall_clock": [True, False]}
        return arg_restrictions

    def get_image(self):
        frame = self._next_image()
        if self.crop is not None:
            frame = frame[self.crop[2]:self.crop[3], self.crop[0]:self.crop[1]]

        if len(frame.shape) == 2 or frame.shape[2] == 1:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        return frame


if __name__ == "__main__":

    camera = BaslerCamera()
    camera.open()
    i = 0
    for t, img in camera:
        print("Resolution of incoming frames")
        print(img.shape[::-1])
        print("Timestamp")
        print(t)
        i += 1
        if i == 5:
            break

    camera.close()



