import argparse
import datetime
import logging
import os.path
import sys
from .base import *

logger = logging.getLogger(__name__)
import cv2
import numpy as np

from baslerpi.io.cameras import BaslerCamera
from baslerpi.io.recorders import Recorder
from baslerpi.processing.compressor import Compressor

ap = argparse.ArgumentParser()

ap.add_argument(
    "--output-dir", type=str, default="/1TB/Cloud/Lab/Projects/FlyBowl/videos"
)
ap.add_argument("--duration", type=int, help="(s)")
ap.add_argument("--encoder", type=str)
ap.add_argument("--crf", type=int)
ap.add_argument("--compress", dest="compress", action="store_true")

args = vars(ap.parse_args())

output_dir = args["output_dir"]
crf = args["crf"]
encoder = args["encoder"]
duration = args["duration"]
compress = args["compress"]

recorder_kwargs = {
    k: args[k]
    for k in args.keys()
    if k in ["duration", "encoder", "crf"] and args[k] is not None
}
print(recorder_kwargs)

filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
print(filename)


camera = BaslerCamera(framerate=30)
camera.open()

if compress:
    compressor = Compressor(ntargets=3, shape=camera.shape)
else:
    compressor = None
recorder = Recorder(camera, compressor=compressor, **recorder_kwargs)


answer = input("Add now any metadata that needs to be entered manually: ")

metadata = {
    "exposure-time": camera.exposuretime,
    "notes": answer,
    "python-version": sys.version,
    "baslerpi-version": baslerpi.__version__,
    "imgstore-version": imgstore.__version__, # for imgstore writer
    "skvideo-version": skvideo.__version__, # for ffmpeg writer
    "cv2-version": cv2.__version__
    }


recorder.open(
    filename = os.path.join(output_dir, f"{filename}.avi"),
    **metadata
)

try:
    recorder.start()
    recorder.join()
except KeyboardInterrupt:
    recorder._stop_event.set()
    logger.info("Quitting...")

recorder.close()
camera.close()
