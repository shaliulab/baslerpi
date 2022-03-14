import cv2

from .basler import BaslerCamera
from .parser import get_parser

def setup(args=None, camera_name="Basler", idx=0, **kwargs):

    camera_kwargs = {
        "framerate": getattr(
            args,
            f"{camera_name.lower()}_framerate",
            getattr(args, "framerate"),
        ),
        "exposure": getattr(
            args, f"{camera_name.lower()}_exposure", getattr(args, "exposure")
        ),
        "width": args.width,
        "height": args.height,
        "resolution_decrease": args.resolution_decrease,
    }
    camera_kwargs.update(kwargs)
    if camera_name == "Basler":
        camera = BaslerCamera(**camera_kwargs, idx=idx)
    return camera


def run(camera, queue=None, preview=False):

    try:
        for timestamp, all_rois in camera:

            for frame in all_rois:
                print(
                    "Basler camera reads: ",
                    timestamp,
                    frame.shape,
                    frame.dtype,
                    camera.computed_framerate,
                )
                if queue is not None:
                    queue.put((timestamp, frame))

                frame = cv2.resize(
                    frame,
                    (frame.shape[1] // 3, frame.shape[0] // 3),
                    cv2.INTER_AREA,
                )
                if preview:
                    cv2.imshow("Basler", frame)
                    if cv2.waitKey(1) == ord("q"):
                        break

    except KeyboardInterrupt:
        return


def setup_and_run(args, **kwargs):

    camera = setup(args)
    maxframes = getattr(args, "maxframes", None)
    if args.select_rois:
        camera.select_ROIs()
    run(camera, preview=args.preview, **kwargs)


def main(args=None, ap=None):
    """
    Initialize a BaslerCamera
    """

    if args is None:
        ap = get_parser(ap=ap)
        args = ap.parse_args()

    setup_and_run(args)


if __name__ == "__main__":
    main()
