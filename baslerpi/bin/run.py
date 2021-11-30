import logging
import logging.config
import json
import os.path
import json
import sys

from baslerpi.io.cameras.basler_camera import (
    get_parser as camera_parser,
)

from baslerpi.io.recorders.record import get_parser as recorder_parser
from baslerpi.core.monitor import run as run_monitor
from baslerpi.core import Monitor

LEVELS = {"DEBUG": 0, "INFO": 10, "WARNING": 20, "ERROR": 30}
logger = logging.getLogger(__name__)
recorder_logger = logging.getLogger("baslerpi.io.record")
recorder_logger.setLevel(logging.DEBUG)


def setup_logger(level):

    logger = logging.getLogger(__name__)
    # logger.setLevel(level)
    recorder_logger.setLevel(level)
    console = logging.StreamHandler()
    console.setLevel(level)
    logger.addHandler(console)
    recorder_logger.addHandler(console)


def load_config(args):
    with open(args.config, "r") as fh:
        config = json.load(fh)

    return config


def setup(args, monitorClass=Monitor, **kwargs):

    level = LEVELS[args.verbose]
    setup_logger(level=level)
    config = load_config(args)
    monitor = monitorClass(camera_name=args.camera_name, input_args=args,  **kwargs)
    return config, monitor


def setup_and_run(args, **kwargs):

    config, monitor = setup(args)
    output = os.path.join(config["videos"]["folder"], args.output)
    run_monitor(monitor, fmt=args.fmt, path=output, **kwargs)


def main(args=None, ap=None):

    if args is None:
        ap = recorder_parser(ap=ap)
        ap = camera_parser(ap=ap)
        args = ap.parse_args()

    setup_and_run(args)
    sys.exit(0)


if __name__ == "__main__":
    main()
