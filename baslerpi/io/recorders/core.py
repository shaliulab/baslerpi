import sys
import queue
import argparse
import datetime
import math
import multiprocessing
import threading
import time
import logging
from abc import abstractmethod

from baslerpi.constants import ENCODER_FORMAT_CPU
from baslerpi.class_utils.time import TimeUtils

class AbstractRecorder(multiprocessing.Process):
# class AbstractRecorder(threading.Thread):
    """
    Take an iterable source object which returns (timestamp, frame)
    in every iteration and save to a path determined in the open() method
    """

    def __init__(
        self,
        path,
        idx=0,
        framerate=None,
        resolution=None,
        duration=math.inf,
        maxframes=math.inf,
        encoder=ENCODER_FORMAT_CPU,
        preview=False,
        sensor=None,
        roi=None,
        stop_queue=None,
        isColor=False,
    ):
        """
        Initialize a recorder with framerate equal to FPS of source
        or alternatively provide a custom framerate
        """
        self.idx = idx
        self._async_writer = None
        self._path = path
        self._first_img = None


        self._framerate = framerate
        self._duration = duration

        assert resolution is not None
        self._resolution = resolution

        if maxframes == 0:
            maxframes = math.inf
        self._maxframes = math.inf
        self._sensor = sensor
        self._time_s = 0


        self._encoder = encoder
        self._preview = preview
        self._roi = roi

        self.start_time = None
        self._last_update = 0

        self.isColor = isColor

        if isColor:
            raise Exception("Color images not supported")
       

        super().__init__()
        self.daemon = True

        # TODO
        # Comment this line when using multiprocessing.Process
        # self.exitcode = 0

    @abstractmethod
    def write(self, frame, framecount, timestamp):
        raise NotImplementedError

    @abstractmethod
    def save_extra_data(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def open(self, path):
        raise NotImplementedError

    @abstractmethod
    def report_cache_usage(self):
        raise NotImplementedError


    @property
    @abstractmethod
    def running_for_seconds(self):
        raise NotImplementedError


    @property
    def resolution(self):
        return self._resolution

    @property
    def sensor(self):
        return self._sensor


    @property
    def all_queues_have_been_emptied(self):
        return self._data_queue.qsize() == self._stop_queue.qsize() == 0

    @property
    def framerate(self):
        return self._framerate

    @property
    def imgshape(self):
        return self.resolution[::-1]


    @property
    def name(self):
        return "Recorder"


    @property
    def max_frames_reached(self):
        return self.n_saved_frames >= self._maxframes


    @property
    def duration_reached(self):
        if self._duration is None:
            duration_reached = False
        else:
            duration_reached = self.running_for_seconds >= self._duration
        
        return duration_reached

    def should_stop(self):

        try:
            msg = self._stop_queue.get(False)
        except queue.Empty:
            msg = None

        result = (
            self.duration_reached
            or self.max_frames_reached
            or msg == "STOP"
        )

        return result

class BaseRecorder(TimeUtils, AbstractRecorder):
    pass