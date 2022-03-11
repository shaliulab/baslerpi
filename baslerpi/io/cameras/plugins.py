import logging
import cv2

logger = logging.getLogger("baslerpi.io.camera")

class ROISMixin:

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

        if self.is_open():

            img = self._next_image_default()[0]
            if self.resolution[0] > 1280 or self.resolution[1] > 960:
                fx = self.resolution[0] / 1280
                fy = self.resolution[1] / 960
                img = cv2.resize(img, (1280, 960), cv2.INTER_AREA)
            rois = cv2.selectROIs("select the area", img)

            rois = [self._process_roi(list(roi), fx, fy) for roi in rois]
            self._rois = rois
            print("Selected ROIs")
            for roi in self._rois:
                print(roi)
            cv2.destroyAllWindows()
            return rois

        else:
            logger.warning(f"{self} is not open")
            return None


    def _next_image_rois(self):

        status, image = self._next_image_default()
        if not status:
            return status, (None)

        data = []
        for r in self.rois:
            data.append(self._crop_roi(image, r))
        return status, data



class CameraUtils:

    def _count_frames_in_second(self):
        offset = self._time_s % 1000
        if offset < self._last_offset:
            self._last_offset = offset
            self._frames_this_second = 0
        else:
            self._frames_this_second += 1