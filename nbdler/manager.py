
from six.moves.queue import Queue as ThreadQueue
from multiprocessing import Manager as ProcessManager
from nbdler.struct.signal import ID_TASK_FINISH, ID_TASK_STOP, ID_TASK_EXCEPTION, ID_TASK_PAUSE, \
    SIGNAL_TASK_PAUSE, Signal, ID_TASK_OPEN, SIGNAL_TASK_OPEN, SIGNAL_TASK_START, ID_TASK_START, \
    SIGNAL_TASK_FAIL, ID_TASK_FAIL, SIGNAL_CALLBACK_END, ID_CALLBACK_END
from nbdler.struct.misc import SignalQueue, ProcessInfo
from nbdler.utils.process_interface import make_class, make_method
from nbdler.utils.thread import ThreadCollector, Lock
from nbdler.struct.task import TaskWrapper, TaskQueue
from nbdler.handler import dlopen
from nbdler.exception import HandlerError, URLError, ClientError, \
    ChildProcessDisable


__all__ = ['Manager', 'manager', 'ManagerForChildProcess']


SIGNAL_CALLBACK_END = SIGNAL_CALLBACK_END(Signal(id=-1))
DEFAULT_MAX_TASK = 2


def manager(max_task=DEFAULT_MAX_TASK, open_args=(), open_kwargs=None, deamon=False, *, child_process=False):
    if child_process:
        manager_handler = ManagerForChildProcess
    else:
        manager_handler = Manager

    return manager_handler(max_task, dlopen, open_args, open_kwargs, deamon)


class RequestWrapper(TaskWrapper):
    __slots__ = ()


class HandlerWrapper(TaskWrapper):
    __slots__ = ()


class ManagerWrapper(TaskWrapper):
    __slots__ = ()


GROUP_OPEN = 'Manager.open'
GROUP_OPEN_CTRL = 'Manager.opening_controller'
GROUP_CTRL_T = 'Manager.controller(t)'
GROUP_CTRL_P = 'Manager.controller(p)'
GROUP_DO_NEXT = 'Manager.Task.do_next'


