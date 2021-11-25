#! /usr/bin/python

import argparse
import sys
import logging
import logging.config
import tempfile

import cv2
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np


from baslerpi.web_utils import TCPServer
from baslerpi.utils import read_config_yaml


temp_file = tempfile.NamedTemporaryFile(
    prefix="flyhostel_", suffix=".jpg"
).name


def save(frame):
    cv2.imwrite(temp_file, frame)


def preview(frame, preview):
    x, y, w, h = preview
    frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
    image = Image.fromarray(np.uint8(frame))
    if img is None:
        img = plt.imshow(image)
    else:
        img.set_data(image)

    plt.pause(0.001)
    logger.debug("Drawing image")
    plt.draw()
    image.verify()
    logger.debug("Image is verified")
    return 0


def main():

    config = read_config_yaml("conf/logging.yaml")
    logging.config.dictConfig(config)
    logger = logging.getLogger(__name__)

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8084)
    ap.add_argument(
        "--no-preview", action="store_false", dest="preview", default=False
    )
    ap.add_argument("--save", action="store_true", dest="save", default=False)
    ap.add_argument(
        "--preview",
        type=int,
        nargs=4,
        dest="preview",
        default=[0, 0, 200, 260],
    )
    args = ap.parse_args()

    tcp_server = TCPServer(args.host, args.port)
    tcp_server.daemon = True
    tcp_server.start()
    img = None
    if args.preview:
        x, y, width, height = args.preview
    if args.save:
        print(temp_file)

    try:
        while True:
            success, frame = tcp_server.dequeue()
            if success:
                if args.preview:
                    preview(frame)
                if args.save:
                    save(frame)

    except KeyboardInterrupt:
        tcp_server.stop()
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
