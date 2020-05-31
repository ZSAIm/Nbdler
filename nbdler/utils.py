import time
from collections import deque
import asyncio
from contextlib import contextmanager
import threading
from concurrent import futures


class UsageInfo:
    """ 用于记录使用信息。
    其中包括使用时长和使用速率。
    """

    __slots__ = '_fetch_length', '_previous_length', '_previous_time', '_start_time', '_moving_avg', 'rate'

    def __init__(self, fetch_length):
        self._fetch_length = fetch_length

        self._previous_length = fetch_length()
        self._start_time = time.time()
        self._previous_time = self._start_time
        self._moving_avg = deque([0 for _ in range(8)])
        self.rate = 0

    def reset(self):
        self._start_time = time.time()
        self._previous_time = self._start_time
        self._moving_avg = deque([0 for _ in range(8)])
        self.rate = 0

    def timelength(self):
        return time.time() - self._start_time

    def refresh(self):
        cur_time = time.time()
        cur_length = self._fetch_length()
        diff_time = cur_time - self._previous_time
        diff_length = cur_length - self._previous_length

        self._previous_length = cur_length
        self._previous_time = cur_time
        speed = diff_length / (diff_time or float('inf'))

        self._moving_avg.pop()
        self._moving_avg.appendleft(speed)

        self.rate = sum(self._moving_avg) / 8


def update_range_field(range_filed, target_range):
    """ 更新范围域。

    通过{}包含域定义，如{begin}
    可选域定义：
        begin: 范围开头。
        end: 范围结尾，不包括该值本身。
        end_with: 范围结尾，包括该值本身。
        length: 范围长度。

    示例：target_range=(2, 99)
    域值更新为：begin=2, end=99, end_with=98, length=97

    Args:
        range_filed: 范围域定义，可更新域有begin,end,end_with,length
        target_range: 要更新的范围值

    Returns:
        更新域值后的结果。
    """
    target_begin, target_end = target_range

    begin = target_begin
    if target_end is None or target_end == float('inf'):
        end = ''
        end_with = ''
        length = ''
    else:
        end = target_end
        if target_end > 0:
            end_with = target_end - 1
        else:
            end_with = ''
        length = end - begin
    return range_filed.format(
        begin=begin,
        end=end,
        end_with=end_with,
        length=length)


class _ExecutorEventLoopFuture:
    """ 在Executor中安全运行run_forever的事件循环的Future。 """
    def __init__(self, task_fut, loop_fut):
        self._loop = loop_fut
        self._task = task_fut

    def __await__(self):
        yield from asyncio.wrap_future(self._task)

    def __iter__(self):
        yield from asyncio.wrap_future(self._task)

    def get_loop(self):
        return self._loop.result()

    async def aget_loop(self):
        return await asyncio.wrap_future(self._loop)

    def join(self):
        return self._task.result()

    async def ajoin(self):
        return await asyncio.wrap_future(self._task)

    result = join

    aresult = ajoin

    def close(self):
        loop = self.get_loop()
        return loop.call_soon_threadsafe(loop.stop)

    async def aclose(self):
        loop = await self.aget_loop()
        fut = loop.call_soon_threadsafe(loop.stop)
        return await asyncio.wrap_future(fut)

    def add_done_callback(self, __fn):
        return self._task.add_done_callback(__fn)


def forever_loop_in_executor(executor, loop=None):
    """ 在concurrent.futures.thread.ThreadPoolExecutor中运行异步事件循环。
    该事件循环线程只能使用loop.stop()方法停止。"""
    def _run():
        nonlocal loop, future_loop
        if loop is None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError('new loop')
            except RuntimeError:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        future_loop.set_result(loop)
        try:
            loop.run_forever()
        finally:
            try:
                cancel_all_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

    future_loop = futures.Future()
    task_fut = executor.submit(_run)
    return _ExecutorEventLoopFuture(task_fut, future_loop)


def cancel_all_tasks(loop):
    """ 关闭循环中剩余的所有任务。 """
    # source from asyncio.runners._cancel_all_tasks

    to_cancel = asyncio.tasks.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        asyncio.tasks.gather(*to_cancel, loop=loop, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'unhandled exception during asyncio.run() shutdown',
                'exception': task.exception(),
                'task': task,
            })