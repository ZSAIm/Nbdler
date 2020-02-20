# -*- coding: UTF-8 -*-
"""
工作原理：

                   +-----------------------+                                     +-----------------------------------+
 EVT_MANAGER_START |                       |    EVT_MANAGER_WORKER_START_TASK    |                                   |
----------------->----------->---------------->-------------------------------->-------------v                       |
                   |         |             |          EVT_TASK_OPENING           |           v                       |
                   |         |          v-----<------------------------------------- EVT_MANAGER_WORKER_DLOPEN_TASK  |
                   |         |          |  |           EVT_TASK_START            |           |                       |
                   |         ^          v-----<----------------------------------------------<                       |
                   | +--------------+   |  |           EVT_TASK_ERROR            |        +------------------------+ |
                   | |  TaskQueue   |   v-----<---------------------------------------<   |  TasksManagerForWorker | |
                   | +--------------+   |  |           EVT_TASK_PAUSED           |    |   +------------------------+ |
                   | |  enqueued    |<--<-----<---------------------------------------<   |         task0          | |
                   | |  running     |   |  |           EVT_TASK_FINISH           |    |<--|         task1          | |
                   | |  dequeued    |   ^-----<---------------------------------------<   |         task2          | |
                   | |      ...     |   |  |          EVT_TASK_SHUTDOWN          |    |   |         task3          | |
                   | +--------------+   ^-----<---------------------------------------<   |           ...          | |
                   |                    |  |           EVT_TASK_CLOSED           |    |   +------------------------+ |
                   |                    ^-----<---------------------------------------<             ^                |
                   |                       |                                     |                  |                |
                   |                       |     EVT_MANAGER_WORKER_CLOSE_TASK   |                   |                |
                   |                       |  ------------------------------------------------------^                |
                   | +-----------------+   |                                     |                                   |
                   | |  TasksManager   |   |                                     |                                   |
                   | +-----------------+   |                                     |                                   |
                   | |    task0        |   |    EVT_MANAGER_WORKER_SPEED_LIMIT    |                                   |
                   | |    task1        |   |  -------------------------------->  |                                   |
                   | |    task2        |   |    EVT_MANAGER_WORKER__HEARTBEAT     |                                   |
                   | |      ...        |   |  -------------------------------->  |                                   |
                   | +-----------------+   |                                     |                                   |
                   |                       |                                     |                                   |
                   |                       |                                     |                                   |
                   |                       |                                     |                                   |
                   |                       |                                     |                                   |
                   |                       |                                     |                                   |
                   |                       |                                     |                                   |
                   |    <con_worker>       |                                     |               <workers>           |
                   |                       |                                     |                                   |
                   +-----------------------+                                     +-----------------------------------+
 EVT_MANAGER_WORKER_PAUSE                                                                   ^
 ------------------------------------------------------------------------------------------^

"""
from ..utils.eventdriven import MappingBlueprint, session, EVT_DRI_TIMING, EVT_WORKER_PREPARE
from ..event import (EVT_TASK_FINISH, EVT_TASK_ERROR, EVT_TASK_SHUTDOWN, EVT_TASK_PAUSED, EVT_TASK_OPENING,
                     EVT_TASK_START, EVT_TASK_CLOSED, EVT_MANAGER_START, EVT_MANAGER_PAUSED,
                     EVT_MANAGER_SUSPEND, EVT_MANAGER_SHUTDOWN, EVT_MANAGER_ERROR)
from ..error import RequestError, MaxRetriesExceededError
from .._api import dlopen


manager_model = MappingBlueprint()
workers_model = MappingBlueprint()


# ==========================================
# 下载池管理器事件
#
# public:
#   session['cfg']      : 下载池管理器配置信息
#   session['workers']  : 下载池工作控制器
#   session['working']  : 正在运行的任务ID链
#   session['queue']    : 下载任务ID队列
#   session['self']     : 控制台控制器
#   session['raise']    : 异常错误队列
#   session['mgr']      : 下载池管理器
#
# ==========================================


