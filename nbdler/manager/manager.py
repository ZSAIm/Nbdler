# -*- coding: UTF-8 -*-
from .struct.task import TaskManager, TasksManagerForWorkers
from .struct.queue import TaskQueue
from ..utils.eventdriven import ControllerPool, Controller, Subprocess, EventPending, Timer
from ._manager import (EVT_MANAGER_WORKER_SPEED_LIMIT, EVT_MANAGER_WORKER_PAUSE)
from nbdler.event import EVT_MANAGER_START
from ._manager import manager_model, workers_model
from ..utils.misc import Component
from ..error import ManagerError
from threading import Lock
from queue import Queue


class ManagerConfigure(Component):
    """ 下载池管理器的配置信息。"""
    HEARTBEAT_INTERVAL = 0.5

    def __init__(self, maxsize, daemon=True, subprocess=False, max_speed=None, max_buff=None,
                 heartbeat_interval=HEARTBEAT_INTERVAL):
        """
        :param
            maxsize:            最大同时下载任务数量。
            daemon:             线程daemon参数。
            subprocess:         是否子进程模式下运行。
            max_speed:          最大速度限制。
            max_buff:           最大内存缓冲大小。若为None则由各自下载任务单独处理。
            heartbeat_interval: 心跳刷新间隔。
        """
        self.maxsize = maxsize
        self.daemon = daemon
        self.subprocess = subprocess
        self.max_speed = max_speed
        self.max_buff = max_buff
        self.heartbeat_interval = heartbeat_interval

    def __snapshot__(self):
        return {
            'maxsize': self.maxsize,
            'daemon': self.daemon,
            'subprocess': self.daemon,
            'max_speed': self.max_speed,
            'max_buff': self.max_buff,
            'heartbeat_interval': self.heartbeat_interval
        }


