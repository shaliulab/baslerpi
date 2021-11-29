import logging
import os.path
import time
import sys


logger = logging.getLogger(__name__)

import cv2
import numpy as np


class OpenCVCompressor:
    """
    Segment animals inside a behavioral recording by masking the foreground
    """

    _blur_kernel = 3
    _erode_kernel = np.ones((9, 9))
    _erode_iterations = 2
    _pad_pixels = 10
    _closing_kernel = np.ones((9, 9))
    _closing_iterations = 5
    _boxSide = 700
    _minContour_area = 500

    def __init__(self, ntargets, shape, frequency=2, algo="MOG2", debug=False):
        self._debug = debug
        self._ntargets = ntargets
        self._frequency = frequency
        self._safe_positions = []
        self._last_positions = []
        self._shape = shape[:2]
        frame_mask = np.full(self._shape, 255, dtype=np.uint8)
        frame_mask = frame_mask[
            self._pad_pixels : (self._shape[0] - self._pad_pixels),
            self._pad_pixels : (self._shape[1] - self._pad_pixels),
        ]

        self._frame_mask = cv2.copyMakeBorder(
            frame_mask,
            *(self._pad_pixels,) * 4,
            cv2.BORDER_CONSTANT,
            None,
            255,
        )
        try:
            assert self._frame_mask.shape == self._shape
        except AssertionError:
            logger.warning(frame_mask.shape)
            logger.warning(self._shape)
            raise Exception("Mask and frame shape dont match")

        # https://docs.opencv.org/master/d1/dc5/tutorial_background_subtraction.html
        self._algo = algo
        if self._algo == "MOG2":
            backSub = cv2.createBackgroundSubtractorMOG2()
        else:
            backSub = cv2.createBackgroundSubtractorKNN()

        self._backSub = backSub
        self._framecount = 0

    def _monochrome(self, frame):
        """
        Make sure frame is in grayscale (2D)
        """
        if len(frame.shape) == 2:
            return frame
        elif len(frame.shape) == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            raise Exception("Frame has 4D or more")

    def _find(self, frame):
        """
        Find big contours and their center of the contours with Huber moments
        Update the _last_positions using a sensible heuristic
        """
        frame = cv2.medianBlur(frame, self._blur_kernel)
        frame = cv2.erode(
            frame,
            self._erode_kernel,
            iterations=self._erode_iterations,
        )

        segmented = self._backSub.apply(frame)
        mask = np.bitwise_and(segmented, np.copy(self._frame_mask))

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            self._closing_kernel,
            iterations=self._closing_iterations,
        )
        mask = cv2.erode(mask, self._erode_kernel, iterations=3)
        cts, _ = cv2.findContours(
            mask,
            mode=cv2.RETR_EXTERNAL,
            method=cv2.CHAIN_APPROX_SIMPLE,
        )
        cts = [ct for ct in cts if cv2.contourArea(ct) > self._minContour_area]

        moms = [cv2.moments(ct) for ct in cts]
        positions = [
            (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])) for M in moms
        ]

        if len(positions) != self._ntargets:
            self._last_positions = self._safe_positions + positions
        else:
            self._last_positions = positions
            self._safe_positions = positions

        if self._debug:
            print(f"Len cts: {len(cts)}")
            self._debug1 = np.hstack(
                [
                    mask,
                    cv2.drawContours(
                        np.zeros(frame.shape, dtype=np.uint8),
                        cts,
                        -1,
                        255,
                        -1,
                    ),
                ]
            )
        return positions

    def _rectfrompt(self, pt):
        if pt is list:
            pt = pt[0]
        return (
            int(pt[0] - self._boxSide / 2),
            int(pt[1] - self._boxSide / 2),
            self._boxSide,
            self._boxSide,
        )

    @property
    def warmup(self):
        return self._framecount < 10

    def apply(self, frame):
        """
        User endpoint receiving a raw frame and returning a compressed (masked) frame
        """
        self._framecount += 1

        frame = self._monochrome(frame)
        frame_orig = frame.copy()
        final_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        if (self._framecount % self._frequency) == 0 or self.warmup:
            positions = self._find(frame)

        # rectangles = [cv2.boundingRect(ct) for ct in cts]
        rectangles = [self._rectfrompt(pt) for pt in self._last_positions]
        # assert len(rectangles) < self._ntargets*2

        for j, rect in enumerate(rectangles):
            final_mask = cv2.rectangle(
                final_mask,
                (rect[0], rect[1]),
                (rect[0] + rect[2], rect[1] + rect[3]),
                255,
                -1,
            )
            final_mask = cv2.putText(
                final_mask,
                str(j),
                (rect[0], rect[1]),
                cv2.FONT_HERSHEY_COMPLEX_SMALL,
                1,
                128,
            )

        compressed_frame = np.bitwise_and(frame_orig, final_mask)

        if self._debug:

            if (
                (self._framecount % self._frequency) == 0 or self.warmup
            ) and self._debug:
                compressed_frame = cv2.putText(
                    compressed_frame,
                    str("FIND"),
                    (100, 200),
                    cv2.FONT_HERSHEY_COMPLEX_SMALL,
                    5,
                    255,
                )
                compressed_frame = cv2.putText(
                    compressed_frame,
                    str(len(positions)),
                    (1000, 200),
                    cv2.FONT_HERSHEY_COMPLEX_SMALL,
                    5,
                    255,
                )
                compressed_frame = cv2.putText(
                    compressed_frame,
                    str(len(self._last_positions)),
                    (1200, 200),
                    cv2.FONT_HERSHEY_COMPLEX_SMALL,
                    5,
                    255,
                )
                for pt in self._last_positions:
                    compressed_frame = cv2.circle(
                        compressed_frame, pt, 20, 128, -1
                    )

            debugging_image = np.hstack(
                [self._debug1, final_mask, compressed_frame]
            )

            debugging_image = cv2.resize(
                debugging_image,
                tuple((np.array(debugging_image.shape)[::-1] // 5).tolist()),
                interpolation=cv2.INTER_AREA,
            )

            print(f"{str(self._framecount).zfill(5)} done")

            if self._debug:
                try:
                    cv2.imshow("output", debugging_image)
                    if cv2.waitKey(0) & 0xFF == 27:
                        # capture.release()
                        sys.exit(0)

                except cv2.error as e:
                    logger.error(e)

        return compressed_frame


if __name__ == "__main__":

    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("camera", choices=["OpenCV", "Basler"])
    ap.add_argument("--input")
    ap.add_argument("--output", required=True)
    ap.add_argument("--frequency", type=int, default=2)
    ap.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="Camera tries getting a frame for ms",
    )
    ap.add_argument(
        "--duration",
        type=int,
        default=300000,
        help="Camera fetches frames for this ms",
    )
    ap.add_argument("-D", "--debug", dest="debug", action="store_true")

    args = ap.parse_args()
    frequency = args.frequency

    i = 0
    from baslerpi.io.recorders import FFMPEGRecorder, ImgstoreRecorder
    from baslerpi.io.cameras import OpenCVCamera, BaslerCamera

    if args.camera == "OpenCV":
        camera = OpenCVCamera(video_path=args.input)
    elif args.camera == "Basler":
        camera = BaslerCamera(tineout=args.timeout)
    else:
        print("Please enter a valid camera class: OpenCV/Basler")
        sys.exit(1)

    camera.open()
    # get a frame just to know what are the frame properties i.e. shape
    for (t, frame) in camera:
        break

    compressor = OpenCVCompressor(
        ntargets=3,
        frequency=frequency,
        shape=frame.shape,
        debug=args.debug,
    )
    # recorder = FFMPEGRecorder(camera, compressor=compressor)
    recorder = ImgstoreRecorder(camera, compressor=compressor)
    recorder.open(path=args.output)
    try:
        recorder.start()
        recorder.join()
    except KeyboardInterrupt:
        recorder._stop_event_set()

    finally:
        recorder.close()
        camera.close()
