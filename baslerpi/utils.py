import baslerpi
import skvideo
import cv2
import sys
import imgstore
import yaml


def parse_protocol(x):

    supported_protocols = ["tcp", "udp"]
    res = x.split("://")
    if len(res) == 2:
        protocol, url = res
    else:
        return None

    if protocol in supported_protocols:
        return (protocol, url)

    else:
        raise Exception(f"Protocol {protocol} not supported")


def read_config_yaml(path):
    with open(path, "r") as stream:
        config = yaml.load(stream, Loader=yaml.FullLoader)
    return config


def document_for_reproducibility(recorder):

    metadata = {
        "exposure-time": recorder.camera.exposuretime,
        "framerate": recorder.camera.framerate,
        "python-version": sys.version,
        "baslerpi-version": baslerpi.__version__,
        "imgstore-version": imgstore.__version__,  # for imgstore writer
        "skvideo-version": skvideo.__version__,  # for ffmpeg writer
        "cv2-version": cv2.__version__,
    }

    return metadata