class Manager:
    """
        Attribute:
            open_handle: A open-handle for handler.

            max_task: Specify the upper limit of running task at the same time.

            open_args: opener default args.

            open_kwargs: opener default kwargs.

            daemon: Default make client thread to be daemon thread if True.

    """
    def __init__(self, max_task, open_handle, open_args=(), open_kwargs=None, daemon=False):
        self._full_queue = []
        self._queue = TaskQueue(unopened=[], opening=[], ready=[], queue=[], running=[],
                                paused=[], finished=[], failed=[])
        self._open_handle = open_handle
        self._max_task = max_task
        if not open_kwargs:
            open_kwargs = {}

        self._open_args = open_args
        self._open_kwargs = open_kwargs

        self._process_mgr = None
        self._thread_queue = ThreadQueue()
        self._process_queue = None

        self._thread_collector = ThreadCollector(daemon)

        self._queue_started = False

        self._queue_lock = Lock()

        self._process_collector = {}

        self._closed = False

    def putrequest(self, request, enqueue=True):
        """ Put a Request into Manager queue.
            Return task id corresponding to the request.
        """
        if not self._process_queue:
            raise ChildProcessDisable('cannot put a request running on '
                                      'child process mode without enabling.')
        if request in self._full_queue:
            raise ValueError('request is already in the task queue.')
        index = len(self._full_queue)
        wrapper = RequestWrapper(id=index, source=request, callback=ThreadQueue(),
                                 child_process=request.child_process)
        self._full_queue.append(wrapper)
        self._queue.unopened.append(index)
        if enqueue:
            self.enqueue(index)

        return index

    def enable_child_process_mode(self):
        if not self._process_mgr:
            self._process_mgr = ProcessManager()
            self._process_queue = self._process_mgr.Queue()
            self._process_collector[-1] = self._process_mgr._process

    def remove(self, task_id):
        """ Remove task by task id. """
        self._border_check(task_id)
        self._full_queue[task_id] = None

    def puthandler(self, handler):
        """ Put a Handler into Manager queue.
            Return task id corresponding to the handler.

            Warning: Not supported in child_process mode.
        """
        if handler in self._full_queue:
            raise ValueError('handler is already in the task queue.')
        index = len(self._full_queue)
        wrapper = HandlerWrapper(id=index, source=handler)
        self._full_queue.append(wrapper)
        handler.install_external_callback_queue(SignalQueue(
            id=index, queue=self._thread_queue))
        self._queue.ready.append(index)
        return index

    def get(self, task_id):
        """ Return HandlerWrapper of the task specified by id.

            Warning: this method does not supported by running in child process mode.
        """
        return self._full_queue[task_id]

    def process_info(self):
        infos = {}
        for k, v in self._process_collector.items():
            infos[k] = ProcessInfo(name=v.name, pid=v.pid, ident=v.ident)
        return infos

    def start_all(self):
        for i in self._queue.ready:
            self.start(i)
        for i in self._queue.paused:
            self.start(i)

    def get_all(self):
        for i in self._full_queue:
            if i is not None:
                yield i

    def enqueue(self, task_id):
        """ Make task into the plan queue.

            When queue is started, manager would run the tasks
            in the queue automatically until queue is empty.
        """
        self._border_check(task_id)
        with self._queue_lock:
            if task_id in self._queue.finished:
                raise RuntimeError('cannot queue a finished task.')
            self.__remove_queue_task(task_id)
            self._queue.queue.append(task_id)

    def getinstspeed(self, task_id=None):
        if task_id is not None:
            if not self._opened_info_checking(task_id):
                return 0
            return self._full_queue[task_id].source.getinstspeed()
        else:
            speed = 0
            for i in self._queue.running:
                speed += self._full_queue[i].source.getinstspeed()
            return speed

    def getavgspeed(self, task_id=None):
        if task_id is not None:
            if not self._opened_info_checking(task_id):
                return 0
            return self._full_queue[task_id].source.getavgspeed()
        else:
            speed = 0
            for i in self._queue.running:
                speed += self._full_queue[i].source.getavgspeed()
            return speed

    def getincbyte(self, task_id=None):
        if task_id is not None:
            if not self._opened_info_checking(task_id):
                return 0
            return self._full_queue[task_id].source.get_go_inc()
        else:
            incbyte = 0
            for i in self._queue.running:
                incbyte += self._full_queue[i].source.get_go_inc()
            return incbyte

    def get_remain_time(self, task_id=None):
        if task_id is not None:
            if not self._opened_info_checking(task_id):
                return float('inf')
            return self._full_queue[task_id].source.get_time_left()
        else:
            remain = 0
            for i in self._queue.running:
                remain += self._full_queue[i].source.get_time_left()
            return remain

    def get_remain_byte(self, task_id=None):
        if task_id is not None:
            if not self._opened_info_checking(task_id):
                return float('inf')
            return self._full_queue[task_id].source.get_byte_left()
        else:
            remain = 0
            for i in self._queue.running:
                remain += self._full_queue[i].source.get_byte_left()
            return remain

    def getfileinfo(self, task_id):
        if not self._opened_info_checking(task_id):
            return None
        return self._full_queue[task_id].source.getfileinfo()

    def geturlinfo(self, task_id):
        if not self._opened_info_checking(task_id):
            return None
        return self._full_queue[task_id].source.geturlinfo_all()

    def start_queue(self):
        """ Start running plan queue.

            The max number of running task is limited by self._max_task.
        """
        self._queue_started = True
        cur_task_len = len(self._queue.running)
        cur_task_len += len(self._queue.running)
        if cur_task_len < self._max_task:
            for i in range(self._max_task - cur_task_len):
                if self._queue.queue:
                    task_id = self._queue.queue[0]
                    self.start(task_id)
                else:
                    self.stop_queue()
                    break

    def stop_queue(self):
        """ Stop running plan queue.

            This method does not stop the running/opening task.
        """
        self._queue_started = False

    def start(self, task_id):
        self._border_check(task_id)

        if type(self._full_queue[task_id]) is RequestWrapper:
            self._full_queue[task_id].after(self.start, args=(task_id,), force=True)
            self.__remove_queue_task(task_id)
            self._queue.opening.append(task_id)
            self.open(task_id, block=False)
        else:
            self._full_queue[task_id].source.start()
            self._send_ctrl_signal(SIGNAL_TASK_START, task_id)

        self._check_controller_state()

    def resume(self, task_id):
        """ Resume the failed task.

            Only make failed task out of failed queue, cannot reopen/rerun the task.
        """
        if task_id not in self._queue.failed:
            raise RuntimeError('task <%d> is no need to resume.' % task_id)

        self._queue.failed.remove(task_id)
        if type(self._full_queue[task_id]) is RequestWrapper:
            self._queue.unopened.append(task_id)
        else:
            self._queue.ready.append(task_id)

    def pause(self, task_id):
        self._border_check(task_id)
        self._send_ctrl_signal(SIGNAL_TASK_PAUSE, task_id)

    stop = pause

    def pause_all(self, *, block=True):
        for i in self._queue.running:
            self.pause(i)
        for i in self._thread_collector.get_group(GROUP_OPEN_CTRL):
            task_id = i.owner
            self.pause(task_id)

        if block:
            for i in self._queue.running:
                self._full_queue[i].source.join()

    stop_all = pause_all

    def open(self, task_id, *, block=True):
        self._border_check(task_id)
        self._check_controller_state()

        if type(self._full_queue[task_id]) is not RequestWrapper:
            raise TypeError('opening task should be a type of request.')

        if block:
            return self._open(task_id)
        else:
            self._thread_collector.put(self._open, GROUP_OPEN, args=(task_id,),
                                       owner=task_id).start()

    def open_all(self, *, sequential=False, block=True):
        for i in self._queue.unopened:
            self.open(i, block=sequential)

        if block:
            self._thread_collector.wait(GROUP_OPEN)

    def is_all_finish(self):
        if not self.is_idle():
            return False
        if self._queue.paused or self._queue.failed or self._queue.unopened:
            return False
        return True

    def is_idle(self):
        """ Return True if all running and opening task are over. """
        if self._thread_collector.get_all():
            return False
        if self._queue.running:
            return False
        return True

    def get_queue(self):
        return tuple(self._queue.queue)

    def get_unopened(self):
        return tuple(self._queue.unopened)

    def get_finished(self):
        return tuple(self._queue.finished)

    def get_running(self):
        return tuple(self._queue.running)

    def get_failed(self):
        return tuple(self._queue.failed)

    def get_paused(self):
        return tuple(self._queue.paused)

    def is_finish(self, task_id):
        self._border_check(task_id)
        return self._full_queue[task_id].source.is_finished()

    def close(self):
        if not self.is_idle():
            raise RuntimeError('cannot close a running manager.')

        if self._closed:
            raise RuntimeError('manager has already closed.')

        if self._process_mgr:
            self._process_mgr.shutdown()
            self._process_mgr = None
            del self._process_collector[-1]
        for k, v in self._process_collector.items():
            if not v._close:
                v.terminate()
        self._closed = True

    def _opening_control_thread(self, task_id, handler):
        callback = self._full_queue[task_id].callback
        while True:
            signal = callback.get()
            if signal.id == ID_TASK_OPEN:
                self._full_queue[task_id] = signal.content
                self._send_ctrl_signal(SIGNAL_TASK_OPEN, task_id)
                callback.put_nowait(SIGNAL_CALLBACK_END)
            elif signal.id == ID_TASK_PAUSE:
                handler.pause(block=False)
                self._send_ctrl_signal(SIGNAL_TASK_PAUSE, task_id)
                callback.put_nowait(SIGNAL_CALLBACK_END)
            elif signal.id == ID_TASK_FAIL:
                self._send_ctrl_signal(SIGNAL_TASK_FAIL, task_id, signal.content)
                callback.put_nowait(SIGNAL_CALLBACK_END)
            elif signal.id == ID_CALLBACK_END:
                while not callback.empty():
                    callback.get_nowait()
                    callback.task_done()
                break
            callback.task_done()

        callback.task_done()

    def _check_controller_state(self):
        if not self._thread_collector.get_group(GROUP_CTRL_T):
            self._thread_collector.put(
                self._manager_control_thread,
                GROUP_CTRL_T, args=(self._thread_queue,),
                owner=self._thread_queue).start()
        if not self._thread_collector.get_group(GROUP_CTRL_P):
            self._thread_collector.put(
                self._manager_control_thread,
                GROUP_CTRL_P, args=(self._process_queue,),
                owner=self._process_queue).start()

    def _manager_control_thread(self, queue):
        while True:
            signal = queue.get()
            task_id = signal.content.id
            content = signal.content.content
            if signal.id == ID_TASK_FINISH:
                self.__finished_task_handler(task_id)
            elif signal.id == ID_TASK_OPEN:
                self.__opened_task_handler(task_id)
            elif signal.id in (ID_TASK_EXCEPTION, ID_TASK_FAIL):
                self.__failed_task_handler(task_id, content)
            elif signal.id == ID_TASK_STOP:
                self.__stopped_task_handler(task_id)
            elif signal.id == ID_TASK_PAUSE:
                self.__paused_task_handler(signal.content)
            elif signal.id == ID_TASK_START:
                self.__started_task_handler(task_id)
            elif signal.id == ID_CALLBACK_END:
                break

            self._do_next(task_id)
            queue.task_done()
            self._idle_checking()

        queue.task_done()

    def _border_check(self, task_id):
        if task_id >= len(self._full_queue) or self._full_queue[task_id] is None:
            raise IndexError('task id is invalid.')

    def _open(self, task_id):
        wrapper = None
        dlreq_wrapper = self._full_queue[task_id]
        handler = self._open_handle(child_process=dlreq_wrapper.child_process,
                                    **self._open_kwargs)
        if dlreq_wrapper.child_process:
            self._process_collector[task_id] = handler._process
        open_callback = dlreq_wrapper.callback
        self._thread_collector.put(self._opening_control_thread, GROUP_OPEN_CTRL,
                                   args=(task_id, handler), owner=task_id).start()
        try:
            handler.open(dlreq_wrapper.source)
        except (HandlerError, URLError, ClientError) as e:
            open_callback.put_nowait(
                SIGNAL_TASK_FAIL(Signal(id=task_id, content=e))
            )
        except Exception as e:
            open_callback.put_nowait(
                SIGNAL_TASK_FAIL(Signal(id=task_id, content=e))
            )
            raise
        else:

            if handler.is_opened():
                if dlreq_wrapper.child_process:
                    queue = self._process_queue
                else:
                    queue = self._thread_queue

                wrapper = HandlerWrapper(id=task_id, source=handler,
                                         child_process=dlreq_wrapper.child_process)
                handler.install_external_callback_queue(SignalQueue(
                    id=task_id, queue=queue))
                wrapper.move_from(dlreq_wrapper)
                open_callback.put_nowait(
                    SIGNAL_TASK_OPEN(content=wrapper))

            else:
                open_callback.put_nowait(SIGNAL_TASK_PAUSE(Signal(id=task_id)))

        return wrapper

    def _pause_opening(self, task_id):
        flag = False
        open_threads = self._thread_collector.get_group(GROUP_OPEN_CTRL)
        for i in open_threads:
            if i.owner == task_id:
                flag = True
        if flag:
            wrapper = self._full_queue[task_id]
            if type(wrapper) is RequestWrapper:
                wrapper.callback.put_nowait(SIGNAL_TASK_PAUSE())

    def _opened_info_checking(self, task_id):
        return type(self._full_queue[task_id]) is not RequestWrapper

    def _send_ctrl_signal(self, signal_wrapper, task_id, content=None):
        signal = signal_wrapper(Signal(id=task_id, content=content))
        if self._full_queue[task_id].child_process:
            self._process_queue.put_nowait(signal)
        else:
            self._thread_queue.put_nowait(signal)

    def _close_controller(self):
        if self._thread_collector.get_group(GROUP_CTRL_T):
            self._thread_queue.put_nowait(SIGNAL_CALLBACK_END)
        if self._thread_collector.get_group(GROUP_CTRL_P):
            self._process_queue.put_nowait(SIGNAL_CALLBACK_END)

    def _idle_checking(self):
        if not self._queue.opening and not self._queue.running and \
                (not self._queue_started or (self._queue_started and not self._queue.queue)):
            self._close_controller()

    def _do_next(self, task_id):
        next_task = self._full_queue[task_id].get_next()
        if next_task:
            self._thread_collector.put(next_task.handler, GROUP_DO_NEXT, args=next_task.args,
                                       kwargs=next_task.kwargs, owner=task_id).start()

    def __remove_queue_task(self, task_id):
        if task_id in self._queue.running:
            self._queue.running.remove(task_id)
        elif task_id in self._queue.queue:
            self._queue.queue.remove(task_id)
        elif task_id in self._queue.paused:
            self._queue.paused.remove(task_id)
        elif task_id in self._queue.ready:
            self._queue.ready.remove(task_id)
        elif task_id in self._queue.unopened:
            self._queue.unopened.remove(task_id)
        elif task_id in self._queue.failed:
            self._queue.failed.remove(task_id)
        elif task_id in self._queue.finished:
            self._queue.finished.remove(task_id)
        elif task_id in self._queue.opening:
            self._queue.opening.remove(task_id)

    def __paused_task_handler(self, signal):
        task_id = signal.id
        if task_id in self._queue.running:
            self._full_queue[task_id].source.pause(block=False)
        elif task_id in self._queue.unopened:
            self._pause_opening(task_id)

        if task_id in self._queue.running:
            self._queue.running.remove(task_id)
            self._queue.paused.append(task_id)

        if self._queue_started:
            self.start_queue()

    def __check_process_collector(self, task_id):
        if task_id in self._process_collector:
            del self._process_collector[task_id]

    def __opened_task_handler(self, task_id):
        self.__remove_queue_task(task_id)
        self._queue.ready.append(task_id)

    def __finished_task_handler(self, task_id):
        self.__remove_queue_task(task_id)
        self._queue.finished.append(task_id)

        self._full_queue[task_id].source.close()
        self.__check_process_collector(task_id)

        if self._queue_started:
            self.start_queue()

    def __failed_task_handler(self, task_id, exception):
        self.__remove_queue_task(task_id)
        self._full_queue[task_id].fail(exception)
        self._queue.failed.append(task_id)
        self._full_queue[task_id].reset()

        self.__check_process_collector(task_id)

        if self._queue_started:
            self.start_queue()

    def __stopped_task_handler(self, task_id):
        pass

    def __started_task_handler(self, task_id):
        self.__remove_queue_task(task_id)
        self._queue.running.append(task_id)


