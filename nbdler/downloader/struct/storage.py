# -*- coding: UTF-8 -*-
from ...utils.misc import Component
from collections import defaultdict
from threading import Lock


class BufferStorage(Component):
    """ 缓冲存储器。 """

    def __init__(self):
        self.unsolved = defaultdict(list)
        self._counter = 0
        self._lock = Lock()

    @property
    def count(self):
        """ 获取当前缓存计数。 """
        return self._counter

    def check(self, max_buff):
        """ 检查缓冲是否溢出。 """
        return max_buff <= self._counter

    def store(self, progress, buff):
        """ 存储缓冲。 """
        with self._lock:
            self._counter += len(buff)
            self.unsolved[progress].append(buff)

    def release(self, file):
        """ 释放缓冲。 """
        with self._lock:
            buffer = self.unsolved
            # 将当前的缓冲放入待释放队列，准备进行释放。
            self.unsolved = defaultdict(list)
            counter = self._counter
            self._counter = 0

        for progress, buff_list in buffer.items():
            file.seek(progress.begin + progress.increment_done)
            progress.done(sum([len(i) for i in buff_list]))
            file.writelines(buff_list)

        return counter

    def clear(self):
        """ 清空缓存。"""
        with self._lock:
            self.unsolved = defaultdict(list)
            self._counter = 0

    def __snapshot__(self, base_info=False):
        """ 状态快照。 """
        return {
            'count': self._counter,
        }