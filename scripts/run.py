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

from baslerpi.io.recorders import FFMPEGRecorder, ImgstoreRecorder
from baslerpi.io.recorders.pipeline import TimeAnnotator, Inverter, FPSAnnotator, Masker, BlackFrameCountAnnotator, FrameCountAnnotator, Overlay
from baslerpi.io.cameras import BaslerCamera
from baslerpi.core.base import *
import baslerpi

CAMERAS = {"Basler": BaslerCamera}

PIPELINES = {
    "mask": [Masker, Overlay],
    "standard": [TimeAnnotator, FPSAnnotator, Inverter, Overlay],
    "full": [TimeAnnotator, FPSAnnotator, Inverter, Masker, Overlay],
    "invert": [Inverter, Overlay],
    "framecount": [FrameCountAnnotator],
    "black-framecount": [BlackFrameCountAnnotator],
    "none": []
}

camera_choices = list(CAMERAS.keys())


def get_parser():

    
   
    ap = argparse.ArgumentParser()
    ap.add_argument("camera", choices=camera_choices)
    ap.add_argument("--input", dest="video_path", help="If using OpenCV camera, path to video or 0 for webcam input")
    ap.add_argument("--output", help="Path to output video (directory for ImgStore). It will be placed in the video folder as stated in the config file. See --config")
    ap.add_argument("--framerate", type=int, default=30, help="Frames Per Second of the camera")
    ap.add_argument("--exposure-time", dest="exposure", type=int, default=25000, help="Exposure time in useconds (10^-6 s)")
    ap.add_argument("--fps", type=int, help="Frames Per Second of the video", required=False)
    ap.add_argument("--config", help="Config file in json format", default="/etc/flyhostel.conf")
    ap.add_argument("--verbose", dest="verbose", action="store_true", default=False)
    ap.add_argument("--pipeline", choices = list(PIPELINES.keys()), help="Preprocessing pipeline to be used. For typical data collection, use standard. full will additionally apply a mask, in case you do not wish to include a part of the arena. mask will only do this masking and otherwise leave the input stream untouched.", default="none")
    #ap.add_argument("--mask", dest="mask", action="store_true", default=False)
    #ap.add_argument("--invert", dest="invert", action="store_true", default=True)
    #ap.add_argument("--no-invert", dest="invert", action="store_false", default=True)
    ap.add_argument("-D", "--debug", dest="debug", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("-n", "--dry-run", dest="dry_run", help="Display what would happend but dont actually do it", default=False, action="store_true")
    ap.add_argument("--timeout", type=int, default=30000, help="Camera tries getting a frame for ms after the last successful trial")
    ap.add_argument("--sensor", type=int, default=None)
    gp = ap.add_mutually_exclusive_group()
    gp.add_argument("--duration", type=int, default=300, help="Camera fetches this amount of frames at max")
    gp.add_argument("--maxframes", type=int, default=math.inf, help="Camera fetches frames (s)")

    return ap


def main(args = None):
    

    with open("/etc/baslerpi.yaml" , "r") as fh:
        try:
            logging_config = yaml.safe_load(fh)
            logging.config.dictConfig(logging_config)
        except yaml.YAMLError as error:
            print(error)

    if args is None:
        ap = get_parser()
        args = ap.parse_args()


    DURATION = args.duration if args.maxframes == math.inf else None
    MAXFRAMES = args.maxframes
    
    with open(args.config, "r") as fh:
        config = json.load(fh)
    
    if args.output is None:
        RecorderClass = ImgstoreRecorder
        OUTPUT = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        RecorderClass = FFMPEGRecorder
        OUTPUT = args.output
    
    i = 0
    
    try:
        CameraClass = CAMERAS[args.camera]
    except KeyError:
        print(f"Enter a valid camera class. Valid options are {' '.join(camera_choices)}")
        sys.exit(1)
    
    keys = list(signature(CameraClass).parameters.keys())
    for cls in CameraClass.__bases__:
        keys = keys + list(signature(cls).parameters.keys())
    
    camera_kwargs = {k: getattr(args, k) for k in vars(args) if k in keys}
    
    logging.debug("This are the camera kwargs:")

    for k, v in camera_kwargs.items():
        logging.debug(f"{k} -> {v}")

    camera = CameraClass(**camera_kwargs)
    pipeline = PIPELINES[args.pipeline]
    
    if args.sensor is None:
        sensor=None
    else:
    
        import urllib.request
        from socket import timeout as TimeoutException
    
        class QuerySensor:
            def __init__(self, port):
                self._port = port
    
            def query(self, timeout=1):
                url = f"http://localhost:{self._port}"
                try:
                    req = urllib.request.urlopen(url, timeout=timeout)
                except TimeoutException:
                    logging.warning("Sensor timeout")
                    return None
                except Exception:
                    return None
    
                data_str = req.read().decode("utf-8")
                data = json.loads(data_str)
                data["temperature"] = float(data["temperature"])
                data["humidity"] = float(data["humidity"])
                return data
    
            def get_temperature(self):
                data = self.query()
                return data["temperature"]
    
            def get_humidity(self):
                data = self.query()
                return data["humidity"]
    
        sensor = QuerySensor(args.sensor)
    
    if args.dry_run:
        print(f"I will open media at {args.video_path} and save it to {OUTPUT}")
        print(f"The camera will run at  {args.framerate} and the video will be saved at {args.fps}")
        print(f"The declared pipeline is {pipeline}")
        if DURATION is None:
            print(f"I will collect {MAXFRAMES} frames")
        else:
            print(f"I will collect frames for {DURATION} seconds")
    
    else:
    
        camera.open()
        recorder = RecorderClass(
            camera,
            framerate=args.fps,
            duration=args.duration, maxframes=args.maxframes,
            sensor=sensor,
            verbose=args.verbose)
        if pipeline:
            recorder.build_pipeline(*pipeline)

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
            path=os.path.join(config["videos"]["folder"], OUTPUT),
            fmt = "mjpeg/avi",
            **metadata
        )
        try:
            recorder.start()
            recorder.join()
        except KeyboardInterrupt:
            logging.info("User pressed control-C. Quitting program in a controlled manner!")
            recorder._stop_event.set()
    
        finally:
            recorder.close()
            camera.close()
            recorder.join()

if __name__ == "__main__":
    main()
