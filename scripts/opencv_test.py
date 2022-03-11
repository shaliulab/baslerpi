# ===============================================================================
#    This sample illustrates how to grab and process images using the CInstantCamera class.
#    The images are grabbed and processed asynchronously, i.e.,
#    while the application is processing a buffer, the acquisition of the next buffer is done
#    in parallel.
#
#    The CInstantCamera class uses a pool of buffers to retrieve image data
#    from the camera device. Once a buffer is filled and ready,
#    the buffer can be retrieved from the camera object for processing. The buffer
#    and additional image data are collected in a grab result. The grab result is
#    held by a smart pointer after retrieval. The buffer is automatically reused
#    when explicitly released or when the smart pointer object is destroyed.
# ===============================================================================
from pypylon import pylon
from pypylon import genicam
import cv2

import sys

import time

# The exit code of the sample application.
exitCode = 0


def main():

    last_tick = 0
    accum = 0

    try:
        # Create an instant camera object with the camera device found first.
        camera = pylon.InstantCamera(
            pylon.TlFactory.GetInstance().CreateFirstDevice()
        )
        camera.Open()

        # Print the model name of the camera.
        print("Using device ", camera.GetDeviceInfo().GetModelName())

        # demonstrate some feature access
        new_width = camera.Width.GetValue() - camera.Width.GetInc()
        if new_width >= camera.Width.GetMin():
            camera.Width.SetValue(new_width)

        # The parameter MaxNumBuffer can be used to control the count of buffers
        # allocated for grabbing. The default value of this parameter is 10.
        camera.MaxNumBuffer = 5

        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        camera.AcquisitionFrameRateEnable.SetValue(True)
        camera.AcquisitionFrameRate.SetValue(30.0)

        # Camera.StopGrabbing() is called automatically by the RetrieveResult() method
        # when c_countOfImagesToGrab images have been retrieved.
        while camera.IsGrabbing():
            # Wait for an image and then retrieve it. A timeout of 5000 ms is used.
            grabResult = camera.RetrieveResult(
                5000, pylon.TimeoutHandling_ThrowException
            )

            # Image grabbed successfully?
            if grabResult.GrabSucceeded():
                # Access the image data.
                print("SizeX: ", grabResult.Width)
                print("SizeY: ", grabResult.Height)
                img = grabResult.Array
                last_t = time.time()
                if last_t > (last_tick + 1):
                    text = f"FPS={accum}"
                    last_tick = last_t
                    accum = 0
                else:
                    accum += 1
                img = img[::-1, ::-1]
                img = cv2.resize(img, (3816 // 3, 2160 // 3), cv2.INTER_AREA)
                img = cv2.putText(
                    img, text, (100, 100), cv2.QT_FONT_NORMAL, 1, 255, 2
                )
                cv2.imshow("img", img)
                if cv2.waitKey(1) == ord("q"):
                    break
            else:
                print(
                    "Error: ",
                    grabResult.ErrorCode,
                    grabResult.ErrorDescription,
                )
            grabResult.Release()
        camera.Close()

    except genicam.GenericException as e:
        # Error handling.
        print("An exception occurred.")
        print(e.GetDescription())
        exitCode = 1
    except Exception as error:
        print(error)


if __name__ == "__main__":
    main()
