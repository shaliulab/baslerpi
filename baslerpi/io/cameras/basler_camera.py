# Standard library
import argparse
import logging
import os.path
import time
import traceback
import inspect
import math
import sys

# Optional modules
from pypylon import pylon
import cv2

# Local library
from baslerpi.decorators import drive_basler
from baslerpi.io.cameras.cameras import BaseCamera
from baslerpi.io.cameras.dlc_camera import Camera as DLCCamera


logger = logging.getLogger("baslerpi.io.camera")
LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}


class BaslerCamera(BaseCamera):

    _MAX_FAILED_COUNT = 5
    REVERSE_X = True
    REVERSE_Y = True

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
        self.camera.ReverseX.SetValue(self.REVERSE_X)
        self.camera.ReverseY.SetValue(self.REVERSE_Y)
        self.camera.Width.SetValue(self._width)
        self.camera.Height.SetValue(self._height)

    def grab(self):

        grabResult = self.camera.RetrieveResult(
            self._timeout, pylon.TimeoutHandling_ThrowException
        )
        status = grabResult.GrabSucceeded()
        if status:
            img = grabResult.Array
            grabResult.Release()
            if self._resolution_decrease not in [1, None]:
                img = cv2.resize(
                    img,
                    (
                        img.shape[1] // self._resolution_decrease,
                        img.shape[0] // self._resolution_decrease,
                    ),
                    cv2.INTER_AREA,
                )

        else:
            img = None
            self.failed_count += 1
            logger.debug(
                "Pylon could not fetch next frame. Trial no %d",
                self.failed_count,
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
                try:

                    self.camera = pylon.InstantCamera(
                        pylon.TlFactory.GetInstance().CreateFirstDevice()
                    )
                except Exception as error:
                    logger.error(error)
                    logger.error(traceback.print_exc())
                    sys.exit(1)

            self.camera.Open()
            self.configure()
            self.report()

            # Print the model name of the camera.
            logger.info(
                "Using device %s", self.camera.GetDeviceInfo().GetModelName()
            )

            self.camera.MaxNumBuffer = buffersize

            if maxframes is math.inf:
                maxframes = None

            if maxframes is not None:
                self.camera.StartGrabbingMax(
                    maxframes
                )  # if we want to limit the number of frames
            else:
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

            status, img = self.grab()

            if status and img is not None:

                logger.info("Basler camera opened successfully")
                self._start_time = time.time()
                logger.info(
                    "Resolution of incoming frames: %dx%d",
                    img.shape[1],
                    img.shape[0],
                )
            else:
                raise Exception("The initial grab() did not work")

        except Exception as error:
            logger.error("Cannot open camera. See error trace below")
            logger.error(error)
            logger.warning(traceback.print_exc())

        return True

    def _next_image_raw(self):
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
                time.sleep(1)
                if self.stopped:
                    return
                else:
                    logger.error(error)
                    logger.warning(traceback.print_exc())

    def _next_image(self):

        image = self._next_image_raw()
        if self._ROI is None:
            return image
        else:
            r = self._ROI
            return image[
                int(r[1]) : int(r[1] + r[3]), int(r[0]) : int(r[0] + r[2])
            ]

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
        if self.is_open():
            self._framerate = float(
                self.camera.AcquisitionFrameRate.GetValue()
            )
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
        self._exposuretime = float(self.camera.ExposureTime.GetValue())
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

    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument(
        "--height",
        type=int,
        default=2160,
    )
    ap.add_argument(
        "--resolution-decrease",
        dest="resolution_decrease",
        type=int,
        default=None,
    )
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
    ap.add_argument("--preview", action="store_true", default=False)
    ap.add_argument(
        "--maxframes",
        type=int,
        default=math.inf,
        help="Camera fetches frames (s)",
    )
    ap.add_argument(
        "--verbose", choices=list(LEVELS.keys()), default="WARNING"
    )
    return ap


def get_dynamic_camera_kwargs(args):

    """
    DEPRECATED
    Filter the input args so only kwargs of the BaslerCamera class init
    or any of its parents are returned
    """

    keys = list(inspect.signature(BaslerCamera).parameters.keys())
    for cls in BaslerCamera.__bases__:
        keys = keys + list(inspect.signature(cls).parameters.keys())

    camera_kwargs = {k: getattr(args, k) for k in vars(args) if k in keys}
    return camera_kwargs


def setup(args=None):

    camera_kwargs = {
        "framerate": getattr(
            args, "basler_framerate", getattr(args, "framerate")
        ),
        "exposure": getattr(
            args, "basler_exposure", getattr(args, "exposure")
        ),
        "width": args.width,
        "height": args.height,
        "resolution_decrease": args.resolution_decrease,
    }
    camera = BaslerCamera(**camera_kwargs)
    return camera


def setup_logger(level):
    logger = logging.getLogger("baslerpi.io.camera")
    logger.setLevel(level)
    console = logging.StreamHandler()
    console.setLevel(level)
    logger.addHandler(console)


def run(camera, queue=None, preview=False):

    try:
        for timestamp, frame in camera:
            print(
                "Basler camera reads: ",
                timestamp,
                frame.shape,
                frame.dtype,
                camera.computed_framerate,
            )
            if queue is not None:
                queue.put((timestamp, frame))

            frame = cv2.resize(
                frame,
                (frame.shape[1] // 3, frame.shape[0] // 3),
                cv2.INTER_AREA,
            )
            if preview:
                cv2.imshow("Basler", frame)
                if cv2.waitKey(1) == ord("q"):
                    break

    except KeyboardInterrupt:
        return


def setup_and_run(args, **kwargs):

    level = LEVELS[args.verbose]
    setup_logger(level=level)
    camera = setup(args)
    maxframes = getattr(args, "maxframes", None)
    camera.open(maxframes=maxframes)
    run(camera, preview=args.preview, **kwargs)


def main(args=None, ap=None):
    """
    Initialize a BaslerCamera
    """

    if args is None:
        ap = get_parser(ap=ap)
        args = ap.parse_args()

    setup_and_run(args)


if __name__ == "__main__":
    main()
