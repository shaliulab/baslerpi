from .core import BaseRecorder
from .mixins import FFMPEGMixin
from .imgstore import ImgStoreRecorder

class FFMPEGRecorder(FFMPEGMixin, BaseRecorder):


    def __init__(self, *args, crf="18", **kwargs):
        super().__init__(*args, **kwargs)
        self._crf = crf


    @property
    def outputdict(self):
        return {
            "-r": str(self._framerate),
            "-crf": str(self._crf),
            "-vcodec": str(self._encoder),
        }

    @property
    def inputdict(self):
        return {"-t": str(self._duration)}




RECORDERS = {
    "FFMPEGRecorder": FFMPEGRecorder,
    "ImgStoreRecorder": ImgStoreRecorder,
    # "OpenCVRecorder": BaseRecorder,
}