import time

class TimeUtils:
    
    @property
    def running_for_seconds(self):
        return time.time() - self.start_time