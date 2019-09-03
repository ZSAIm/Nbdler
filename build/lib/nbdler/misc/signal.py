

from collections import namedtuple

Signal = namedtuple('Signal', 'id content')
Signal.__new__.__defaults__ = (None,)


def make_signal(id):
    func = lambda content: Signal(id=id, content=content)
    func.__defaults__ = (None,)
    return func


ID_TASK_STOP = -1
ID_TASK_BUFF = 0
ID_BLOCK_FINISH = 1
ID_TASK_SLICE = 2
ID_TASK_FINISH = 3
ID_THREAD_END = 4
ID_TASK_PAUSE = 5
ID_TASK_EXCEPTION = 6
ID_TASK_OPEN = 7
ID_TASK_START = 8
ID_TASK_FAIL = 9
ID_EMPTY_RECV = 15

ID_CALLBACK_END = 10

ID_STOP_ALL = 16
ID_IDLE = 17

ID_URL_STATUS = 100

ID_NORMAL = 0
ID_CRASH = 1
ID_TIMEOUT = 2
ID_GAIERROR = 3
ID_UNKNOWN = 4
ID_SWITCH = 5
ID_WAIT = 6


SIGNAL_TASK_STOP = make_signal(ID_TASK_STOP)

SIGNAL_STOP_ALL = make_signal(ID_STOP_ALL)

SIGNAL_TASK_FINISH = make_signal(ID_TASK_FINISH)

SIGNAL_TASK_PAUSE = make_signal(ID_TASK_PAUSE)

SIGNAL_TASK_OPEN = make_signal(ID_TASK_OPEN)
SIGNAL_TASK_START = make_signal(ID_TASK_START)
SIGNAL_TASK_BUFF = make_signal(ID_TASK_BUFF)
SIGNAL_TASK_SLICE = make_signal(ID_TASK_SLICE)
SIGNAL_THREAD_END = make_signal(ID_THREAD_END)

SIGNAL_EMPTY_RECV = make_signal(ID_EMPTY_RECV)

SIGNAL_URL_STATUS = make_signal(ID_URL_STATUS)

SIGNAL_NORMAL = make_signal(ID_NORMAL)
SIGNAL_CRASH = make_signal(ID_CRASH)
SIGNAL_TIMEOUT = make_signal(ID_TIMEOUT)
SIGNAL_GAIERROR = make_signal(ID_GAIERROR)
SIGNAL_UNKNOWN = make_signal(ID_UNKNOWN)

SIGNAL_EXCEPTION = make_signal(ID_TASK_EXCEPTION)

SIGNAL_SWITCH = make_signal(ID_SWITCH)

SIGNAL_WAIT = make_signal(ID_WAIT)

SIGNAL_IDLE = make_signal(ID_IDLE)

SIGNAL_TASK_FAIL = make_signal(ID_TASK_FAIL)

SIGNAL_CALLBACK_END = make_signal(ID_CALLBACK_END)