@make_class(Manager)
class ManagerForChildProcess:

    @make_method
    def putrequest(self, request, enqueue=True):
        pass

    # @make_method
    # def puthandler(self, handler):
    #     pass

    @make_method
    def remove(self, task_id):
        pass

    # @make_method
    # def get(self, task_id):
    #     pass

    # @make_method
    # def save_handle(self):
    #     pass

    @make_method
    def start_all(self):
        pass

    @make_method
    def get_all(self):
        pass

    @make_method
    def enqueue(self, task_id):
        pass

    @make_method
    def start_queue(self):
        pass

    @make_method
    def stop_queue(self):
        pass

    @make_method
    def start(self, task_id):
        pass

    @make_method
    def resume(self, task_id):
        pass

    @make_method
    def pause(self, task_id):
        pass

    stop = pause

    @make_method
    def pause_all(self, task_id):
        pass

    stop_all = pause_all

    @make_method
    def open(self, task_id, *, block=True):
        pass

    @make_method
    def open_all(self, *, sequential=False, block=True):
        pass

    @make_method
    def is_all_finish(self):
        pass

    @make_method
    def is_idle(self):
        pass

    @make_method
    def get_queue(self):
        pass

    @make_method
    def get_unopened(self):
        pass

    @make_method
    def get_finished(self):
        pass

    @make_method
    def get_running(self):
        pass

    @make_method
    def get_failed(self):
        pass

    @make_method
    def get_paused(self):
        pass

    @make_method
    def is_finish(self, task_id):
        pass

    @make_method
    def getfileinfo(self, task_id):
        pass

    @make_method
    def geturlinfo(self, task_id):
        pass

    @make_method
    def getincbyte(self, task_id=None):
        pass

    @make_method
    def getinstspeed(self, task_id=None):
        pass

    @make_method
    def getavgspeed(self, task_id=None):
        pass

    @make_method
    def get_remain_time(self, task_id=None):
        pass

    @make_method
    def get_remain_byte(self, task_id=None):
        pass

    @make_class
    def close(self):
        pass

    @make_method
    def enable_child_process_mode(self):
        pass

    @make_method
    def process_info(self):
        pass

    @make_method
    def dumps_handle(self):
        pass

    @make_method
    def loads_handle(self, dumped_data):
        pass


