# -*- coding: UTF-8 -*-
from ...error import SubprocessUnavailableError
from functools import wraps
from threading import Event
from time import time


class TasksManagerForWorkers:
    """ 工作线程维护的一个任务管理器。"""
    __slots__ = '_id_tasks'

    def __init__(self):
        self._id_tasks = {}

    def __contains__(self, item):
        return item in self._id_tasks

    def __getitem__(self, item):
        return self._id_tasks[item]

    def __setitem__(self, key, value):
        self._id_tasks[key] = value

    def items(self):
        return self._id_tasks

    def is_finished(self, tid_list=None):
        """ 返回下载任务是否完成。"""
        id_tasks = self._id_tasks
        if tid_list is None:
            return all([task.is_finished() for task in id_tasks.values()])
        else:
            return all([False if tid in id_tasks else id_tasks[tid].is_finished() for tid in tid_list])

    def increment_go(self, tid_list=None, each=False):
        """ 返回已下载的字节长度。"""
        return self.__realtime_info('increment_go', tid_list, each)

    def increment_done(self, tid_list=None, each=False):
        """ 返回已写入文件的字节长度。 """
        return self.__realtime_info('increment_done', tid_list, each)

    def remaining_time(self, tid_list=None, each=False):
        """ 返回下载任务的估计剩余下载时间。"""
        return self.__realtime_info('remaining_time', tid_list, each)

    def remaining_length(self, tid_list=None, each=False):
        """ 返回下载任务的剩余下载长度。 """
        return self.__realtime_info('remaining_length', tid_list, each)

    def realtime_speed(self, tid_list=None, each=False):
        """ 返回下载任务的实时速度。 """
        return self.__realtime_info('realtime_speed', tid_list, each)

    def average_speed(self, tid_list=None, each=False):
        """ 返回下载任务的平均速度。"""
        return self.__realtime_info('average_speed', tid_list, each)

    def get_realtime_info(self, tid_list=None, each=False):
        """ 返回实时速度 + 平均速度 + 剩余下载量 + 估计剩余下载时间 的字典。"""
        return {
            'realtime_speed': self.realtime_speed(tid_list, each),
            'average_speed': self.average_speed(tid_list, each),
            'remaining_length': self.remaining_length(tid_list, each),
            'remaining_time': self.remaining_time(tid_list, each),
            'increment_go': self.increment_go(tid_list, each),
            'increment_done': self.increment_done(tid_list, each),
        }

    def get_file(self, tid_list=None):
        """ 返回下载对象的文件信息。 """
        return self.__body_info('file', tid_list)

    def get_url(self, tid_list=None):
        """ 返回下载对象的下载源信息。"""
        return self.__body_info('url', tid_list)

    def get_config(self, tid_list=None):
        """ 返回下载对象配置信息。 """
        return self.__body_info('config', tid_list)

    def get_all_body(self, tid_list=None):
        """ 返回下载对象的全部信息。 """
        return self.__body_info('all', tid_list)

    def get_body_info(self, tid_list=None):
        return {
            'file': self.get_file(tid_list),
            'url': self.get_url(tid_list),
            'config': self.get_config(tid_list),
            'block_mgr': self.get_block_mgr(tid_list)
        }

    def get_block_mgr(self, tid_list=None, index=None):
        """ 返回下载对象的下载块信息。"""
        id_tasks = self._id_tasks
        if tid_list is None:
            res = {tid: task.body.block_mgr.get_all() for tid, task in id_tasks.items()}
        else:
            if index is None:
                res = {tid: id_tasks[tid].body.block_mgr.get_all() for tid in tid_list}
            else:
                res = {tid: id_tasks[tid].body.block_mgr[index] for tid in tid_list}

        return res

    def __realtime_info(self, meth, tid_list, each):
        """ 返回实时信息。"""
        id_tasks = self._id_tasks
        if tid_list is None:
            return sum([getattr(v, meth)() for v in id_tasks.values()])
        if each:
            return {tid: getattr(id_tasks[tid], meth)() for tid in tid_list if tid in id_tasks}
        else:
            return sum([getattr(id_tasks[tid], meth)() for tid in tid_list if tid in id_tasks])

    def __body_info(self, meth, tid_list):
        """ 返回实体信息。"""
        id_tasks = self._id_tasks
        if tid_list is None:
            res = {tid: getattr(task.body, meth) for tid, task in id_tasks.items()}
        else:
            res = {tid: getattr(id_tasks[tid].body, meth) for tid in tid_list if tid in id_tasks}
        return res

    def pause(self, tid_list):
        """ 暂停下载任务。"""
        id_tasks = self._id_tasks
        for tid in tid_list:
            if tid in id_tasks:
                id_tasks[tid].pause(block=False)

    def release_buffer(self, tid_list):
        id_tasks = self._id_tasks
        for tid in tid_list:
            if tid in id_tasks:
                id_tasks[tid].console.release_buffer()


