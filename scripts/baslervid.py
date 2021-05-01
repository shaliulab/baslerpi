#! /usr/bin/python

"""
A raspivid-like executable to interact with Basler cameras
Key flags should have a behavior identical to raspivid
"""
import argparse
import sys
import math
import re
import logging
import logging.config

import cv2

from baslerpi.utils import parse_protocol, read_config_yaml
from baslerpi.io.cameras.basler_camera import BaslerCamera
from baslerpi.io.cameras.emulator_camera import EmulatorCamera 
from baslerpi.web_utils import TCPClient

config = read_config_yaml("conf/logging.yaml")
logging.config.dictConfig(config)

logger = logging.getLogger(__name__)


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
ap.add_argument("-fps", "--framerate", default=30)
ap.add_argument("-ss", "--shutter", default=15000, help="Manually controls the speed of the camera’s shutter in microseconds (i.e. 1e6 us = 1s")
ap.add_argument("-v", "--verbose", dest="verbose", default=False, action="store_true")
ap.add_argument("-t", "--timeout", default=5000, type=int, help="Control the timeout, in ms, that the video will be recorded")
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

ap.add_argument("-e", "--emulate", dest="emulate", default=False, action="store_true", help="If passed, an emulator camera yielding random RGB images is run, instead of a Basler Camera. This is useful for debugging / testing purposes")

args = ap.parse_args()

if args.print_help:
  ap.print_help()
  sys.exit(0)

class BaslerVidClient:

    def __init__(self, args):

        if args.emulate:
            CameraClass = EmulatorCamera
        else:
            CameraClass = BaslerCamera

        camera = CameraClass(
          # temporal resolution
          framerate=args.framerate,
          # spatial resolution
          height=args.height,
          width=args.width,
          # shutter speed (exposure time)
          shutter=args.shutter,
          # ISO
          iso = args.iso,
          # timeout
          timeout=args.timeout,
          # color scale of the camera
          colfx=args.colfx
        )

        self._camera = camera



    def stream(self, url):
        """
        Stream data to tcp server in url
        """

        host, port = url[1].split(":")
        logger.debug(f"Streaming data to {url}")
        # protocol
        tcp_client = TCPClient(host, int(port))
        tcp_client.daemon = True
        tcp_client.start()
        self._camera.open()

        for t_ms, frame in self._camera:
            tcp_client.queue(frame)
        tcp_client.stop()
        return 0

    def save(self, path):
        pass

    def pipe(self):
        """
        Pass obtained data to std output
        """

        logger.debug("Piping data to stdout")
        encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]

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
        logger.debug("Running preview of camera")

        for t_ms, frame in self._camera:
            cv2.imshow("preview", frame)
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break

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
            self.preview()
        else:
            url = parse_protocol(args.output)
            if url is None:
                if args.output == "-":
                    self.pipe()
                else:
                    self.save(args.output)
            else:
                self.stream(url)

baslervid = BaslerVidClient(args)
baslervid.run(args)
