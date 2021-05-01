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


def main():

    config = read_config_yaml("conf/logging.yaml")
    logging.config.dictConfig(config)
    logger = logging.getLogger(__name__)

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port",   type=int, default=8084)
    ap.add_argument("--width",  type=int, default=200)
    ap.add_argument("--height", type=int, default=260)
    args = ap.parse_args()

    temp_file = tempfile.NamedTemporaryFile(prefix="flyhostel_", suffix=".jpg").name

    tcp_server = TCPServer(args.host, args.port)
    tcp_server.daemon = True
    tcp_server.start()
    img = None
    try:
        while True:
            success, frame = tcp_server.dequeue()
            if success:
                cv2.imwrite(temp_file, frame)
                frame = cv2.resize(frame, (args.width, args.height), interpolation=cv2.INTER_AREA)
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

    except KeyboardInterrupt:
        tcp_server.stop()
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
