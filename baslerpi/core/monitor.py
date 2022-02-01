import logging
import time

logger = logging.getLogger(__name__)
import multiprocessing
import threading
import queue

from baslerpi.io.recorders import ImgStoreRecorder
from baslerpi.io.recorders.record import setup as setup_recorder

from baslerpi.utils import document_for_reproducibility
from baslerpi.io.cameras.basler_camera import setup as setup_camera
from baslerpi.web_utils.sensor import setup as setup_sensor
from baslerpi.exceptions import ServiceExit


LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30}


class Monitor(threading.Thread):
    _RecorderClass = ImgStoreRecorder
    _CAMERAS = {"Basler": setup_camera}

    def __init__(
        self,
        camera_name,
        input_args,
        stop_queue=None,
        *args,
        sensor=None,
        camera_idx=0,
        start_time=None,
        **kwargs,
    ):

        self._logging_level = int(LEVELS[input_args.verbose])
        self._camera_idx = camera_idx

        queue_size = int(self._RecorderClass._asyncWriterClass._CACHE_SIZE)
        rois = kwargs.pop("rois", None)
        self.setup_camera(
            camera_name=camera_name,
            args=input_args,
            idx=camera_idx,
            rois=rois,
            start_time=start_time,
        )

        self._stop_queue = stop_queue

        self._queues = [
            multiprocessing.Queue(maxsize=queue_size) for _ in self.camera.rois
        ]
        self._stop_queues = [
            multiprocessing.Queue(maxsize=1) for _ in self.camera.rois
        ]

        if sensor is None:
            sensor = setup_sensor(input_args)

        kwargs.update(
            {
                "sensor": sensor,
            }
        )
        self._stop_event = multiprocessing.Event()

        self._recorders = []

        for i in range(len(self.camera.rois)):
            kwargs.update(
                {
                    "resolution": self.camera.rois[i][2:4],
                }
            )

            data_queue = self._queues[i]
            data_queue.name = camera_name

            recorder = setup_recorder(
                input_args,
                *args,
                recorder_name=self._RecorderClass.__name__,
                source=data_queue,
                stop_queue=self._stop_queues[i],
                idx=i,
                roi=self.camera.rois[i],
                framerate=float(int(self.camera.framerate)),
                **kwargs,
            )
            self._recorders.append(recorder)

        super(Monitor, self).__init__()

    def setup_camera(self, camera_name, args, **kwargs):
        self._camera_name = camera_name
        camera = self._CAMERAS[camera_name](
            args=args, camera_name=camera_name, **kwargs
        )

        maxframes = getattr(args, "maxframes", None)
        camera.open(maxframes=maxframes)

        if args.select_rois:
            camera.select_ROIs()

        self.camera = camera
        return camera

    def open(self, path, **kwargs):
        for idx in range(len(self.camera.rois)):

            recorder_path = self.camera.configure_output_path(path, idx)

            self._recorders[idx].open(
                path=recorder_path, logging_level=self._logging_level, **kwargs
            )
            print(
                f"{self._recorders[idx]} for {self.camera} has recorder_path = {recorder_path}"
            )

    def run(self):

        logger.info("Monitor starting")
        self._start_time = self.camera._start_time
        for recorder in self._recorders:
            recorder._start_time = self._start_time
            recorder._async_writer._start_time = self._start_time
            recorder.start()

        for frame_idx, (timestamp, frame) in enumerate(self.camera):

            if self._stop_event.is_set():
                # if self._logging_level <= 10:
                print("Monitor exiting")

                for i in range(len(self._recorders)):
                    if self._logging_level <= 10:
                        print(
                            f"Recorder {i} output queue has {self._recorders[i].buffered_frames} frames"
                        )
                break

            if self._stop_queue is not None:
                try:
                    msg = self._stop_queue.get(False)
                except queue.Empty:
                    msg = None
                if msg == "STOP":
                    print(f"Setting {self} stop event")
                    self._stop_event.set()

            # print("New frame read")
            for i in range(len(self.camera.rois)):
                # self._recorders[i]._run(timestamp, frame[i])
                recorder = self._recorders[i]
                # logger.debug(f"Recorder {i} queue is being put a frame at t {timestamp}")
                if self._logging_level <= 10:
                    print(
                        f"Recorder {i} data queue is being put a frame with shape {frame[i].shape} at t {timestamp}"
                    )
                self._queues[i].put((timestamp, frame_idx, frame[i]))
                if self._logging_level <= 10:
                    print(
                        f"Recorder {i} data queue's has now {recorder._data_queue.qsize()} frames"
                    )

        print("Joining recorders")
        for recorder in self._recorders:
            if recorder.is_alive():
                while not recorder.all_queues_have_been_emptied:
                    time.sleep(1)
                    print("Waiting for", recorder)
                    # recorder._report_cache_usage()
                # print("Terminating")
                # recorder.terminate()
                print("Report one last time ", recorder)
                recorder._async_writer._report_cache_usage()
                print("Close tqdm for ", recorder)
                print("Joining", recorder)
            recorder.join()
            print("JOOOOIIIIIINEEEEDD")

        print("Joined all recorders")

    def close(self):

        # this makes the run method exit
        # because it checks if the stop_event is set
        self._stop_event.set()
        logger.info("Monitor closing")

        for recorder in self._recorders:
            recorder.close()


def run(monitor, **kwargs):

    kwargs.update(document_for_reproducibility(monitor))
    monitor.open(**kwargs)
    try:
        monitor.start()
        time.sleep(5)
        monitor.join()
        # while monitor.is_alive():
        #    print("Running time sleep forever")
        #    time.sleep(0.5)

    except ServiceExit:
        print("ServiceExit captured at Monitor level")
        monitor.close()
    except Exception as error:
        print(error)
    finally:
        print(f"Joining monitor {monitor}")
        monitor.join()
        print(f"Joined monitor {monitor}")
        if monitor._stop_queue is not None:
            print(f"stop_queue size: {monitor._stop_queue.qsize()}")

        for some_queue in monitor._stop_queues:
            print(f"{some_queue} size: {some_queue.qsize()}")
        for some_queue in monitor._queues:
            while some_queue.qsize() != 0:
                print(f"Wait! {some_queue} size: {some_queue.qsize()}")
                time.sleep(1)
                try:
                    data = some_queue.get(False)
                    print(data)
                except queue.Empty:
                    pass
