# Modified by smartbuilds.io
# Date: 27.09.20
# Desc: This web application serves a motion JPEG stream
# main.py
# import the necessary packages
from flask import Flask, render_template, Response, request
from camera import Camera
import time
import threading
import os
import logging

logger = logging.getLogger("baslerpi.io.cameras")
logger.propagate = True
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
logger.setLevel(logging.INFO)
logger.addHandler(sh)

camera = Camera(timeout=0)
camera.open()

# App Globals (do not edit)
app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")  # you can customze index.html here


def gen(camera):
    # get camera frame
    frame = camera.get_frame()
    yield (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n"
    )


@app.route("/video_feed")
def video_feed():
    return Response(
        gen(camera), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":

    app.run(host="0.0.0.0", debug=True)
