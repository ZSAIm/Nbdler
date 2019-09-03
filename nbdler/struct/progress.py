

from __future__ import division
from nbdler.struct.dump import ProgressDumpedData
from nbdler.struct.time_speed import AccumulatedTime


class Progress:
    def __init__(self, _range, go_inc: int = 0, done_inc: int = 0):
        if len(_range) == 1:
            _range = (_range[0], None)
        self.range = _range

        if done_inc != go_inc:
            done_inc = go_inc
        self.go_inc = go_inc
        self.done_inc = done_inc

        self._acum_time = AccumulatedTime(0)

        self._retrieve_buff = []

    @property
    def go_finishflag(self):
        return self.go_inc >= self.length

    @property
    def done_finishflag(self):
        return self.done_inc >= self.length

    @property
    def finishflag(self):
        return self.go_finishflag and self.done_finishflag

    @property
    def begin(self):
        return self.range[0]

    @property
    def end(self):
        return self.range[1]

    @property
    def length(self):
        try:
            return self.range[1] - self.range[0]
        except TypeError:
            return float('inf')

    @property
    def go_remain(self):
        return self.length - self.go_inc

    @property
    def done_remain(self):
        return self.length - self.done_inc

    @property
    def differ(self):
        return self.go_inc - self.done_inc

    def getavgspeed(self):
        return self.go_inc / self._acum_time.getinctime()

    def go(self, byte_len):
        self.go_inc += byte_len

    def done(self, byte_len):
        self.done_inc += byte_len

    def buffer(self, b):
        self._retrieve_buff.append(b)

    def fetch_buffer(self):
        while True:
            try:
                buff = self._retrieve_buff.pop(0)
                self.done(len(buff))
                yield buff
            except IndexError:
                break

    def is_empty_buff(self):
        return self._retrieve_buff == []

    def close(self):
        self._acum_time.stop()

    def start(self):
        self._acum_time.start()

    def stop(self):
        self._acum_time.stop()

    def force_to_finish_go(self):
        self.range = (self.begin, self.begin + self.go_inc)

    def clear(self):
        self.go_inc = 0
        self.done_inc = 0
        self._retrieve_buff = []

    def slice_check(self, req_range):
        if req_range[0] > self.begin + self.go_inc:
            if req_range[1] != self.end:
                req_range = (req_range[0], self.end)
            if req_range[0] >= req_range[1]:
                req_range = ()
            put_range = req_range
        else:
            put_range = ()

        if put_range:
            self.range = (self.range[0], put_range[0])

        return put_range

    def __repr__(self):
        return "[%d-%d] %d/%d,finish=%s" % (self.begin, self.end, self.go_inc, self.length, self.finishflag)

    def dump_data(self):
        return ProgressDumpedData(range=self.range, go_inc=self.go_inc,
                                  done_inc=self.done_inc)


