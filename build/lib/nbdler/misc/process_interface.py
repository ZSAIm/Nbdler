
from multiprocessing import Pipe, Process, current_process
from six.moves.queue import Queue
from threading import current_thread
from collections import namedtuple
from nbdler.misc.thread import ThreadCollector
from traceback import format_exc


class ProcessRuntimeError(Exception):
    pass


HandleSignal = namedtuple('HandleSignal', 'id name args kwargs')
ResponseSignal = namedtuple('ResponseSignal', 'id value traceback')

HandleSignal.__new__.__defaults__ = ((), None)
ResponseSignal.__new__.__defaults__ = (None, None)

TERMINATE_PROCESS_SIGNAL = HandleSignal(id=None, name='')
TERMINATE_RESPONSE_SIGNAL = ResponseSignal(id=None)


def make_method(func=None, block=True):
    if func is not None:
        def wrapper(self, *args, **kwargs):
            cur_t = current_thread()
            cur_queue = Queue()
            self._process_response_id_queue[cur_t.ident] = cur_queue
            h_signal = HandleSignal(id=cur_t.ident, name=func.__name__,
                                    args=args, kwargs=kwargs)
            self._parent_conn.send(h_signal)
            if block:
                res_signal = cur_queue.get()
                if res_signal.traceback:
                    raise res_signal.value

                return res_signal.value

        return wrapper
    else:
        def inner_wrapper(f):
            return make_method(f, block=block)

        return inner_wrapper


def make_class(handle_class):
    def wrapper(wrapped_class):
        class MultiprocessClassWrapper(wrapped_class):
            def __init__(self, *args, **kwargs):
                self._parent_conn, self.__child_conn = Pipe()
                self.__class_handle = handle_class
                self.__args = args
                self.__kwargs = kwargs
                self.__thread_collector = ThreadCollector()
                self._process_response_id_queue = {}
                self._process = Process(target=child_process_main_thread,
                                        args=(self.__child_conn, handle_class, args, kwargs))
                self._process.start()
                self.__thread_collector.put(self.__response_receiver_thread,
                                            '(pid_%d)C_recv' % current_process().pid).start()
                self._closed = False

            def __response_receiver_thread(self):
                while True:
                    signal = self._parent_conn.recv()
                    if signal.id is None:
                        break
                    self._process_response_id_queue[signal.id].put_nowait(signal)
                    if signal.traceback:
                        if type(signal.value) is ProcessRuntimeError:
                            self.__thread_collector.put(
                                self.close, '(pid_%d)P_close' % current_process().pid).start()

            def close(self, *args, **kwargs):
                if self._closed:
                    raise RuntimeError('(pid:%d)process has already closed.' % current_process().pid)
                self._closed = True
                try:
                    make_method(self.close)(self, *args, **kwargs)
                finally:
                    self._parent_conn.send(TERMINATE_PROCESS_SIGNAL)
                    self.__child_conn.send(TERMINATE_PROCESS_SIGNAL)
                    self._process.join()
                    self._process.close()

        return MultiprocessClassWrapper

    return wrapper


def child_process_main_thread(child_conn, class_handle, class_args=(), class_kwargs=None):
    def handle_thread(handle_signal):
        try:
            retval = getattr(class_instance, handle_signal.name)(
                *handle_signal.args, **handle_signal.kwargs)
        except Exception as e:
            ret_signal = ResponseSignal(id=handle_signal.id, value=e,
                                        traceback=format_exc())
        else:
            ret_signal = ResponseSignal(id=handle_signal.id, value=retval)

        response_queue.put_nowait(ret_signal)

    def send_response_thread():
        while True:
            res_signal = response_queue.get()
            if res_signal.id is None:
                break
            try:
                child_conn.send(res_signal)
            except Exception as e:
                res_signal = ResponseSignal(id=res_signal.id,
                                            value=ProcessRuntimeError(e),
                                            traceback=format_exc())
                child_conn.send(res_signal)

    def recv_handle_thread():
        while True:
            signal = child_conn.recv()
            if signal.id is None:
                response_queue.put_nowait(TERMINATE_RESPONSE_SIGNAL)
                break
            thread_collector.put(handle_thread, signal.name, args=(signal,)).start()

    thread_collector = ThreadCollector()
    class_instance = class_handle(*class_args, **class_kwargs)
    response_queue = Queue()
    cur_p = current_process()
    thread_collector.put(send_response_thread, '(pid_%d)C_send' % cur_p.pid).start()
    thread_collector.put(recv_handle_thread, '(pid_%d)C_recv' % cur_p.pid).start()

    thread_collector.join()

