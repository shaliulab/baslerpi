import logging

import datetime
import cv2


logger = logging.getLogger(__name__)


class BaseAnnotator:
    def annotate(self, frame):
        return frame


class TimeAnnotator(BaseAnnotator):
    def annotate(self, frame):

        time_now = datetime.datetime.now().strftime("%H:%M:%S")
        logger.debug(f"Annotating time: {time_now}")
        frame = cv2.putText(
            frame,
            time_now,
            (500, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        frame = super().annotate(frame)
        return frame


class DateAnnotator(BaseAnnotator):
    def annotate(self, frame):
        date_now = datetime.datetime.now().strftime("%Y-%m-%d")
        frame = cv2.putText(
            frame,
            date_now,
            (0, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            255,
            1,
            cv2.LINE_AA,
        )
        frame = super().annotate(frame)
        return frame


class DateTimeAnnotator(DateAnnotator, TimeAnnotator):
    def annotate(self, frame):
        frame = super().annotate(frame)
        return frame


class ShutterAnnotator(BaseAnnotator):
    def annotate(self, frame):
        logger.debug("Not implemented")
        return super().annotate(frame)


class FreeAnnotator(BaseAnnotator):
    def __init__(self, text):
        self._text = text

    def annotate(self, frame):
        frame = cv2.putText(
            frame,
            self._text,
            (1000, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            255,
            2,
            cv2.LINE_AA,
        )
        frame = super().annotate(frame)
        return frame


class Annotator:

    _meanings = {
        4: TimeAnnotator,
        8: DateAnnotator,
        12: DateTimeAnnotator,
        16: ShutterAnnotator,
    }

    def _decompose_value(self, value):

        try:
            value = int(value)
            value_is_str = False
        except ValueError:
            value_is_str = True

        if value_is_str:
            self._annotators.append(FreeAnnotator(value))
        else:
            binary_string = "{0:b}".format(value)
            keys = [
                2 ** i for i, v in enumerate(binary_string[::-1]) if v == "1"
            ]
            for i, key in enumerate(keys):
                if key in self._meanings:
                    annotator = self._meanings[key]
                    self._annotators.append(annotator())
                # if the key is not available, ignore it

    def __init__(self):
        self._annotators = []

    def annotate(self, frame):

        if self._annotators:
            for ann in self._annotators:
                frame = ann.annotate(frame)
        return frame