@manager_model.register(EVT_MANAGER_START)
def __manager_start__():
    """ 下载池管理器运行队列。
    :private
        null
    """
    if session['mgr'].is_paused():
        return

    task_queue = session['queue']
    # 任务队列安全锁
    with task_queue:
        n = session['cfg'].maxsize - len(session['working'])
        for i in range(n):
            try:
                tid = task_queue.enqueued[0]
            except IndexError:
                break
            task_queue.unsettle(tid)
            request_task = task_queue[tid]
            session['working'].append(tid)
            # 任务空闲状态事件清除。
            request_task.idle.clear()

            session['workers'].dispatch(EVT_MANAGER_WORKER_START_TASK, context={
                'tid': tid,
                'request': request_task.request,
                'daemon': session['cfg'].daemon,
                'max_buff': session['cfg'].max_buff
            })


@manager_model.register(EVT_MANAGER_PAUSED)
def __manager_paused__():
    """ 暂停下载池管理器。
    :private
        null
    """
    session['self'].dispatch(EVT_MANAGER_SUSPEND)


@manager_model.register(EVT_MANAGER_SHUTDOWN)
def __manager_close__():
    """ 下载池管理器准备关闭事件。
    :private
        null
    """
    if not session['cfg'].subprocess:
        session['workers'].shutdown()
    session['self'].shutdown()


@manager_model.register(EVT_MANAGER_SUSPEND)
def __manager_suspend__():
    """ 下载池队列已完成。进入挂起状态。
    :private
        null
    """
    # 挂起后挂起限速的心跳发送。
    session['self'].adapters['timer'].suspend()
    # 下载队列已全部结束，关闭队列。
    session['queue'].close()
    # 如何使用了trap方法释放锁。
    session['mgr']._raise_exception(None)


@manager_model.register(EVT_MANAGER_ERROR)
def __manager_error__():
    """ 下载池任务异常抛出。
    :private
    type1:(任务事件-转发)
        session['val']  : ForwardingPacket(value, context)
        session.lname   : 任务ID

    type2:(管理器事件)
        session['val']  : 异常错误
        session.tid     : 任务ID
    """
    try:
        # :::::type1
        # 对应 __dl_error__
        tid = session.lname
        exception, _ = session['val']
    except AttributeError:
        # :::::type2
        tid = session.tid
        exception = session['val']

    session['queue'].go_error(tid)
    # 引出异常错误。
    session['mgr']._raise_exception((tid, exception))


@manager_model.register(EVT_DRI_TIMING)
def __manager_timing__():
    """ 定时发生器。目前只用于限速心跳事件。
    :private
        session['val']  : 时钟间隔
    """
    running = session['queue'].running
    if not session['mgr'].is_finished() and running:
        session['workers'].dispatch(EVT_MANAGER_WORKER_HEARTBEAT, session['val'], context={
            'running': running,
            'max_speed': session['cfg'].max_speed,
            'max_buff': session['cfg'].max_buff
        })


@manager_model.register(EVT_TASK_START)
def __dl_started__():
    """ 下载任务开始。
    :private
        session.tid : 任务ID
    """
    session['queue'].go_started(session.tid)


@manager_model.register(EVT_TASK_OPENING)
def __dl_opening__():
    """ 任务打开中。
    :private
        session.tid : 任务ID
    """
    session['queue'].go_opening(session.tid)


@manager_model.register(EVT_TASK_FINISH)
def __dl_finished__():
    """ 任务完成。事实上这确实是任务已完成，但是还在下载完成后的处理，未完全下载完成。
    :private
        session.lname       : 任务ID
    """
    tid = session.lname


@manager_model.register(EVT_TASK_PAUSED)
def __dl_paused__():
    """ 任务暂停。
    :private
        session.lname       : 任务ID
    """
    tid = session.lname


@manager_model.register(EVT_TASK_SHUTDOWN)
def __dl_shutdown__():
    """ 任务关闭退出。（可以通过判断值value来判断是下载完成或任务暂停）
    视情况而定，原计划是用于关闭当前任务并且进行下一任务的进行。
    :private
        session['val']      : ForwardingPacket(value, context) 转发事件
        session.lname       : 任务ID

    :from
        downloader
    """
    tid = session.lname
    value, context = session['val']
    # 该ID下载任务设置为空闲状态
    session['queue'][tid].idle.set()
    if value is True:
        # _finish_task(tid)
        session['queue'].go_finished(tid)
        # 如果下载任务已经完成了，那么关闭下载任务。
        session['workers'].dispatch(EVT_MANAGER_WORKER_CLOSE_TASK, context={'tid': tid})
        # 下载完成的任务，之后会进行关闭下载器的操作，所以不会立即通知控制台任务已完成。
    else:
        session['queue'].go_paused(tid)
        # 通知该任务的处理已结束。
        session['self'].dispatch(EVT_TASK_CLOSED, context={'tid': tid})

    session['self'].dispatch(EVT_MANAGER_START)


