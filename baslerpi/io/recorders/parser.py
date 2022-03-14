import argparse
import datetime
import math
from baslerpi.constants import ENCODER_FORMAT_CPU
from .record import RECORDERS

def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser(conflict_handler="resolve")

    ap.add_argument(
        "--config",
        help="Config file in json format",
        default="/etc/flyhostel.conf",
    )
    ap.add_argument(
        "--output",
        default=datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        help="Path to output video (directory for ImgStore). It will be placed in the video folder as stated in the config file. See --config",
    )
    ap.add_argument(
        "--fps",
        type=int,
        help="Frames Per Second of the video",
        required=False,
    )
    ap.add_argument("--sensor", type=str, default=None)
    ap.add_argument("--duration", type=int, default=math.inf, help="Recording duration in seconds")
    ap.add_argument("--encoder", type=str)
    ap.add_argument("--fmt", type=str, default=ENCODER_FORMAT_CPU)
    ap.add_argument("--crf", type=int)
    ap.add_argument(
        "--recorder",
        choices=list(RECORDERS.keys()),
        default="ImgStoreRecorder",
    )
    return ap
