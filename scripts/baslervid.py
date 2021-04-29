#! /usr/bin/python

"""
A raspivid-like executable to interact with Basler cameras
Key flags should have a behavior identical to raspivid
"""
import argparse
import sys
import math
import re

import baslerpi.utils
from baslerpi.io.cameras.basler_camera import BaslerCamera

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
ap.add_argument("-t", "--timeout", default=5000, help="Control the timeout, in ms, that the video will be recorded")
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

args = ap.parse_args()

if args.print_help:
  ap.print_help()
  sys.exit(0)

camera = BaslerCamera(
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


protocol = parse_protocol(args.output)

if protocol is None:
  if args.output == "-":
    # std out
    pass

  else:
    # normal path to video
    pass



camera.open()
camera.start()
camera.close()
