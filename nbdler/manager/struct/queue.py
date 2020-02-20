# -*- coding:UTF-8 -*-

from ...utils.misc import Component
from threading import RLock, Event


class RequestTask:
    __slots__ = 'id', 'request', 'idle', 'ready'

    def __init__(self, id, request):
        self.id = id
        self.request = request
        self.idle = Event()
        self.idle.set()
        self.ready = Event()

    def __eq__(self, other):
        return type(self.request) is RequestTask and self.request == other.request


class TaskQueue(Component):
    __slots__ = ('_requests', '__count', '_rlock', '__closed',
                 'enqueued', 'running', 'dequeued', 'unsettled',
                 'ready', 'opening', 'started', 'paused', 'error', 'finished')

    def __init__(self):
        self._requests = {}
        self.__count = 0
        self._rlock = RLock()
        self.__closed = Event()
        # 初始化后处于挂起状态。
        self.__closed.set()
        # 运行队列
        self.enqueued = []
        self.running = []
        self.dequeued = []

        self.unsettled = []
        # 状态队列
        self.ready = []
        self.opening = []
        self.started = []
        self.paused = []
        self.error = []
        self.finished = []

    def __enter__(self):
        """ 为了安全的编辑任务队列，先上锁在进行修改队列列表。"""
        self._rlock.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rlock.release()

    def __getitem__(self, item):
        """ 返回任务请求任务。"""
        return self._requests[item]

    def wait(self, timeout=None):
        """ 等待队列结束。"""
        return self.__closed.wait(timeout)

    join = wait

    def start(self):
        """ 队列运行。"""
        self.__closed.clear()

    def close(self):
        """ 关闭队列。"""
        self.__closed.set()

    def is_empty(self):
        """ 返回队列是否为空。 """
        return not self.enqueued and not self.running and not self.unsettled

    def is_closed(self):
        return self.__closed.is_set()

    def push(self, request):
        """ 任务入队列"""
        with self:
            if request in self._requests:
                raise ValueError('队列中已存在当前任务。')
            tid = self.__count
            self._requests[tid] = RequestTask(tid, request)
            self.__count += 1
            self.enqueue(tid)
        return tid

    def enqueue(self, tid):
        """ 任务ID入列。"""
        with self:
            if tid in self.unsettled:
                raise PermissionError('不允许入列处于未确定状态的任务。')
            if tid in self.running:
                raise PermissionError('不允许入列正在运行的任务。')
            self._pop_status(tid)
            self.ready.append(tid)
            # 任务入列。
            self._pop_queue(tid)
            self.enqueued.append(tid)

    def unsettle(self, tid):
        """ 待决的任务ID。"""
        with self:
            self._pop_queue(tid)
            self.unsettled.append(tid)

    def go_finished(self, tid):
        """ 任务完成事件。"""
        with self:
            self._pop_status(tid)
            self.finished.append(tid)
            # 任务完成出列。
            self._pop_queue(tid)
            self.dequeued.append(tid)

    def go_error(self, tid):
        """ 任务异常错误事件。 """
        with self:
            self._requests[tid].ready.set()
            self._pop_status(tid)
            self.error.append(tid)
            # 任务错误出列。
            self._pop_queue(tid)
            self.dequeued.append(tid)

    def go_started(self, tid):
        """ 任务开始。"""
        with self:
            self._pop_status(tid)
            self.started.append(tid)
            # 任务运行中
            self._pop_queue(tid)
            self.running.append(tid)
            self._requests[tid].ready.set()

    def go_opening(self, tid):
        """ 任务打开中。"""
        with self:
            self._pop_status(tid)
            self.opening.append(tid)

    def go_paused(self, tid):
        """ 任务暂停中。"""
        with self:
            self._pop_status(tid)
            self.paused.append(tid)
            # 任务暂停出列。
            self._pop_queue(tid)
            self.dequeued.append(tid)

    def go_ready(self, tid):
        """ 任务就绪中。"""
        with self:
            self._pop_status(tid)
            self.ready.append(tid)
            # 任务就绪入列。
            self._pop_queue(tid)
            self.enqueued.append(tid)

    def _pop_status(self, tid):
        """ 状态、运行队列移除。"""
        if tid in self.ready:
            self.ready.remove(tid)
        elif tid in self.started:
            self.started.remove(tid)
        elif tid in self.opening:
            self.opening.remove(tid)
        elif tid in self.paused:
            self.paused.remove(tid)
        elif tid in self.error:
            self.error.remove(tid)
        elif tid in self.finished:
            self.finished.remove(tid)

    def _pop_queue(self, tid):
        """ 状态、运行队列移除。"""
        if tid in self.unsettled:
            self.unsettled.remove(tid)
        elif tid in self.enqueued:
            self.enqueued.remove(tid)
        elif tid in self.running:
            self.running.remove(tid)
        elif tid in self.dequeued:
            self.dequeued.remove(tid)

    def __snapshot__(self):
        return {
            'enqueued': self.enqueued,
            'dequeued': self.dequeued,
            'running': self.running,
            'ready': self.ready,
            'opening': self.opening,
            'started': self.started,
            'paused': self.paused,
            'error': self.error,
            'finished': self.finished
        }


