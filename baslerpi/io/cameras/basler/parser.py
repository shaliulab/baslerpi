import argparse
import math

def get_parser(ap=None):

    if ap is None:
        ap = argparse.ArgumentParser()

    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--camera-name", dest="camera_name", default="Basler")
    ap.add_argument(
        "--height",
        type=int,
        default=2160,
    )
    ap.add_argument(
        "--resolution-decrease",
        dest="resolution_decrease",
        type=float,
        default=None,
    )
    ap.add_argument(
        "--framerate",
        type=int,
        default=30,
        help="Frames Per Second of the camera",
    )
    ap.add_argument(
        "--exposure-time",
        dest="exposure",
        type=int,
        default=25000,
        help="Exposure time in useconds (10^-6 s)",
    )
    ap.add_argument("--preview", action="store_true", default=False)
    ap.add_argument(
        "--maxframes",
        type=int,
        default=math.inf,
        help="Camera fetches frames (s)",
    )

    ap.add_argument(
        "--select-rois",
        default=False,
        dest="select_rois",
        action="store_true",
    )
    return ap