class Manager(Component):
    def __init__(self, maxsize, **configure):
        assert maxsize > 0
        self._subprocess = None
        # 下载池管理器配置信息
        self.configure = ManagerConfigure(maxsize, **configure)
        # 任务ID队列
        self.__queue = TaskQueue()
        # 实时运行中的任务ID队列
        self.working = []
        # 下载任务管理器，集合下载对象信息的获取方法
        task_mgr_for_workers = TasksManagerForWorkers()
        # 初始化控制台和工作控制器。
        con_worker = Controller(mapping=manager_model, static={
            'mgr': self, 'cfg': self.configure, 'queue': self.__queue, 'working': self.working
        }, daemon=self.configure.daemon, name='manager-%s' % maxsize)
        # 时钟发生器适配器用来实现限速的信号量处理问题。
        con_worker.Adapter(Timer())
        workers_static = {
            '_is_subprocess': self.configure.subprocess, 'task_mgr': task_mgr_for_workers,
        }
        if self.configure.subprocess:
            # 为了确保多余的空闲工作线程，多创建一个工作线程。
            con_worker.Adapter(Subprocess(maxsize=maxsize+1, mapping=workers_model, static=workers_static))
            # 子进程模式下使用了子进程插件Subprocess使得控制台在子进程下具有控制器池。
            # 所以控制台控制器也属于工作控制器。
            workers = con_worker
            self._subprocess = con_worker.adapters['subprocess']
            # 将父进程的下载任务替换成虚拟实例。
            task_mgr_for_workers = self._subprocess['task_mgr']
        else:
            # 统一与子进程模式下调用的行为，添加适配器EventPending
            con_worker.Adapter(EventPending())
            # 在非子进程模式下，工作控制器和控制台控制器是分开的，所以为了在工作控制器方便使用，将其引入静态上下文。
            workers_static['con_worker'] = con_worker
            workers = ControllerPool(maxsize, workers_model, static=workers_static, daemon=self.configure.daemon)

        self.workers = workers
        # 控制台引入工作控制器的对象。
        con_worker.__static__['workers'] = self.workers
        self.con_worker = con_worker
        task_mgr_for_workers = TaskManager(task_mgr_for_workers, self.configure.subprocess, self.__queue)
        self._task_mgr = task_mgr_for_workers

        # 异常错误队列
        self.__raise = Queue()
        self.__trap_lock = Lock()
        self.__paused = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def body(self):
        """ 返回正在运行队列的任务的实体信息。"""
        return self._task_mgr.running_tasks.body

    info = body

    def __getitem__(self, item):
        if item == -1:
            return self._task_mgr.running_tasks
        elif item == -2:
            return self._task_mgr.all_tasks
        if item is not None and type(item) not in (tuple, list):
            # 列表化，方便后续统一的处理。
            item = (item,)
        return self._task_mgr.get_tasks(item)

    @property
    def queue(self):
        """ 返回下载任务队列消息。"""
        return self.__queue

    def is_paused(self):
        """ 返回管理器是否被暂停。"""
        return self.__paused

    def is_alive(self):
        """ 返回管理器是否在运行中。"""
        return self.con_worker.is_alive()

    def putrequest(self, request, enqueue=True):
        """ 添加下载任务请求到待下载队列。
        返回任务ID号，用于接下来对其进行操作。
        """
        tid = self.__queue.push(request)
        if enqueue:
            self.__queue.enqueue(tid)
        return tid

    def is_finished(self):
        """ 返回所有下载任务是否已结束。"""
        return not self.__paused and self.__queue.is_closed()

    def remaining_time(self):
        """ 返回运行中的总的估计剩余下载时间。"""
        return self._task_mgr.running_tasks.remaining_time()

    def remaining_length(self):
        """ 返回运行中的总的剩余下载字节数。"""
        return self._task_mgr.running_tasks.remaining_length()

    def realtime_speed(self):
        """ 返回运行中的总实时下载速度。"""
        return self._task_mgr.running_tasks.realtime_speed()

    def average_speed(self):
        """ 返回运行中的总平均下载速度。"""
        return self._task_mgr.running_tasks.average_speed()

    def increment_go(self):
        """ 返回运行中的总下载字节长度。"""
        return self._task_mgr.running_tasks.increment_go()

    def increment_done(self):
        """ 返回运行中的总写入文件的字节长度。"""
        return self._task_mgr.running_tasks.increment_done()

    def wait(self, timeout=None):
        """ 等待入列的任务处理完毕。并且等待下载池管理器控制器处于空闲状态。"""
        # 等待队列全部处理完成后
        self.__queue.join(timeout)
        # 控制器事件处理完毕并且处于空闲状态。
        self.con_worker.pending()
        self.con_worker.wait_for_idle()
        self.workers.pending()
        self.workers.wait_for_idle()

    join = wait

    def _raise_exception(self, error):
        """ 异常错误推送。"""
        if error is None:
            # 如果进入了trap方法的锁才进行推送None以通知释放锁。
            if not self.__trap_lock.locked():
                return
        self.__raise.put(error)

    def trap(self, timeout=None):
        """ 下载异常捕获等待。注意这应该只让其中一个线程处理，否则其他线程会出现阻塞的问题。"""
        with self.__trap_lock:
            if not self.con_worker.is_alive():
                return
            while True:
                data = self.__raise.get(timeout=timeout)
                # 如果异常信息是None说明是控制台停止所抛出的消息。
                if data is None:
                    break
                tid, exception = data

                raise ManagerError(exception, tid)

    def start(self):
        """ 开始/继续下载池管理器，之后将会按照待下载队列以最大下载任务数顺序进行下载。 """
        if self.con_worker.is_alive():
            self.__paused = False
            # 恢复队列的挂起。
            self.__queue.start()
            # 下载池管理器已经启动的前提下尝试运行队列的任务。
            self.con_worker.dispatch(EVT_MANAGER_START)
            self.con_worker.adapters['timer'].resume()
        else:
            # 准备任务队列
            self.__queue.start()
            # 启动控制台线程。
            self.con_worker.run()
            # 子进程模式下由于工作线程处于控制台的控制下，所以这时候不需要手动启动工作线程。
            if not self._subprocess:
                self.workers.run()
            self._task_mgr.start()
            # 等待工作控制器数据准备就绪。
            self.con_worker.dispatch(EVT_MANAGER_START).pending()
            self.con_worker.adapters['timer'].set_timing(self.configure.heartbeat_interval)

    def pause(self, block=True):
        """ 停止下载池管理器。"""
        self.__paused = True
        self.workers.dispatch(EVT_MANAGER_WORKER_PAUSE, self.__queue.running)
        if block:
            self.join()

    def close(self):
        """ 关闭下载池管理器。"""
        assert self.is_alive()
        # 关闭队列，任务管理器，再关闭控制台和工作线程，
        # 避免子进程模式下关闭后继续请求子进程获取下载信息而发生错误。
        self.__queue.close()
        # 关闭任务管理器
        self._task_mgr.close()
        # 关闭控制台线程
        self.con_worker.shutdown()
        if not self._subprocess:
            self.workers.shutdown()
        self.con_worker.wait()
        self.workers.wait()
        # 清理控制台和工作线程的多余未处理时间，以便再次启动有之前的残留事件。
        self.con_worker.clean()
        self.workers.clean()

    def set_limit(self, max_speed):
        """ 开启下载管理器全局限速。"""
        self.configure.max_speed = max_speed
        if max_speed is None:
            # 最大速度为None则是关闭限速。
            self.workers.dispatch(EVT_MANAGER_WORKER_SPEED_LIMIT, False, context={'running': self.__queue.running})
        else:
            self.workers.dispatch(EVT_MANAGER_WORKER_SPEED_LIMIT, True, context={'running': self.__queue.running})

    def __snapshot__(self):
        return {
            'configure': self.configure.__snapshot__(),
            'queue': self.__queue.__snapshot__()
        }

    export = __snapshot__
