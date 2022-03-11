import unittest
import numpy as np

from baslerpi.io.cameras.basler import BaslerCamera

class TestBasler(unittest.TestCase):


    def test_camera_reads(self):
        self.camera = BaslerCamera()
        self.assertTrue(self.camera.is_open())
        ret, frame = self.camera.read()
        self.assertIsInstance(frame[0], np.ndarray)
        self.camera.close()
        self.assertFalse(self.camera.is_open())


    def test_camera_cm(self):
        with BaslerCamera() as self.camera:
            ret, frame = self.camera.read()
            self.assertTrue(isinstance(frame, np.ndarray))
       

    def test_camera_loops(self):
        self.camera = BaslerCamera()
        for timestamp, rois in self.camera:
            self.assertIsInstance(rois[0], np.ndarray)
            self.assertLess(timestamp - self.camera.start_time, 5)
            break
        
        self.camera.close()


    def test_rois(self):

        self.camera = BaslerCamera(rois=[(0, 0, 100, 50)])
        for timestamp, rois in self.camera:
            self.assertEqual(rois[0].shape[0], 50)
            self.assertEqual(rois[0].shape[1], 100)
            break

    def test_set_parameters(self):
        self.camera = BaslerCamera(framerate=30, exposure=15000)

        self.assertAlmostEqual(self.camera.framerate, 30, delta=1)
        self.assertAlmostEqual(self.camera.exposure, 15000, delta=20)

        self.camera.close()
        


if __name__ == "__main__":
    unittest.main()
