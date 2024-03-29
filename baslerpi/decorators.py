import logging
import traceback
import re

from functools import wraps
from time import time

from pypylon import genicam

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def drive_basler(f):
    def wrapper(*args, **kwargs):
        self = args[0]
        try:
            return f(*args, **kwargs)
        except (
            genicam._genicam.AccessException,
            genicam._genicam.LogicalErrorException,
        ) as error:
            print(error.args)
            match_objects = [
                re.match(".*(ExposureTime).*", error.args[0]),
                re.match(".*(FrameRate).*", error.args[0]),
            ]
            try:
                attribute = [
                    e.groups()[0].lower() for e in match_objects if e is not None
                ][0]

                res = getattr(self, "_" + attribute)

                # logging.debug(error)
                # logging.debug(traceback.print_exc())
                logging.warning(f"Could not read/write {attribute}")
                logging.debug("I will proceed nominal")
                return res
            except Exception as error:
                logger.warning(error)
                return None


    return wrapper


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        # print('func:%r took: %2.5f msec' % \
        #   (f.__name__, (te-ts)*1000))
        # print('func:%r args:[%r, %r] took: %2.5f msec' % \
        #   (f.__name__, args, kw, (te-ts)*1000))
        return result
    return wrap