@manager_model.register(EVT_TASK_ERROR)
def __dl_error__():
    """ 任务异常错误。
    存在两种错误发起源： 一种是由下载对象转发的事件，另一种是由下载池管理器发起的事件。

    :private
    type1:
        session['val']      : 下载池管理器发起。

    type2:
        session['val']      : ForwardingPacket(value, context) 转发事件
        session.lname       : 任务ID

    :from
        1. manager 2. downloader
    """
    try:
        tid = session.tid
        exception = session['val']
    except AttributeError:
        tid = session.lname
        exception, _ = session['val']
    # 将错误报告给管理器控制台
    session['self'].dispatch(EVT_MANAGER_ERROR, exception, context={'tid': tid})


@manager_model.register(EVT_TASK_CLOSED)
def __dl_closed__():
    """ 下载任务结束了任务关闭操作后。
    :private
        session.tid : 任务ID
    """
    session['working'].remove(session.tid)
    task_queue = session['queue']
    with task_queue:
        if task_queue.is_empty():
            session['self'].dispatch(EVT_MANAGER_SUSPEND)


# ==========================================
# 工作控制器。
# public:
#   session['self']         : 下载池管理器工作控制器
#   session['task_mgr']     : 下载任务管理器
#   session['pool_mgr']     : 工作线程池管理器
#   session['_is_subprocess']:是否在子进程模式下
#
#
# subprocess only:
#   session['instance']     : 子进程实例空间
#   session['bri_worker']   : 子进程通信桥控制器
#
# not subprocess only:
#   session['con_worker']   : 控制台控制器
#
# ==========================================

EVT_MANAGER_WORKER_START_TASK = '|MGR|WORKER|START|TASK|'
EVT_MANAGER_WORKER_DLOPEN_TASK = '|MGR|DLOPEN|'
EVT_MANAGER_WORKER_CLOSE_TASK = '|MGR|CLOSE|TASK|'
EVT_MANAGER_WORKER_PAUSE = '|MGR|WORKER|PAUSE|'
EVT_MANAGER_WORKER_HEARTBEAT = '|MGR|WORKER|HEARTBEAT|'
EVT_MANAGER_WORKER_SPEED_LIMIT = '|MGR|SPEED|LIMIT|'


@workers_model.register(EVT_WORKER_PREPARE)
def __prepare__():
    """ 工作控制器准备工作。
    :private
        session['val']  : None
    """
    if session['_is_subprocess']:
        # 方便父进程使用虚拟实例引用任务管理器
        session['instances']['task_mgr'] = session['task_mgr']


@workers_model.register(EVT_MANAGER_WORKER_START_TASK)
def __goto_start__():
    """ 开始任务。
    :private
        session.request     : 下载任务的请求对象
        session.tid         : 下载任务ID
    """

    if session.tid in session['task_mgr']:
        # 如果在任务队列中存在当前的运行的ID号，那么将继续使用ID号运行任务。
        _report_to_console(EVT_TASK_START)
        session['task_mgr'][session.tid].start()
    else:
        # 任务队列没有找到对应的任务ID则使用dlopen来打开。
        session['pool_mgr'].dispatch(EVT_MANAGER_WORKER_DLOPEN_TASK, session.request, context={
            'tid': session.tid,
            'daemon': session.daemon,
            'max_buff': session.max_buff
        })


