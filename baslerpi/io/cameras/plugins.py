import cv2

class ROISMixin:
    """
    
    Needed signatures

    status, image = self._next_image_default()
    width, height = self.resolution   
    """

    ROI_SEGMENTATION_PREVIEW_WIDTH = 1280
    ROI_SEGMENTATION_PREVIEW_HEIGHT = 960

    @staticmethod
    def _crop_roi(image, roi):
        return image[
            int(roi[1]) : int(roi[1] + roi[3]),
            int(roi[0]) : int(roi[0] + roi[2]),
        ]


    @staticmethod
    def _process_roi(r, fx, fy):
        r[0] = int(r[0] * fx)
        r[1] = int(r[1] * fy)
        r[2] = int(r[2] * fx)
        r[3] = int(r[3] * fy)
        roi = tuple(r)
        return roi

    def select_ROIs(self):
        """
        Select 1 or more ROIs
        """
        status, image = self._next_image_default()

        if (
            image.shape[1] > self.ROI_SEGMENTATION_PREVIEW_WIDTH or 
            image.shape[0] > self.ROI_SEGMENTATION_PREVIEW_HEIGHT
        ):
            fx = image.shape[1] / self.ROI_SEGMENTATION_PREVIEW_WIDTH
            fy = image.shape[0] / self.ROI_SEGMENTATION_PREVIEW_HEIGHT

            image = cv2.resize(
                image,
                (
                    self.ROI_SEGMENTATION_PREVIEW_WIDTH,
                    self.ROI_SEGMENTATION_PREVIEW_HEIGHT
                ),
                cv2.INTER_AREA
            )

        rois = cv2.selectROIs("select the area", image)

        rois = [self._process_roi(list(roi), fx, fy) for roi in rois]
        self._rois = rois
        print("Selected ROIs")
        for roi in self._rois:
            print(roi)
        cv2.destroyAllWindows()
        return rois



    def _next_image_rois(self):

        status, image = self._next_image_default()
        if not status:
            return status, (None)

        data = []
        for r in self.rois:
            data.append(self._crop_roi(image, r))
        return status, data


    @property
    def rois(self):
        if self._rois is None:
            try:
                return [(0, 0, *self.resolution)]
            except:
                raise Exception(
                    "Please open the camera before asking for its resolution"
                )
        else:
            return self._rois



class CameraUtils:

    def _count_frames_in_second(self):
        offset = self._time_s % 1000
        if offset < self._last_offset:
            self._last_offset = offset
            self._frames_this_second = 0
        else:
            self._frames_this_second += 1