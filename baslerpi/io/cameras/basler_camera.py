# Standard library
import argparse
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


logger = logging.getLogger("baslerpi.io.camera")


class BaslerCamera(BaseCamera):

    _MAX_FAILED_COUNT = 5

    r"""
    Drive a Basler camera using pypylon.

    Methods:

    _open():        Turn on the camera. Called by the __init__ method of abstract class
    _next_image(): Fetch next frame. Called by the __iter__ method of abstract class
    close():       Close the camera
    """

    def is_last_frame(self):
        # TODO
        return False

    def is_open(self):
        """
        Return True if camera is opened
        """
        return self.camera.IsOpen()

    def configure(self):
        """
        Set the exposure time and the framerate of the camera
        to the attributes of the class
        """
        self.exposuretime = self._target_exposuretime
        self.framerate = self._target_framerate

    def grab(self):

        grabResult = self.camera.RetrieveResult(
            self._timeout, pylon.TimeoutHandling_ThrowException
        )
        status = grabResult.GrabSucceeded()
        if status:
            img = grabResult.Array
            grabResult.Release()
        else:
            img = None
            self.failed_count += 1
            logger.debug(
                "Pylon could not fetch next frame. Trial no %d", failed_count
            )

        return status, img

    def open(self, maxframes=None, buffersize=5):
        """
        Detect a Basler camera using pylon
        Assign it to the camera slot and try to open it
        Try to fetch a frame
        """
        try:
            if not getattr(self, "camera", False):
                self.camera = pylon.InstantCamera(
                    pylon.TlFactory.GetInstance().CreateFirstDevice()
                )


            self.camera.Open()
            self.configure()
            self.report()

            # Print the model name of the camera.
            logger.info(
                "Using device %s", self.camera.GetDeviceInfo().GetModelName()
            )

            self.camera.MaxNumBuffer = buffersize

            if maxframes is not None:
                self.camera.StartGrabbingMax(
                    maxframes
                )  # if we want to limit the number of frames


            _, img = self.grab()
            logger.info("Pylon camera opened successfully")
            self._start_time = time.time()
            logger.info(
                "Resolution of incoming frames: %dx%d",
                img.shape[1],
                img.shape[0],
            )

        except Exception as error:
            logger.error("Cannot open camera. See error trace below")
            logger.error(error)
            logger.warning(traceback.print_exc())

        return True

    def _next_image(self):
        """
        Try to get the next frame
        up to _MAX_FAILED_COUNT times in a row
        Return a np.array of the image
        """
        failed_count = 0
        # this while loop is designed to try several times,
        # not to be run continuosly
        # i.e. in normal conditions, it should be broken every time
        # the continously running loop is implemented BaseCamera.__iter__
        while (
            self.camera.IsGrabbing()
            and self.failed_count < self._MAX_FAILED_COUNT
        ):

            grabResult = None

            # logger.warning('Input framerate is %s', str(self.framerate))
            try:
                status, img = self.grab()
                if status:
                    return img

                elif self.failed_count >= self._MAX_FAILED_COUNT:
                    message = f"Tried reading next frame {self._MAX_FAILED_COUNT} times and none worked. Exiting."
                    logger.warning(message)
                    return None

            except KeyboardInterrupt:
                return None

            except Exception as error:
                logger.error(error)
                logger.warning(traceback.print_exc())

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
        self._resolution = (
            self.camera.Width.GetValue(),
            self.camera.Height.GetValue(),
        )
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

        if not self.camera.AcquisitionFrameRateEnable.GetValue():
            self.camera.AcquisitionFrameRateEnable.SetValue(True)

        try:

            if not framerate is None:
                self.camera.AcquisitionFrameRate.SetValue(framerate)
                logger.info("Setting framerate to %3.f", framerate)

            self._framerate = float(
                self.camera.AcquisitionFrameRate.GetValue()
            )
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
        return self._exposuretime

    @exposuretime.setter
    @drive_basler
    def exposuretime(self, exposuretime):
        try:
            if not exposuretime is None:
                self.camera.ExposureTime.SetValue(exposuretime)
                logger.info("Setting exposure time to %3.f", exposuretime)
            self._exposuretime = float(self.camera.ExposureTime.GetValue())

        except Exception as error:
            logger.warning(error)
            logger.debug(traceback.print_exc())
            logger.warning("Error in exposuretime setter")


def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser()
        ap.add_argument(
            "--framerate",
            type=int,
            default=30,
            help="Frames Per Second of the camera",
        )
        ap.add_argument(
            "--exposure-time",
            dest="exposure",
            type=int,
            default=25000,
            help="Exposure time in useconds (10^-6 s)",
        )
    return ap


def get_dynamic_camera_kwargs(args):

    """
    DEPRECATED
    Filter the input args so only kwargs of the BaslerCamera class init
    or any of its parents are returned
    """

    keys = list(signature(BaslerCamera).parameters.keys())
    for cls in BaslerCamera.__bases__:
        keys = keys + list(signature(cls).parameters.keys())

    camera_kwargs = {k: getattr(args, k) for k in vars(args) if k in keys}
    return camera_kwargs


def setup_camera(args=None):

    camera_kwargs = {"framerate": args.framerate, "exposure": args.exposure}
    camera = BaslerCamera(**camera_kwargs)
    return camera


def setup_logger(level):
    logger = logging.getLogger("baslerpi.io.camera")
    logger.setLevel(level)
    console = logging.StreamHandler()
    console.setLevel(level)
    logger.addHandler(console)


def main(args=None, ap=None):
    """
    Initialize a BaslerCamera
    """

    LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}
    if args is None:
        ap = get_parser()
        ap.add_argument(
            "--maxframes", default=5, help="Number of frames to be acquired", type=int
        )
        ap.add_argument(
             "--verbose", choices=list(LEVELS.keys()), default="WARNING"
        )

        args = ap.parse_args()

        level = LEVELS[args.verbose]
        setup_logger(level=level)

    camera = setup_camera(args)
    camera.open(maxframes=getattr(args, "maxframes", 5))
    for timestamp, frame in camera:
        print(timestamp, frame.shape, frame.dtype, camera.computed_framerate)


if __name__ == "__main__":
    main()
