# -*- coding: UTF-8 -*-

# from ..utils.misc import Component
# # from .misc import Timer


class Progress:
    __slots__ = '_range', 'walk_length', 'done_length', '_timer'

    def __init__(self, range, walk_length=0, done_length=0, increment_time=0):
        begin, end = range
        self._range = range

        if done_length != walk_length:
            # 存在下载缓冲未写入文件，下载配置文件可能被非正常关闭。尝试回退下载进度。
            done_length = walk_length

        self.walk_length = walk_length
        self.done_length = done_length

    def is_walk_finished(self):
        return self.walk_length >= self.total_length

    def is_done_finished(self):
        return self.done_length >= self.total_length

    def is_finished(self):
        return self.is_walk_finished() and self.is_done_finished()

    @property
    def range(self):
        return self._range

    @property
    def begin(self):
        return self._range[0]

    @property
    def end(self):
        return self._range[1]

    @property
    def total_length(self):
        try:
            return self._range[1] - self._range[0]
        except TypeError:
            return float('inf')

    @property
    def walk_left(self):
        return self.total_length - self.walk_length

    @property
    def done_left(self):
        return self.total_length - self.done_length

    @property
    def differ(self):
        return self.walk_length - self.done_length

    @property
    def time_length(self):
        return 0

    @property
    def average_speed(self):
        return

    @property
    def percent_complete(self):
        return self.walk_length * 100 / self.total_length

    def walk(self, byte_len):
        self.walk_length += byte_len

    def done(self, byte_len):
        self.done_length += byte_len

    def start(self):
        pass

    def stop(self):
        pass

    def set_walk_finish(self):
        """ 由于存在未指定结尾的情况，也就是未指定下载大小的情况。
        那么当下载完全的情况下，允许强制其以当前下载量作为结尾。
        """
        assert self.end is None
        self._range = (self.begin, self.begin + self.walk_length)

    def reset(self):
        self.walk_length = 0
        self.done_length = 0

    def slice(self, request_range):
        """ 下载进度切片。"""
        put_begin, put_end = request_range
        if put_begin > self.begin + self.walk_length:
            if put_end != self.end:
                put_end = self.end
            if put_begin >= put_end:
                return None
        else:
            return None

        self._range = (self._range[0], put_begin)
        return put_begin, put_end

    def __repr__(self):
        return '<Progress [{}-{}]> {:.2%}'.format(self.begin, self.end, self.percent_complete / 100)

    def __iter__(self):
        return iter([self._range, self.walk_length, self.done_length])
