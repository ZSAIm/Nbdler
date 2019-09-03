
from collections import namedtuple
TaskQueue = namedtuple('_TaskQueue', 'unopened opening ready queue '
                                     'running paused finished failed')
Task = namedtuple('_Task', 'handler args kwargs')


class TaskWrapper:
    def __init__(self, id, source, callback=None, child_process=False):
        self.id = id
        self.source = source
        self.callback = callback
        self._after = []
        self._failed_exc = None
        self.child_process = child_process

    def after(self, handler, args=(), kwargs=None, force=False):
        if not kwargs:
            kwargs = {}
        task = Task(handler=handler, args=args, kwargs=kwargs)
        if force:
            self._after.insert(0, task)
        else:
            self._after.append(task)
        return self

    def get_next(self):
        if not self._after:
            return None
        return self._after.pop(0)

    def fail(self, msg):
        self._failed_exc = msg

    def move_from(self, task_wrapper):
        nexttask = task_wrapper.get_next()
        while nexttask:
            self._after.append(nexttask)
            nexttask = task_wrapper.get_next()

    def reset(self):
        self._after.clear()
        if self.callback:
            while not self.callback.empty():
                self.callback.get_nowait()



