import logging
import time

logger = logging.getLogger(__name__)
import multiprocessing
import threading

from baslerpi.io.recorders import ImgstoreRecorder
from baslerpi.utils import document_for_reproducibility
from baslerpi.io.cameras.basler_camera import setup as setup_camera

CAMERAS = {"Basler": setup_camera}

class Monitor(threading.Thread):
    _RecorderClass = ImgstoreRecorder

    def __init__(self, camera_name, args, *args, **kwargs):

        queue_size = self._RecorderClass._CACHE_SIZE
        self.setup_camera(camera_name, args)
        self._queues = [multiprocessing.Queue(maxsize=queue_size) for _ in self.camera.rois]

        self._recorders = [
            self._RecorderClass(
                *args,
                source=self._queues[i],
                resolution=self.camera.rois[i][2:4],
                **kwargs
            )
            for i in self.camera.rois
        ]


    def setup_camera(self, camera_name, args):
        self._camera_name = camera_name
        camera = CAMERAS[camera_name](args)
        camera.open()
        if self.select_roi:
            camera.select_ROI()

        self.camera = camera
        return camera


    def open(self, path, **kwargs):
        for idx in range(len(self.camera.rois)):
            if path[-1] == "/":
                path = path[:-1]

            recorder_path = path + f"_ROI_{idx}"
            self._recorders[idx].open(path=recorder_path, **kwargs)

    def run(self):

        self._start_time = time.time()
        for recorder in self._recorders:
            recorder._start_time = self._start_time

        for timestamp, frame in self.camera:
            for i in range(len(self.camera.rois)):
                self._recorders[i].source.put((timestamp, frame[i]))


    def close(self):
        for recorder in self._recorders:
            recorder.close()


def run(monitor, **kwargs):

    kwargs.update(document_for_reproducibility(monitor))
    # print("Opening recorder")
    monitor.open(**kwargs)
    # print("Starting recorder")

    try:
        monitor.start()
        monitor.join()
    except KeyboardInterrupt:
        pass
    monitor.close()
