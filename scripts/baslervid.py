#! /usr/bin/python

"""
A raspivid-like executable to interact with Basler cameras
Key flags should have a behavior identical to raspivid
"""
import argparse
import sys
import math
import time
import logging
import logging.config
import multiprocessing
import math

import numpy as np

from baslerpi.utils import parse_protocol, read_config_yaml
from baslerpi.io.cameras.basler_camera import BaslerCamera
from baslerpi.io.cameras.emulator_camera import RandomCamera, DeterministicCamera

config = read_config_yaml("conf/logging.yaml")
logging.config.dictConfig(config)

logger = logging.getLogger(__name__)


try:
    from baslerpi.processing.annotate import Annotator
    ANNOTATOR_AVAILABLE = True
except ModuleNotFoundError:
    logger.warning("Could not find cv2 module installation")
    ANNOTATOR_AVAILABLE = False


def range_limited_int_type(arg):
    """ Type function for argparse - an int within some predefined bounds """
    MIN_VAL = 100
    MAX_VAL = 800
    try:
        f = int(arg)
    except ValueError:    
        raise argparse.ArgumentTypeError("Must be an int number")
    if f < MIN_VAL or f > MAX_VAL:
        raise argparse.ArgumentTypeError("Argument must be < " + str(MAX_VAL) + "and > " + str(MIN_VAL))
    return f


ap = argparse.ArgumentParser(add_help=False)

ap.add_argument("-h", "--height", type=int, default=960)
ap.add_argument("-w", "--width", type=int, default=1280)
ap.add_argument("-?", dest="print_help", default=False, action="store_true")
ap.add_argument("-o", "--output", required=False)
ap.add_argument("-fps", "--framerate", default=30, type=int)
ap.add_argument("-ss", "--shutter", default=15000, type=int, help="Manually controls the speed of the camera’s shutter in microseconds (i.e. 1e6 us = 1s")
ap.add_argument("-v", "--verbose", dest="verbose", default=False, action="store_true")

ap.add_argument("-t", "--timeout", default=5000, type=int, help="Control the timeout, in ms, that the video will be recorded")
ap.add_argument("--count", dest="count", default=math.inf, type=int, help="Number of frames to be recorded")
ap.add_argument("-cfx", "--colfx", default="128:128", help="""
    TODO Allows the user to adjust the YUV colour space for fine-grained control of the final image.
    Values should be given as U:V , where U controls the chrominance and V the luminance.
    A value of 128:128 will result in a greyscale image
    """
)
ap.add_argument("-ISO", "--ISO", dest="iso", type=range_limited_int_type, help="TODO ISO sensitivity")
#ap.add_argument("-roi", "--roi", nargs="4",  help="TODO Allows part of the camera sensor to be specified as the capture source. Ex 0 0 100 100", required=False, default="0 0 math.inf math.inf")
ap.add_argument("-n", "--no-preview", dest="preview", default=False, action="store_false", help="TODO Does not display a preview window while capturing.")
ap.add_argument("-p", "--preview", dest="preview", nargs=4, help=
    """
    TODO
    Sets the size of the preview window and where it appears.
    The value should be given as X,Y,W,H —where X and Y are the
    pixel coordinates where the window’s top-left corner should be drawn, and W and H
    the width and height of the preview window in pixels, respectively.
    """
)

ap.add_argument("-e", "--emulate", default=None, help=
        """
        If passed and set to random, an emulator camera yielding random RGB images is run, instead of a Basler Camera.
        If passed and set to deterministic, the same random frame is always passed.
        If not passed at all, a basler camera is used.
        This is useful for debugging / testing purposes.
        """)
ap.add_argument("-a", "--annotate", action="append", nargs="+", type=str, help="Enable/set annotate flags or text")

args = ap.parse_args()

if args.print_help:
  ap.print_help()
  sys.exit(0)

