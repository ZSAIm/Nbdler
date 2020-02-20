# -*- coding: UTF-8 -*-

from eventdriven import session, Controller, ControllerPool, MappingBlueprint
from eventdriven.adapter import Timer, Subprocess, EventPending, AbstractAdapter
from eventdriven.adapter.timer import EVT_DRI_TIMING
from eventdriven.adapter.subprocess import EVT_WORKER_PREPARE
from threading import Lock, Condition

__all__ = [
    'Controller', 'ControllerPool', 'MappingBlueprint', 'session',
    'Timer', 'Subprocess', 'Semaphore', 'EventPending',
    'EVT_DRI_TIMING', 'EVT_WORKER_PREPARE'
]


class Semaphore(AbstractAdapter):
    """ 下载限流信号量适配器。 """
    def __init__(self):
        self._cond = Condition(Lock())
        # 记录被获取的锁，负数代表获取的锁的数量，正数代表剩余可通过的锁的数量。
        self._value = 0
        self._opened = False
        self._partial = 0

    def __enter__(self):
        self._cond.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cond.release()

    def open(self):
        self._opened = True

    def close(self):
        self._opened = False
        self.release_all()

    def __patch__(self):
        self._parent.acquire = self.acquire
        self._parent.release = self.release

    def __run__(self):
        self._value = 0

    def __close__(self):
        self.close()

    def __len__(self):
        """ 返回已获得的锁数量。"""
        return 0 if self._value >= 0 else int(-self._value)

    def acquire(self):
        if self._opened:
            with self._cond:
                # 如果存在可释放量，直接通过；否则，获取锁，等待释放。
                self._value -= 1
                if self._value < 0:
                    self._cond.wait()

    def release(self, n):
        """ 每一次释放，都将重置释放量的值。
        :param
            n : 释放的量。允许使用float类型作为值传递，
                提供浮点的小数部分具有累计效应。这是为了解决当限速小于或者与下载粒度相近的情况下
                一直处于流量被锁的的问题。
        """
        if self._opened:
            with self._cond:
                if self._value < 0:
                    # 小数点部分累加。
                    self._partial += n % 1
                    n = int(n)
                    if self._partial >= 1:
                        # 凑整后添加需要释放的锁数量
                        n += 1
                        self._partial %= 1

                    # 如果值是负的说明已经存在被获取的锁。
                    self._cond.notify(min(-self._value, n))
                    # 释放指定量的已经获取的锁，剩余的量作为可直接通过的锁数量。
                    self._value += int(n)
                else:
                    self._value = int(n)
                    self._partial += n % 1
                    if self._partial >= 1:
                        self._value += 1
                        self._partial %= 1

    def release_all(self):
        """ 释放所有获取的锁。"""
        with self._cond:
            self._cond.notify_all()
