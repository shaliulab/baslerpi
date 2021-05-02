import logging

import cv2

#from baslerpi.io.cameras.basler_camera import BaslerCamera as CameraClass
from baslerpi.io.cameras.emulator_camera import EmulatorCamera as CameraClass

logger = logging.getLogger("baslerpi.io.cameras")
logger.propagate = True
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
logger.setLevel(logging.INFO)
logger.addHandler(sh)


class Camera(CameraClass):

    def get_frame(self):
        time_s, frame = self._next_time_image()
        ret, jpeg = cv2.imencode('.jpg', frame)
        frame_binary = jpeg.tobytes()
        return frame_binary
