
from threading import Thread as _Thread, current_thread
from threading import Lock, RLock
from time import perf_counter


class Thread(_Thread):
    __slots__ = ('_owner',)

    def __init__(self, owner=None, *args, **kwargs):
        _Thread.__init__(self, *args, **kwargs)
        self._owner = owner

    def is_stopped(self):
        """ Return True if thread is stopped. """
        return not self.is_alive() and self._is_stopped

    def is_started(self):
        """ Return True if thread is started. """
        return self._started.is_set()

    @property
    def owner(self):
        """ Return thread's owner. """
        return self._owner


class ThreadCollector:
    def __init__(self, daemon=False):
        self._running_threads = {}
        self.__make_lock = Lock()
        self._daemon = daemon

    @property
    def daemon(self):
        return self._daemon

    def put(self, target, group_name, args=(), owner=None, kwargs=None):
        """ Make a new thread into thread pool. """
        self._correct_running()
        target = Thread(target=target, name=group_name, args=args,
                        daemon=self._daemon, owner=owner, kwargs=kwargs)
        with self.__make_lock:
            if group_name not in self._running_threads:
                self._running_threads[group_name] = []

            self._running_threads[group_name].append(target)
        return target

    def wait(self, group_name, timeout=None):
        """ Wait a specified group of threads until to the end of life. """
        cur_thread = current_thread()
        for thread in self._running_threads.get(group_name, []):
            if thread != cur_thread:
                timeout = _join_one(thread, timeout)

    def join(self, timeout=None):
        """ Wait all the threads in the pool until to the end of life. """
        cur_thread = current_thread()
        for v in list(self._running_threads.values()):
            for thread in v:
                if thread != cur_thread:
                    timeout = _join_one(thread, timeout)

    def start_all(self):
        """ Start all the threads in the pool. """
        for v in list(self._running_threads.values()):
            for thread in v:
                if not thread.is_started() and not thread.is_stopped():
                    thread.start()

    def start_group(self, name):
        """ Start a specified group of threads to run. """
        for thread in self._running_threads[name]:
            if not thread.is_started() and not thread.is_stopped():
                thread.start()

    def get_group(self, group_name):
        """ Return all threads in a specified group. """
        self._correct_running()
        return self._running_threads.get(group_name, [])

    def _correct_running(self):
        """ Clean all the stopped thread. """
        with self.__make_lock:
            for i, v in list(self._running_threads.items()):
                for thread in v:
                    if thread.is_stopped():
                        v.remove(thread)
                if not v:
                    del self._running_threads[i]

    def get_all(self):
        """ Return all running threads. """
        self._correct_running()
        return self._running_threads


def _join_one(thread, timeout=None):
    if timeout is not None and timeout < 0:
        raise TimeoutError()
    start = perf_counter()
    thread.join(timeout=timeout)
    if timeout is not None:
        timeout -= perf_counter() - start

    return timeout


# _GLOBAL_THREAD_POOLS = {}
#
#
# def get(name, *, owner=None, daemon=False):
#     global _GLOBAL_THREAD_POOLS
#     if name not in _GLOBAL_THREAD_POOLS:
#         _GLOBAL_THREAD_POOLS[name] = ThreadCollector(daemon)
#
#     if owner is not None:
#         name = name + '<%d>' % id(owner)
#
#     return _GLOBAL_THREAD_POOLS[name]
#
#
# def remove(name):
#     global _GLOBAL_THREAD_POOLS
#     if name not in _GLOBAL_THREAD_POOLS:
#         raise ValueError('thread pool named %s isn\'t existed.' % name)
#
#     del _GLOBAL_THREAD_POOLS[name]
#
#
# def has_key(name):
#     global _GLOBAL_THREAD_POOLS
#     return name in _GLOBAL_THREAD_POOLS