class TaskManager:
    """ 控制台维护的一个任务管理器。"""
    __slots__ = '_task_mgr', '_task_queue', '_subprocess', '_running_body', '_all_body', '_closed'

    def __init__(self, tasks_mgr, subprocess, task_queue):
        self._task_mgr = tasks_mgr
        self._subprocess = subprocess
        self._closed = Event()
        self._task_queue = task_queue
        self._running_body = Tasks(tasks_mgr, task_queue, subprocess, task_queue.running, self._closed)
        self._all_body = Tasks(tasks_mgr, task_queue, subprocess, None, self._closed)

    @property
    def running_tasks(self):
        return self._running_body

    @property
    def all_tasks(self):
        return self._all_body

    def get_tasks(self, tid_list):
        return Tasks(self._task_mgr, self._task_queue, self._subprocess, tid_list, self._closed)

    def close(self):
        """ 下载任务管理器关闭。"""
        self._closed.set()

    def start(self):
        """ 下载任务管理器开启。"""
        self._closed.clear()


def _is_available(func):
    """ 判断信息是否可获取。"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._subprocess and self._closed.is_set():
            raise SubprocessUnavailableError('下载进程已关闭，无法获取下载对象信息。')
        return func(self, *args, **kwargs)
    return wrapper


class Tasks:
    """ 多个Downloader的封装。"""
    __slots__ = '_task_mgr', '_task_queue', '_subprocess', '_tid_list', '_body', '_closed'

    def __init__(self, tasks_mgr, task_queue, subprocess, tid_list, closed_event):
        self._task_mgr = tasks_mgr
        self._task_queue = task_queue
        self._subprocess = subprocess
        self._tid_list = tid_list
        self._body = TasksBody(tasks_mgr, subprocess, tid_list, closed_event)
        self._closed = closed_event

    @property
    def body(self):
        return self._body

    info = body

    @_is_available
    def remaining_length(self, each=False):
        return self._task_mgr.remaining_length(self._tid_list, each)

    @_is_available
    def remaining_time(self, each=False):
        return self._task_mgr.remaining_time(self._tid_list, each)

    @_is_available
    def realtime_speed(self, each=False):
        return self._task_mgr.realtime_speed(self._tid_list, each)

    @_is_available
    def average_speed(self, each=False):
        return self._task_mgr.average_speed(self._tid_list, each)

    @_is_available
    def increment_go(self, each=False):
        return self._task_mgr.increment_go(self._tid_list, each)

    @_is_available
    def increment_done(self, each=False):
        return self._task_mgr.increment_done(self._tid_list, each)

    @_is_available
    def realtime_info(self, each=False):
        return self._task_mgr.get_realtime_info(self._tid_list, each)

    @_is_available
    def body_info(self):
        return self._task_mgr.get_body_info(self._tid_list)

    @_is_available
    def pause(self):
        self._task_mgr.pause(self._tid_list)

    @_is_available
    def is_finished(self):
        return self._task_mgr.is_finished(self._tid_list)

    def wait_for_ready(self, timeout=None):
        """ 等待任务准备就绪。"""
        endtime = None
        for tid in self._tid_list:
            if timeout is not None:
                if endtime is None:
                    endtime = time() + timeout
                else:
                    timeout = endtime - time()
                    if timeout <= 0:
                        return False
            ret = self._task_queue[tid].ready.wait(timeout)
            if not ret:
                return False
        return True

    def wait(self, timeout=None):
        """ 等待下载任务结束。若指定timeout，超时后返回False"""
        endtime = None
        for tid in self._tid_list:
            if timeout is not None:
                if endtime is None:
                    endtime = time() + timeout
                else:
                    timeout = endtime - time()
                    if timeout <= 0:
                        return False
            ret = self._task_queue.wait(tid)
            if not ret:
                return False
        return True

    join = wait


class TasksBody:
    __slots__ = '_task_mgr', '_subprocess', '_tid_list', '_closed', '_block_mgr'

    def __init__(self, tasks_mgr, subprocess, tid_list, closed_event):
        self._task_mgr = tasks_mgr
        self._subprocess = subprocess
        self._tid_list = tid_list
        self._closed = closed_event
        self._block_mgr = TasksBloMgrBody(tasks_mgr, subprocess, tid_list, closed_event)

    @property
    @_is_available
    def file(self):
        return self._task_mgr.get_file(self._tid_list)

    @property
    @_is_available
    def url(self):
        return self._task_mgr.get_url(self._tid_list)

    @property
    @_is_available
    def config(self):
        return self._task_mgr.get_config(self._tid_list)

    @property
    @_is_available
    def block_mgr(self):
        return self._block_mgr

    @property
    @_is_available
    def all(self):
        return self._task_mgr.get_all_body(self._tid_list)


class TasksBloMgrBody:
    __slots__ = '_task_mgr', '_subprocess', '_tid_list', '_closed'

    def __init__(self, tasks_mgr, subprocess, tid_list, closed_event):
        self._task_mgr = tasks_mgr
        self._subprocess = subprocess
        self._tid_list = tid_list
        self._closed = closed_event

    @_is_available
    def __getitem__(self, item):
        return self._task_mgr.get_block_mgr(self._tid_list, item)

    @_is_available
    def get_all(self):
        return self._task_mgr.get_block_mgr(self._tid_list)



