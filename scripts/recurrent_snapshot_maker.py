import logging
import math
import time
logging.basicConfig(level=logging.INFO)

from baslerpi.io.cameras import BaslerCamera

import argparse
import json
import datetime
import os.path
from inspect import signature
import cv2


ap = argparse.ArgumentParser()
ap.add_argument("--input", dest="video_path", help="If using OpenCV camera, path to video or 0 for webcam input")
ap.add_argument("--output", help="Path to output video (directory for ImgStore). It will be placed in the video folder as stated in the config file. See --config")
ap.add_argument("--exposure-time", dest="exposuretime", type=int, default=15000, help="Exposure time in useconds (10^-6 s)")
ap.add_argument("--frequency", type=int, help="Seconds between shots")
ap.add_argument("--timeout", type=int, default=30000, help="Camera tries getting a frame for ms after the last successful trial")
ap.add_argument("--config", help="Config file in json format", default="/etc/flyhostel.conf")
ap.add_argument("--verbose", dest="verbose", action="store_true", default=False)
ap.add_argument("-D", "--debug", dest="debug", action="store_true")
ap.add_argument("-n", "--dry-run", dest="dry_run", help="Display what would happend but dont actually do it", default=False, action="store_true")

gp = ap.add_mutually_exclusive_group()
gp.add_argument("--duration", type=int, default=300, help="Camera fetches this amount of frames at max")
gp.add_argument("--maxframes", type=int, default=math.inf, help="Camera fetches frames (s)")


args = ap.parse_args()

with open(args.config, "r") as fh:
    config = json.load(fh)

i = 0

keys = list(signature(BaslerCamera).parameters.keys())
for cls in BaslerCamera.__bases__:
    keys = keys + list(signature(cls).parameters.keys())

camera_kwargs = {k: getattr(args, k) for k in vars(args) if k in keys}

print(camera_kwargs)
camera = BaslerCamera(**camera_kwargs)

last_tick = 0

while True:
    
    try:

        now = time.time()
    
        if (now - last_tick) > args.frequency:
    
            try:
                camera.open()
                frame = camera._next_image()
                output_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_baslerpi.png"
                output_path = os.path.join(args.output, output_filename)
                logging.info("Writing image")
                cv2.imwrite(output_path, frame)
                camera.close()
                last_tick = now
    
            except Exception as error:
                print(error)
                if camera.is_open():
                    camera.close()
        else:
            time.sleep(1)
    
    except KeyboardInterrupt:
        if camera.is_open():
            camera.close()
        break


