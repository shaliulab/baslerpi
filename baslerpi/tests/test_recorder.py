import unittest
import os
import argparse
import logging
import time
import tempfile
import glob
import numpy as np
import cv2
import tqdm

logger1 = logging.getLogger("baslerpi.io.recorders.async_writers")
logger1.setLevel(logging.DEBUG)
logger2 = logging.getLogger("baslerpi.io.recorders.imgstore")
logger2.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger("baslerpi")
log_console_format = "%(levelname)s:%(name)s - %(message)s"
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(log_console_format))
logger.addHandler(handler)


from .utils import download_file
# from baslerpi.tests.utils import download_file
from baslerpi.io.recorders import ImgStoreRecorder


BUFFERSIZE=100
FRAMES=60
CHUNK_DURATION=.5
TARGET_FRAMERATE=30
N_TESTS=2
RES_DEC = 5


n_chunks=FRAMES // TARGET_FRAMERATE // CHUNK_DURATION

class Utils:


    def setUp(self):
        # self._mp4_file = tempfile.NamedTemporaryFile(suffix=".mp4")
        self._mp4_file = argparse.Namespace(name="/home/antortjim/video.mp4")
        # download_file(destination=self._mp4_file.name)
        
        # self._dest_file = tempfile.TemporaryDirectory()
        self._dest_file = argparse.Namespace(name="/home/antortjim/baslerpi_test")
        os.makedirs(self._dest_file.name, exist_ok=True)
        print(f"Saving to {self._dest_file.name}")


    def init_recorder(self, resolution):
        path = self._dest_file.name

        duration = None
        sensor = None
      
        recorder = ImgStoreRecorder(
            idx=0,
            path=path,
            format="mjpeg/avi",
            resolution=resolution,
            framerate=TARGET_FRAMERATE,
            duration=duration,
            sensor=sensor,
            preview=False,
            chunk_duration_s=CHUNK_DURATION,
            extra_data_frequency=2000,
            buffer_size=BUFFERSIZE,
        )
        
        recorder.open(path)
        # print("before recorder.start")
        recorder.start()
        # print("after recorder.start")
        time.sleep(1)
        if not recorder._start_event.is_set():
            recorder._start_event.set()
            recorder.terminate()
            time.sleep(1)
            print(recorder.is_alive())
            print(recorder._async_writer.is_alive())

        return recorder

    def record_from_video_to_imgstore(self, terminate=None):

        cap = cv2.VideoCapture(self._mp4_file.name)
        resolution = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) / RES_DEC),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) / RES_DEC),
        )
        recorder = self.init_recorder(resolution)
        self.recorder = recorder

        if recorder.is_alive():
            for i in range(1,FRAMES):
                if i == terminate:
                    recorder.terminate()
                    return 0
                ret, frame = cap.read()
                frame = frame[:resolution[1],:resolution[0],0]
                timestamp = time.time() - recorder.start_time
                recorder.write(timestamp, i, frame)
                time.sleep(0.1/TARGET_FRAMERATE)

            logger.debug("Last frame is written")        
            cap.release()
            recorder.close()
            exitcode = recorder.safe_join(timeout=6)
            return exitcode
        else:
            return 2


class TestImgStoreRecorder(Utils, unittest.TestCase):

    def _tearDown(self):
        files = glob.glob(os.path.join(self._dest_file.name, "*"))
        for file in files:
            # print(file)
            os.remove(file)


    def _test_records_from_camera(self, terminate=None):

        exitcode = self.record_from_video_to_imgstore(terminate=terminate)
        if exitcode > 1:
            logging.warning("INVALID TEST")
            return

        if self.recorder.is_alive():
            import ipdb; ipdb.set_trace()
        
        self.assertFalse(self.recorder.is_alive())
        self.assertFalse(self.recorder._async_writer.is_alive())
        self.assertTrue(self.recorder._async_writer._data_queue.empty())
        self.assertEqual(exitcode, 0)
        
        avi = glob.glob(
            os.path.join(self._dest_file.name, "*.avi")
        )
        n_avi = len(avi)

        n_metadata = len(glob.glob(
            os.path.join(self._dest_file.name, "*.npz")
        ))

        self.assertEqual(n_avi, n_chunks)
        self.assertEqual(n_metadata, n_chunks)
        self.assertTrue(os.path.exists(
            os.path.join(self._dest_file.name, "metadata.yaml")
        ))


        cap = cv2.VideoCapture(avi[0])
        self.assertTrue("get" in dir(cap))
        framerate = cap.get(cv2.CAP_PROP_FPS)
        self.assertEqual(framerate, TARGET_FRAMERATE)

        nframes = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.assertAlmostEqual(nframes, CHUNK_DURATION*TARGET_FRAMERATE, delta=1)
        ret, frame = cap.read()
        cap.release()

        self.assertTrue(ret)
        self.assertIsInstance(frame, np.ndarray)
        self._tearDown()

    def test_stop_queue(self):

        cap = cv2.VideoCapture(self._mp4_file.name)
        resolution = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) / RES_DEC),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) / RES_DEC),
        )
        recorder = self.init_recorder(resolution)
        if not recorder.is_alive():
            logging.warning("INVALID TEST")
            return

        recorder.close()
        exitcode = recorder.safe_join(6)
        self.assertFalse(recorder._async_writer.is_alive())
        self.assertFalse(recorder.is_alive())
        self.assertEqual(exitcode, 0)

    def test_records_from_camera(self):
        for _ in tqdm.tqdm(range(N_TESTS), desc="test_records_from_camera"):
            self._test_records_from_camera()

    def test_terminate(self):
        exitcode = self.record_from_video_to_imgstore(terminate=30)
        if exitcode == 2:
            logging.warning("INVALID TEST")
            return
        self.assertFalse(self.recorder.is_alive())
        self.assertFalse(self.recorder._async_writer.is_alive())
        self.assertTrue(self.recorder._async_writer._data_queue.empty())
        self.assertEqual(exitcode, 0)

if __name__ == "__main__":
    unittest.main()