# -*- coding: UTF-8 -*-

from ...utils.misc import Component
from .misc import Timer


class Progress(Component):
    __slots__ = '_range', 'increment_go', 'increment_done', '_timer'

    def __init__(self, _range, increment_go=0, increment_done=0, increment_time=0):
        if len(_range) == 1:
            _range = (_range[0], None)
        self._range = _range

        if increment_done != increment_go:
            # 存在下载缓冲未写入文件，下载配置文件可能被非正常关闭。尝试回退下载进度。
            increment_done = increment_go

        self.increment_go = increment_go
        self.increment_done = increment_done

        self._timer = Timer(increment_time)

    @property
    def finish_go_flag(self):
        return self.increment_go >= self.length

    @property
    def finish_done_flag(self):
        return self.increment_done >= self.length

    @property
    def finish_flag(self):
        return self.finish_go_flag and self.finish_done_flag

    @property
    def begin(self):
        return self._range[0]

    @property
    def end(self):
        return self._range[1]

    @property
    def length(self):
        try:
            return self._range[1] - self._range[0]
        except TypeError:
            return float('inf')

    @property
    def remaining_go(self):
        return self.length - self.increment_go

    @property
    def remaining_done(self):
        return self.length - self.increment_done

    @property
    def differ(self):
        return self.increment_go - self.increment_done

    @property
    def increment_time(self):
        return self._timer.get_time()

    @property
    def average_speed(self):
        increment_time = self._timer.get_time()
        return self.increment_go / increment_time if increment_time else 0

    @property
    def percent(self):
        return self.increment_go * 100 / self.length

    def go(self, byte_len):
        self.increment_go += byte_len

    def done(self, byte_len):
        self.increment_done += byte_len

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def force_to_finish_go(self):
        """ 由于存在未指定结尾的情况，也就是未指定下载大小的情况。
        那么当下载完全的情况下，允许强制其以当前下载量作为结尾。
        """
        assert self.end == float('inf')
        self._range = (self.begin, self.begin + self.increment_go)

    def reset(self):
        self.increment_go = 0
        self.increment_done = 0

    def slice(self, request_range):
        """ 下载进度切片。"""
        if request_range[0] > self.begin + self.increment_go:
            if request_range[1] != self.end:
                request_range = (request_range[0], self.end)
            if request_range[0] >= request_range[1]:
                request_range = ()
            put_range = request_range
        else:
            put_range = ()

        if put_range:
            self._range = (self._range[0], put_range[0])

        return put_range

    def __repr__(self):
        return '<Progress [{}-{}]> {:.2%}'.format(self.begin, self.end, self.percent / 100)

    def __snapshot__(self):
        return {
            'range': self._range,
            'increment_go': self.increment_go,
            'increment_done': self.increment_done,
            'increment_time': self.increment_time
        }

