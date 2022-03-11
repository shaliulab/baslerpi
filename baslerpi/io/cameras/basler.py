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
from baslerpi.io.cameras.core import CV2Compatible


logger = logging.getLogger("baslerpi.io.camera")
LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}


class BaslerCamera(CV2Compatible):

    _MAX_FAILED_COUNT = 5

    r"""
    Drive a Basler camera using pypylon.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.REVERSE_X = True
        self.REVERSE_Y = True
        self.camera=None
        self.open()

    @property
    def width(self):
        return self.camera.Width.GetValue()

    @property
    def height(self):
        self.camera.Height.GetValue()

    @property
    def model_name(self):
        return self.camera.GetDeviceInfo().GetModelName()

    @property
    def framerate(self):
        return self._target_framerate

    @framerate.getter
    def framerate(self):
        return float(self.camera.AcquisitionFrameRate.GetValue())

    @framerate.setter
    def framerate(self, framerate):
        logging.warning("Setting framerate is not recommended in baslerpi")
        self.camera.AcquisitionFrameRate.SetValue(framerate)

    @property
    def exposure(self):
        return self._exposure

    @exposure.getter
    def exposure(self):
        return float(self.camera.ExposureTime.GetValue())

    @exposure.setter
    def exposure(self, exposure):
        logging.warning("Setting exposure time is not recommended in baslerpi")
        self.camera.ExposureTime.SetValue(exposure)

    def is_last_frame(self):
        if self._duration is None:
            return False

        return self._duration < (self._time_s - self.start_time)

    def is_open(self):
        """
        Return True if camera is opened
        """
        return self.camera.IsOpen()
       
    def _next_image(self):
        # NOTE
        # Forcing here _next_image_rois() 
        if self._rois is None:# and False:
            return self._next_image_default()
        else:
            return self._next_image_rois()


    def _next_image_default(self):
        grabResult = self.camera.RetrieveResult(
            self._timeout, pylon.TimeoutHandling_ThrowException
        )
        status = grabResult.GrabSucceeded()
        if status:
            img = grabResult.Array
            grabResult.Release()
            code = 0
        else:
            img = None
            code = 1
        
        return status, img

    def _init_camera(self):
        try:
        # Get the transport layer factory.

            tlFactory = pylon.TlFactory.GetInstance()
            camera_device = tlFactory.CreateFirstDevice()
            self.camera = pylon.InstantCamera(
                camera_device
            )
        except Exception as error:
            logger.error(
                "The Basler camera cannot be opened."\
                " Please check error trace for more info"
            )
            logger.error(error)
            logger.error(traceback.print_exc())
            sys.exit(1)


    def _init_read(self):
        status, img = self._next_image_default()

        if status and img is not None:

            logger.info("Basler camera opened successfully")
            if self.start_time is None:
                self.start_time = time.time()

            logger.info(
                "Resolution of incoming frames: %dx%d",
                img.shape[1],
                img.shape[0],
            )
        else:
            raise Exception("The initial grab() did not work")


    def open(self, maxframes=None, buffersize=5):
        """
        Detect a Basler camera using pylon
        Assign it to the camera slot and try to open it
        Try to fetch a frame
        """
        self._init_camera()
        self.camera.Open()
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        self.camera.ExposureTime.SetValue(self._target_exposure)
        self.camera.AcquisitionFrameRate.SetValue(self._target_framerate)
        self.camera.Width.SetValue(self._target_width)
        self.camera.Height.SetValue(self._target_height)
        self.camera.ReverseX.SetValue(self.REVERSE_X)
        self.camera.ReverseY.SetValue(self.REVERSE_Y)
        self.camera.MaxNumBuffer = buffersize

        if maxframes is not None:
            self.camera.StartGrabbingMax(maxframes)
            # if we want to limit the number of frames
        else:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        # Print the model name of the camera.
        logger.info(f"Using device {self.model_name}")
        self._init_read()

    def close(self):
        self.camera.Close()

def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser()

    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--camera-name", dest="camera_name", default="Basler")
    ap.add_argument(
        "--height",
        type=int,
        default=2160,
    )
    ap.add_argument(
        "--resolution-decrease",
        dest="resolution_decrease",
        type=float,
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
    ap.add_argument(
        "--select-rois",
        default=False,
        dest="select_rois",
        action="store_true",
    )
    return ap


def setup(args=None, camera_name="Basler", idx=0, **kwargs):

    camera_kwargs = {
        "framerate": getattr(
            args,
            f"{camera_name.lower()}_framerate",
            getattr(args, "framerate"),
        ),
        "exposure": getattr(
            args, f"{camera_name.lower()}_exposure", getattr(args, "exposure")
        ),
        "width": args.width,
        "height": args.height,
        "resolution_decrease": args.resolution_decrease,
    }
    camera_kwargs.update(kwargs)
    if camera_name == "Basler":
        camera = BaslerCamera(**camera_kwargs, idx=idx)
    return camera


def setup_logger(level):
    logger = logging.getLogger("baslerpi.io.camera")
    logger.setLevel(level)
    console = logging.StreamHandler()
    console.setLevel(level)
    logger.addHandler(console)


def run(camera, queue=None, preview=False):

    try:
        for timestamp, all_rois in camera:

            for frame in all_rois:
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
    if args.select_rois:
        camera.select_ROIs()
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
