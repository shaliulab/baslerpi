# import cv2
# from .basler import BaslerCamera


# class BaslerCameraDLC(BaslerCamera, DLCCamera):
#     """
#     A clone of BaslerCamera where its arguments are explicit and not inherited from abstract classes
#     """

#     def __init__(
#         self,
#         *args,
#         id=0,
#         resolution="2592x1944",
#         exposure=15000,
#         gain=0,
#         rotate=0,
#         crop=None,
#         fps=30,
#         use_tk_display=False,
#         display_resize=1.0,
#         drop_each=1,
#         use_wall_clock=True,
#         timeout=3000,
#         **kwargs
#     ):

#         resolution = resolution.split("x")

#         DLCCamera.__init__(
#             self,
#             id,
#             resolution=resolution,
#             exposure=exposure,
#             gain=gain,
#             rotate=rotate,
#             crop=crop,
#             fps=fps,
#             use_tk_display=use_tk_display,
#             display_resize=display_resize,
#         )

#         # this bypasses the __init__ method of BaslerCamera
#         # de facto making the BaslerCamera part a composition, not an inheritance
#         super(BaslerCamera, self).__init__(
#             *args,
#             drop_each=drop_each,
#             use_wall_clock=use_wall_clock,
#             timeout=timeout,
#             framerate=fps,
#             width=resolution[0],
#             height=resolution[1],
#             **kwargs
#         )

#     def __getstate__(self):
#         d = self.__dict__
#         attrs = dict(d)
#         camera = attrs.pop("camera", None)
#         return attrs

#     def __setstate__(self, d):
#         self.__dict__ = d

#     def configure(self):
#         super().configure()
#         return True

#     def set_capture_device(self):
#         return self.open()

#     def close_capture_device(self):
#         return self.close()

#     @staticmethod
#     def arg_restrictions():
#         arg_restrictions = {"use_wall_clock": [True, False]}
#         return arg_restrictions

#     def get_image(self):
#         frame = self._next_image()
#         if self.crop is not None:
#             frame = frame[
#                 self.crop[2] : self.crop[3],
#                 self.crop[0] : self.crop[1],
#             ]

#         if len(frame.shape) == 2 or frame.shape[2] == 1:
#             frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
#         return frame


# class BaslerCameraDLCCompatibility(BaslerCameraDLC):
#     def __init__(self, *args, **kwargs):

#         if "framerate" in kwargs:
#             kwargs["fps"] = int(kwargs.pop("framerate") or 30)

#         if "height" in kwargs and "width" in kwargs:
#             kwargs["resolution"] = "x".join(
#                 [
#                     str(kwargs.pop("width") or 2592),
#                     str(kwargs.pop("height" or 1944)),
#                 ]
#             )

#         if "shutter" in kwargs:
#             kwargs["exposure"] = int(kwargs.pop("shutter", 15000))

#         if "iso" in kwargs:
#             kwargs["gain"] = int(kwargs.pop("iso") or 0)

#         print("Loading camera...")
#         super().__init__(*args, **kwargs)

#     def close(self):
#         print("Closing camera...")
#         super().close()

#     def open(self):
#         print("Opening camera...")
#         return super().open()
