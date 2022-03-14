import cv2
import logging
import os.path

class OpenCVMixin:
    """
    Teach a Recorder class how to use OpenCV to write a video
    """

    def open(self, path, maxframes=None, **kwargs):
        """
        Open a cv2.VideoWriter to the specified path
        Only .avi supported
        If output folder does not exist, it is created on the spot

        path: str encoding a filename with our without folder path
        maxframes: int or None with maximum number of frames to fetch
        """
        assert path.split(".")[-1] == "avi"

        self._path = path
        self._maxframes = maxframes

        # Report information to user
        logging.info("Initializing OpenCV video with following properties:")
        logging.info("  Framerate: %d", self._framerate)
        logging.info("  Resolution: %dx%d", *self.resolution)
        logging.info("  Path: %s", self._path)

        # Create folder if required
        if len(self._path.split("/")[-1].split(".")) != 1:
            output_dir = os.path.dirname(self._path)
        else:
            output_dir = self._path

        self._output_dir = output_dir
        os.makedirs(self._output_dir, exist_ok=True)

        # Initialize video writer
        self._video_writer = cv2.VideoWriter(
            path,
            # cv2.VideoWriter_fourcc(*"DIVX"),
            cv2.VideoWriter_fourcc(*"XVID"),
            int(self._framerate),
            self.resolution,
        )

    def write(self, frame, i, timestamp):
        cv2.imwrite(frame, os.path.join(self._path, f"{str(i).zfill(10)}.png"))

    def close(self):
        """
        Close the cv2.VideoWriter
        """
        self._video_writer.release()
