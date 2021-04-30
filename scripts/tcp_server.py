import argparse
import sys
import logging
import logging.config

from baslerpi.web_utils import TCPServer
from baslerpi.utils import read_config_yaml

config = read_config_yaml("conf/logging.yaml")
logging.config.dictConfig(config)

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="0.0.0.0")
ap.add_argument("--port", default=8084)
args = ap.parse_args()


if __name__ == "__main__":

    tcp_server = TCPServer(args.host, args.port)
    tcp_server.daemon = True
    tcp_server.start()
    try:
        while True:
            success, frame = tcp_server.dequeue()
            if success:
                print(frame.shape)

    except KeyboardInterrupt:
        tcp_server.stop()
        cv2.destroyAllWindows()

    sys.exit(0)