class BaslerVidClient:

    def __init__(self, args):

        if args.emulate is None:
            CameraClass = BaslerCamera
        elif args.emulate == "random":
            CameraClass = RandomCamera
        elif args.emulate == "deterministic":
            CameraClass = DeterministicCamera
        else:
            logger.error("Please emulate with random or deterministic camera")
        
        self.manager = multiprocessing.Manager()
        self.out_q = self.manager.Queue(maxsize=1)
 
        camera_kwargs = {
            # temporal resolution
            "framerate": args.framerate,
            # spatial resolution
            "height": args.height,
            "width": args.width,
            # shutter speed (exposure time)
            "shutter": args.shutter,
            # ISO
            "iso": args.iso,
            "timeout": args.timeout,
            "count": args.count,
            # color scale of the camera
            "colfx": args.colfx
        }

        if ANNOTATOR_AVAILABLE:
            annotator = Annotator()
            if args.annotate:
                for v in args.annotate:
                    if isinstance(v, list):
                        for vv in v:
                            annotator._decompose_value(vv)
                    else:
                        annotator._decompose_value(v)

            camera_kwargs["annotator"] = annotator

        self._CameraClass = CameraClass
        self._camera_kwargs = camera_kwargs


    def stream(self, url, in_q):
        """
        Stream data to tcp server in url
        """
        from baslerpi.web_utils.client import TCPClient, FastTCPClient
        import multiprocessing

        TCPClientClass = FastTCPClient

        host, port = url[1].split(":")
        logger.debug(f"Streaming data to {url}")
        self.tcp_client = TCPClientClass(in_q, host, int(port))
        self.tcp_client.daemon = True
        self.tcp_client.start()


    def get_frames(self, out_q, CameraClass, **camera_kwargs):

        camera = CameraClass(**camera_kwargs)
        camera.open()

        last_tick = 0
        count = 0
        for t_ms, frame in camera:
            if t_ms > (last_tick + 1000):
                last_tick = t_ms
                print(f"Framerate: {count}")
                count = 0
            else:
                count += 1
                
            if out_q.qsize() == 1:
                out_q.get()
            out_q.put((t_ms, frame))

        camera.close()
        return 0

    def save(self, path):
        pass

    def pipe(self):
        """
        Pass obtained data to std output
        """

        logger.debug("Piping data to stdout")
        import cv2
        encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
        logging.basicConfig(level=logging.CRITICAL)

        for t_ms, frame in self._camera:
            result, imgencode = cv2.imencode('.jpg', frame, encode_param)
            data = np.array(imgencode)
            binary_data = data.tostring()
            sys.stdout.buffer.write(binary_data)

        return 0

    def preview(self):
        """
        Preview data in a pop up window live
        """
        import cv2
        logger.debug("Running preview of camera")

        self.fetcher_process = multiprocessing.Process(target=self.get_frames, args=(self.out_q, self._CameraClass), kwargs=self._camera_kwargs)
        self.fetcher_process.start()

        try:
            while True:
                t_ms, frame = self.out_q.get()
                cv2.imshow("preview", preview)
                if cv2.waitKey(25) & 0xFF == ord('q'):
                    break

        except KeyboardInterrupt:
            return 0

        return 0


    def minimal(self):
        import cv2
        logger.debug("Running preview of camera")

        self.fetcher_process = multiprocessing.Process(target=self.get_frames, args=(self.out_q, self._CameraClass), kwargs=self._camera_kwargs)
        self.fetcher_process.start()

        try:
            while True:
                t_ms, frame = self.out_q.get()
                print(frame.shape)

        except KeyboardInterrupt:
            return 0

        return 0




    def close(self):
        logger.debug("Closing baslervid")
        camera.close()
        return 0


    def run(self, args):
        """
        Run baslervid by following user's arguments
        """
        

        if args.output is None:
            self.minimal()
        elif args.preview:
            self.preview()
        else:
            url = parse_protocol(args.output)
            if url is None:
                if args.output == "-":
                    self.pipe()
                else:
                    self.save(args.output)
            else:
                self.fetcher_process = multiprocessing.Process(target=self.get_frames, args=(self.out_q, self._CameraClass), kwargs=self._camera_kwargs)
                self.fetcher_process.start()

                try:
                    self.stream(url, in_q=self.out_q)
                except KeyboardInterrupt:
                    pass
                finally:
                    pass



baslervid = BaslerVidClient(args)
baslervid.run(args)
