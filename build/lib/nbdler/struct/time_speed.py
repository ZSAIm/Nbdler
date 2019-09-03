from time import perf_counter


class AccumulatedTime:
    __slots__ = ('_start_time', '_inc_time', '_end_time')

    def __init__(self, inc_time=0):
        self._start_time = None
        self._inc_time = inc_time
        self._end_time = None

    def start(self):
        if not self._start_time:
            self._end_time = None
            self._start_time = perf_counter()

    def stop(self):
        if self._start_time:
            self._end_time = perf_counter()
            self._inc_time += self._end_time - self._start_time
            self._start_time = None

    def getinctime(self):
        return perf_counter() - self._start_time + self._inc_time if self._start_time else self._inc_time

    def clear(self):
        self._inc_time = 0


class InstSpeedMaker:
    __slots__ = ('_speed', '_prv_size', '_prv_time')

    def __init__(self):
        self._speed = 0
        self._prv_size = 0
        self._prv_time = None

    def start(self, start):
        self._prv_size = start
        self._prv_time = perf_counter()
        self._speed = 0

    def stop(self):
        self._prv_time = None
        self._speed = 0
        self._prv_size = 0

    def capture(self, cur_length):
        cur_time = perf_counter()
        self._speed = (cur_length - self._prv_size) / (cur_time - self._prv_time)
        self._prv_time = cur_time
        self._prv_size = cur_length

    def getspeed(self):
        return self._speed