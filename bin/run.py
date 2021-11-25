import logging
import logging.config
import math
from inspect import signature
import argparse
import json
import datetime
import yaml
import os.path
import sys

from baslerpi.io.recorders import setup_recorder
from baslerpi.io.recorders import get_parser as recorder_parser
from baslerpi.io.cameras import setup_camera
from baslerpi.io.cameras import get_parser as camera_parser


def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        help="Config file in json format",
        default="/etc/flyhostel.conf",
    )
    ap.add_argument("-D", "--debug", dest="debug", action="store_true")
    ap.add_argument("--preview", action="store_true")
    return ap


def setup_logging():

    with open("/etc/baslerpi.yaml", "r") as fh:
        try:
            logging_config = yaml.safe_load(fh)
            logging.config.dictConfig(logging_config)
        except yaml.YAMLError as error:
            raise error

    return logging


def load_config(args):
    with open(args.config, "r") as fh:
        config = json.load(fh)

    return config


def setup(args):

    logging = setup_logging()
    config = load_config(args)
    RecorderClass, output = setup_recorder(args)
    camera = setup_camera(args)
    camera.open()
    recorder = setup_recorder(camera, sensor, args)
    
    output = os.path.join(config["videos"]["folder"], output)
    recorder.open(
        path=output, fmt=args.fmt
    )

    return recorder


def run(recorder):

    try:
        recorder.start()
        recorder.join()
    except KeyboardInterrupt:
        recorder._stop_event.set()

    finally:
        recorder.close()
        recorder.join()


def main(args=None, ap=None):

    if args is None:
        ap = get_parser(ap)
        args = ap.parse_args()

    recorder = setup(args)
    run(recorder)


if __name__ == "__main__":

    ap = camera_parser()
    ap = recorder_parser(ap=ap)
    main(ap=ap)
