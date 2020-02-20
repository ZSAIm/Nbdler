# -*- coding: UTF-8 -*-
from threading import Lock
from time import time


class FormatRange:
    """ 请求头范围请求格式。

    :param
        format_dict : 范围格式化字典

    范围关键字：
        begin   : 请求字节开始
        end     : 请求字节结束（不包括当前字节）
        end_with: 请求戒子结束（包括当前字节）
        length  : 请求字节长度

    对于HTTP/S：
        format_dict = {'Range': 'bytes={begin}-{end_with}'}
        将生成请求头域:（若begin=0, end_with=999, length=1000）
            Range: bytes=0-999

    """
    def __init__(self, format_dict):
        self._full_formats = format_dict

        self._query_dict = {}
        self._header_dict = {}

        for i, j in self._full_formats.items():
            if i[0] != '&':
                self._header_dict[i] = j
            else:
                self._query_dict[i] = j

    @staticmethod
    def _format(r, format_dict):
        ret_dict = format_dict.copy()
        for k, v in format_dict.items():
            begin = r[0]
            end = r[1] or ''
            end_with = r[1] - 1 if r[1] is not None and r[1] > 0 else ''
            length = (r[1] or 0) - r[0]
            ret_dict[k] = v.format(begin=begin, end=end, end_with=end_with, length=length)
        return ret_dict

    def get_headers(self, r):
        return self._format(r, self._header_dict)

    def get_query(self, r):
        return self._format(r, self._query_dict)

    def __iter__(self):
        return iter(self._full_formats.items())


class Timer:
    """ 简单的计时器。 """
    __slots__ = '_start', '_inc', '_end'

    def __init__(self, inc_time=0):
        self._start = None
        self._inc = inc_time
        self._end = None

    def start(self):
        if not self._start:
            self._end = None
            self._start = time()

    def stop(self):
        if self._start:
            self._end = time()
            self._inc += self._end - self._start
            self._start = None

    def get_time(self):
        return time() - self._start + self._inc if self._start else self._inc

    def clear(self):
        self._inc = 0


class RealtimeSpeed:
    """ 使用滑动平均算法得到的实时速度。 """

    def __init__(self, depth=8):
        """
        :param
            depth   : 滑动平均的深度
        """
        self._speed = 0
        self._prv_size = 0
        self._prv_time = None
        self._lock = Lock()
        self._depth = depth
        self._moving_list = [0 for _ in range(depth)]

    def is_stopped(self):
        return self._prv_time is None

    def start(self, start):
        with self._lock:
            self._prv_size = start
            self._prv_time = time()
            self._speed = 0

    def stop(self):
        with self._lock:
            self._prv_time = None
            self._speed = 0
            self._prv_size = 0

    def refresh(self, cur_length):
        """ 刷新实时速度计。"""
        with self._lock:
            cur_time = time()
            prv = self._prv_time
            if prv is not None:
                incr_time = cur_time - prv
                speed = (cur_length - self._prv_size) / (incr_time or float('inf'))
                self._prv_time = cur_time
                self._prv_size = cur_length
                # 更新滑动平均数据
                self._moving_list.pop()
                self._moving_list.insert(0, speed)
                # 计算滑动平均数据
                self._speed = sum(self._moving_list) / self._depth

    def get_speed(self):
        return self._speed if not self.is_stopped() else 0



