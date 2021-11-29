"""
Define the steps of an image processing pipeline
Each step is represent by a class which defines an apply() method
This method exposes the functionality of the class
i.e. subclasses using these classes will call this method only
The method MUST take only a frame and return the frame with the processing applied on it
The classes here are passed to the build_pipeline method of a recorder, either as class or an instantiated object
"""
import logging
import datetime
import time

logger = logging.getLogger(__name__)

import numpy as np
import cv2


class TextStep:
    _FONT = cv2.FONT_HERSHEY_SIMPLEX
    _FONTSCALE = 1
    _color = 255

    def put_text(self, frame, text):

        if len(frame.shape) == 3:
            color = (self._color,) * frame.shape[2]  # prob always 3
        else:
            color = self._color

        frame = cv2.putText(
            frame,
            text,
            self._POS,
            self._FONT,
            self._FONTSCALE,
            color,
            2,
            cv2.LINE_AA,
        )

        return frame


class Overlay:
    def apply(self, frame):
        overlay_width = frame.shape[1]
        overlay_height = 100
        overlay_shape = list(frame.shape)
        overlay_shape[0] = overlay_height
        overlay_shape[1] = overlay_width
        overlay = np.zeros(tuple(overlay_shape), dtype=np.uint8)
        frame[:overlay_height, :overlay_width] = overlay
        return frame


class TimeAnnotator(TextStep):
    """
    Teach a Recorder class how to write down on the frame
    datetime and other potentially relevant variables
    """

    _POS = (1, 25)  # x, y

    def apply(self, frame):
        text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = self.put_text(frame, text)
        return frame


class FrameCountAnnotator(TextStep):
    def __init__(self):
        self._frame_count = 0

    @property
    def _POS(self):
        return (int(self._frame_shape[1] * 0.9), 25)

    def apply(self, frame):
        self._frame_count += 1
        self._frame_shape = frame.shape
        text = f"Frame {self._frame_count}"
        frame = self.put_text(frame, text)
        return frame


class BlackFrameCountAnnotator(FrameCountAnnotator):
    _color = 0


class FPSAnnotator(TextStep):
    """
    Write down the average fps over the last _INTERVAL_SECONDS
    """

    _INTERVAL_SECONDS = 1
    _POS = (1, 60)  # x, y

    def __init__(self):
        self._lastcount = 0
        self._last_timestamp = 0

    @property
    def computed_fps(self):
        if (time.time() - self._last_timestamp) > self._INTERVAL_SECONDS:
            self._computed_fps = self._lastcount / self._INTERVAL_SECONDS
            self._last_timestamp = time.time()
            self._lastcount = 0
        else:
            self._lastcount += 1

        return self._computed_fps

    def apply(self, frame):

        text = f"FPS: {int(self.computed_fps)}"
        frame = self.put_text(frame, text)
        return frame


class Inverter:
    """
    Invert a frame so y = 255 - x
    """

    @staticmethod
    def apply(frame):
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        gray = 255 - gray
        return gray


class Masker:
    """
    Mask a video with a predefined mask
    """

    _mask = None
    _box = [0, 0, 1000, 1000]

    def set_mask(self, frame, box):
        mask = np.zeros(frame.shape, np.uint8)
        mask[box[0] : box[2], box[1] : box[3]] = 255
        self._mask = mask

    def apply(self, frame):

        if self._mask is None:
            self.set_mask(frame, self._box)

        cv2.bitwise_and(frame, self._mask, frame)
        return frame