@workers_model.register(EVT_MANAGER_WORKER_DLOPEN_TASK)
def __dlopen_start__():
    """ 打开下载请求。
    :private
        session['val']          : 下载请求request。
        session.tid             : 下载任务ID号。
        session.daemon          : 管理器配置参数daemon。
        session.max_buff        : 最大内存缓冲大小。
    """
    try:
        # 调整任务为opening状态。
        _report_to_console(EVT_TASK_OPENING)
        configure = {
            'daemon': session.daemon,
        }
        if session.max_buff:
            # 为了由下载管理器进行缓冲控制，
            # 强制设置所有的max_buff为float('inf')以避免各自的缓冲管理器自动释放。
            configure['max_buff'] = float('inf')

        dl = dlopen(session['val'], **configure)
    except (RequestError, MaxRetriesExceededError) as err:
        # 返回打开请求错误消息
        _report_to_console(EVT_TASK_ERROR, err)
    else:
        # 工作控制池存放下载任务。
        session['task_mgr'][session.tid] = dl
        # 监听下载任务的事件。
        allow = (EVT_TASK_FINISH, EVT_TASK_ERROR, EVT_TASK_SHUTDOWN, EVT_TASK_PAUSED)

        if session['_is_subprocess']:
            dl.listened_by(session['bri_worker'].return_channel, name=session.tid, allow=allow)
        else:
            dl.listened_by(session['con_worker'].event_channel, name=session.tid, allow=allow)
        # 开始下载任务
        dl.start()
        _report_to_console(EVT_TASK_START)


@workers_model.register(EVT_MANAGER_WORKER_CLOSE_TASK)
def __close_task__():
    """ 下载任务完成关闭。
    :private
        session.tid : 下载任务ID
    """
    try:
        session['task_mgr'][session.tid].close()
    except Exception as err:
        _report_to_console(EVT_TASK_ERROR, err)
    finally:
        _report_to_console(EVT_TASK_CLOSED)


@workers_model.register(EVT_MANAGER_WORKER_PAUSE)
def __pause_manager__():
    """ 暂停下载池控制器工作线程。
    :private
        session['val']  : running的任务ID列表
    """
    for tid in session['val']:
        session['task_mgr'][tid].pause()

    _report_to_console(EVT_MANAGER_PAUSED)


@workers_model.register(EVT_MANAGER_WORKER_HEARTBEAT)
def __heartbeat__():
    """ 心跳检测信号。
    :private
        session['val']      : 时钟间隔
        session.running     : 运行队列
        session.max_speed   : 最大速度限制
        session.max_buff    : 最大内存缓冲
    """
    task_mgr = session['task_mgr']
    running_queue = session.running
    # :::::内存缓冲。
    if session.max_buff:
        diff = task_mgr.increment_go(running_queue) - task_mgr.increment_done(running_queue)
        if diff > session.max_buff:
            task_mgr.release_buffer(running_queue)
    # :::::限速实现。
    if not session.max_speed:
        return
    # 粒度8k
    n = session.max_speed * session['val'] / 8196
    if not running_queue:
        return
    # 根据颗粒数尽量释放已获取的锁
    for tid in running_queue:
        semaphore = task_mgr[tid].console.adapters['semaphore']
        # 刷新开启限速锁。
        semaphore.open()
        if n > 0:
            x = min(n, len(semaphore))
            semaphore.release(x)
            n -= x
        else:
            break
    # 若存在剩余颗粒数将平均分配。
    if n > 0:
        if len(running_queue) > n:
            for tid in running_queue:
                task_mgr[tid].console.adapters['semaphore'].release(1)
                n -= 1
                if n <= 0:
                    break
        else:
            unit = n / len(running_queue)
            for tid in running_queue:
                task_mgr[tid].console.adapters['semaphore'].release(unit)


@workers_model.register(EVT_MANAGER_WORKER_SPEED_LIMIT)
def __speed_limit__():
    """ 关闭限速信号量控制器。
    :private
        session.running : 运行队列
    """
    for tid in session.running:
        if session['val']:
            session['task_mgr'][tid].console.adapters['semaphore'].open()
        else:
            session['task_mgr'][tid].console.adapters['semaphore'].close()


def _report_to_console(evt, value=None, context=None, args=(), kwargs=None):
    """ (workers Only)报告事件给控制台。
    :private
        session.tid : 下载任务ID
    """
    context = dict(context or {})
    try:
        context['tid'] = session.tid
    except AttributeError:
        context['tid'] = None
    if session['_is_subprocess']:
        session['bri_worker'].message(evt, value, context, args, kwargs)
    else:
        session['con_worker'].dispatch(evt, value, context, args, kwargs)
