# -*- coding: UTF-8 -*-
from abc import abstractmethod
from queue import Queue
from ...utils.eventdriven import session
from ...event import EVT_TASK_PAUSING, EVT_TASK_SLICE, EVT_CLIENT_SWITCH, EVT_CLIENT_WAIT, EVT_BUFFER_COUNT


class BaseClient:
    def __init__(self, source, progress, partial, **option):
        self._queue = Queue()
        self.source = source
        self.progress = progress
        self.partial = partial
        self.options = option

        self._conn_res = None, None
        self._cons = None

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def retrieve(self):
        pass

    def clean(self):
        """ 清空消息队列。
        该方法应由控制端使用。
        """
        self._queue = Queue()

    def getresponse(self):
        """ 获取客户端连接响应。 """
        return self.source.response

    def pause(self):
        """ 发送暂停控制信号。 """
        self._dispatch(EVT_TASK_PAUSING)

    def wait(self, sec):
        """ 发送睡眠等待信号。 """
        self._dispatch(EVT_CLIENT_WAIT, sec)

    def slice_from(self, req_range):
        """ 发送切片信号。 """
        self._dispatch(EVT_TASK_SLICE, req_range)

    def switch_to(self, source):
        """ 发送切下载源。 """
        self._dispatch(EVT_CLIENT_SWITCH, source)

    def _dispatch(self, sig_id, value=None):
        """ 控制台发送给客户端控制信号。 """
        self._queue.put((sig_id, value))

    def _buffer(self, data):
        """ 缓存下载数据报告给控制台。 """
        if data:
            self._report(EVT_BUFFER_COUNT, data)

    def _report(self, evt, value=None, context=None):
        """ 客户端报告给控制台。 """
        context = context or {}
        context.update({'blo': session.blo})
        self._cons.dispatch(evt, value, context)

    @abstractmethod
    def run(self, cons):
        """ 客户端自动连接下载。 """

    @abstractmethod
    def close(self):
        """ 客户端关闭连接。 """

    @staticmethod
    @abstractmethod
    def dlopen(source, progress, partial, **options):
        pass





