import json
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


def setup(args):
    if args.sensor is None:
        sensor = None
    else:
        sensor = QuerySensor(args.sensor)
    return sensor
