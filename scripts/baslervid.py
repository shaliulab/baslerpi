#! /usr/bin/env python

"""
A raspivid-like executable to interact with Basler cameras
Key flags should have a behavior identical to raspivid
"""
import argparse
import datetime
import math
import logging
import logging.config
import os.path
import sys
import time

import numpy as np

from baslerpi.utils import parse_protocol, read_config_yaml
from baslerpi.io.cameras.basler_camera import BaslerCamera
from baslerpi.io.cameras.emulator_camera import RandomCamera, DeterministicCamera

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


def parse_args():
    ap = argparse.ArgumentParser(add_help=False)
    
    ap.add_argument("-h", "--height", type=int, default=960)
    ap.add_argument("-w", "--width", type=int, default=1280)
    ap.add_argument("-?", dest="print_help", default=False, action="store_true")
    ap.add_argument("-o", "--output", required=False)
    ap.add_argument("-fps", "--framerate", default=30, type=int)
    ap.add_argument("-ss", "--shutter", default=15000, type=int, help="Manually controls the speed of the camera’s shutter in microseconds (i.e. 1e6 us = 1s")
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

    return args

class BaslerVidClient:

    def __init__(self, args):

        self.action = None

        if args.emulate is None:
            CameraClass = BaslerCamera
        elif args.emulate == "random":
            CameraClass = RandomCamera
        elif args.emulate == "deterministic":
            CameraClass = DeterministicCamera
        else:
            logger.error("Please emulate with random or deterministic camera")
        
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

        camera = CameraClass(**camera_kwargs)
        self._camera = camera



    def stream(self, url):
        """
        Stream data to tcp server in url
        """
        from baslerpi.web_utils import TCPClient

        host, port = url[1].split(":")
        logger.debug(f"Streaming data to {url}")
        tcp_client = TCPClient(host, int(port))
        tcp_client.daemon = True
        tcp_client.start()
        self.tcp_client = tcp_client
        self.action = "stream" 

        last_tick = 0
        for t_ms, frame in self._camera:
            tcp_client.queue(frame)
            if (t_ms - last_tick) > 1000:
                last_tick = t_ms
                logger.info(f"Computed TCP Client framerate: {tcp_client._count}")
                tcp_client._count = 0
            if tcp_client._stop.is_set():
                print("TCP Client has stopped. Exiting...")
                break

        return 0

    def save(self, path):

        import imgstore

        self.action = "save"
        datetime_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        basedir = os.path.join(path, datetime_str)

        os.makedirs(basedir)
        video_format = "mjpeg/avi"
        self._store = None
        i=0
        chunksize=self._camera._target_framerate * 300

        for t_ms, frame in self._camera:
            if self._store is None:
                self._store = imgstore.new_for_format(video_format, mode='w', basedir=basedir, imgshape=frame.shape, imgdtype=frame.dtype, chunksize=chunksize)

            #b=time.time()
            self._store.add_image(frame, i, t_ms)
            #a=time.time()
            #print(a-b)
            i+=1

        return 0


    def pipe(self):
        """
        Pass obtained data to std output
        """

        logger.debug("Piping data to stdout")
        import cv2
        self.action = "pipe"
        encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
        logging.basicConfig(level=logging.CRITICAL)

        for t_ms, frame in self._camera:
            result, imgencode = cv2.imencode('.jpg', frame, encode_param)
            data = np.array(imgencode)
            binary_data = data.tostring()
            sys.stdout.buffer.write(binary_data)

        return 0

    def preview(self, tl, wh):
        """
        Preview data in a pop up window live
        """
        import cv2
        self.action = "preview"
        logger.debug("Running preview of camera")
        try:
            for t_ms, frame in self._camera:
                cv2.namedwindow("preview")
                cv2.imshow("preview", frame)
                cv2.resizeWindow("preview", *wh)
                cv2.moveWindow("preview", *tl)
                if cv2.waitKey(10) & 0xFF == ord('q'):
                    break

        except KeyboardInterrupt:
            return 0

        return 0

    def close(self):
        logger.debug("Closing baslervid")
        self._camera.close()

        if self.action == "stream":
            self.tcp_client.stop()

        return 0


    def run(self, args):
        """
        Run baslervid by following user's arguments
        """
        
        self._camera.open()

        try:
            if args.preview:
                self.preview(preview[:2], preview[2:4])
            elif args.output is None:
                return
            elif args.output == "-":
                self.pipe()
            elif "://" in args.output:
                url = parse_protocol(args.output)
                self.stream(url)
            else:
                self.save(args.output)

        except KeyboardInterrupt:
            self.close()



def main(args):
    baslervid = BaslerVidClient(args)
    baslervid.run(args)
 
if __name__ == "__main__":
    args = parse_args()

    config = read_config_yaml("conf/logging.yaml")
    logging.config.dictConfig(config)


    main(args)

