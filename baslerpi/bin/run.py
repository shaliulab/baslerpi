import argparse
import datetime
import logging
import logging.config
import json
import math
import os.path
import json

from baslerpi.io.cameras.basler_camera import setup as setup_camera
from baslerpi.io.cameras.basler_camera import get_parser as camera_parser
from baslerpi.io.recorders.record import setup as setup_recorder
from baslerpi.io.recorders.record import RECORDERS
from baslerpi.io.recorders.record import get_parser as recorder_parser
from baslerpi.io.recorders.record import run as run_recorder
from baslerpi.web_utils.sensor import setup as setup_sensor


LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}
logger = logging.getLogger(__name__)

def setup_logger(level):

    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    console = logging.StreamHandler()
    console.setLevel(level)
    logger.addHandler(console)

def load_config(args):
    with open(args.config, "r") as fh:
        config = json.load(fh)

    return config


def setup(args):

    level = LEVELS[args.verbose]
    setup_logger(level=level)
    config = load_config(args)
    sensor = setup_sensor(args)
    camera = setup_camera(args)
    camera.open()
    recorder = setup_recorder(args, camera, sensor)
    return config, recorder


def setup_and_run(args, **kwargs):
    
    config, recorder = setup(args)
    output = os.path.join(config["videos"]["folder"], args.output)
    run_recorder(recorder, fmt=args.fmt, path=output, **kwargs)


def main(args=None, ap=None):
    
    if args is None:
        ap = recorder_parser(ap=ap)
        ap = camera_parser(ap=ap)
        args = ap.parse_args()

    setup_and_run(args, output=args.output)


if __name__ == "__main__":
    main()
