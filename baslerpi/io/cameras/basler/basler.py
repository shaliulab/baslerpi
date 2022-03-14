# Standard library
from lib2to3.pgen2.token import NOTEQUAL
import logging
import traceback
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
        return float(self.camera.AcquisitionFrameRate.GetValue())

    @framerate.setter
    def framerate(self, framerate):
        logging.warning("Setting framerate is not recommended in baslerpi")
        self.camera.AcquisitionFrameRate.SetValue(framerate)
        self._target_framerate = framerate

    @property
    def exposure(self):
        return float(self.camera.ExposureTime.GetValue())

    @exposure.setter
    def exposure(self, exposure):
        logging.warning("Setting exposure time is not recommended in baslerpi")
        self.camera.ExposureTime.SetValue(exposure)
        self._target_exposure = exposure

    def is_open(self):
        """
        Return True if camera is opened
        """
        return self.camera.IsOpen()
       
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
        
        # NOTE
        # When selecting a particular camera
        # you may want to use self.idx

        try:
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

        if self._target_width is None:
            self._target_width = self.camera.Width.GetMax()

        if self._target_height is None:
            self._target_height = self.camera.Height.GetMax()

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
