# Standard library
import logging
import os
import os.path
import time
import traceback

# Optional modules
from pypylon import pylon

# Local library
from baslerpi.decorators import drive_basler
from baslerpi.io.cameras.cameras import BaseCamera

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

    def __init__(self, *args, **kwargs):
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
        time.sleep(1)
        self._report()

    def set_capture_device(self):
        return self.configure()

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
            self._report()

        except Exception as error:
            logger.error("Cannot open camera. See error trace below")
            logger.error(error)
            logger.warning(traceback.print_exc())


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

    @property
    @drive_basler
    def resolution(self):
        r"""
        Convenience function to return resolution of camera.
        Resolution = (number_horizontal_pixels, number_vertical_pixels)
        """
        self._resolution = (self.camera.Width.GetValue(), self.camera.Height.GetValue())
        return self._resolution

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

