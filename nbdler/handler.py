import asyncio
from collections import defaultdict
from contextvars import ContextVar
from contextlib import asynccontextmanager, contextmanager
from concurrent.futures.thread import ThreadPoolExecutor
from nbdler.error import HandlerError, ClientError
from functools import partial
from copy import copy
from operator import attrgetter
import threading
from nbdler.utils import UsageInfo
from traceback import format_exc
import logging
import weakref
import json

log = logging.getLogger(__name__)

block_context = ContextVar('block context')


def _lookup_block():
    """ 查找上下文的下载块。"""
    return block_context.get()


def await_coroutine_threadsafe(coro, timeout=None):
    """ 线程安全等待协程结束。
    Args:
        coro: 协程
        timeout: 等待超时事件

    Returns:
        返回协程的执行结果，或抛出异常。
    """
    fut = asyncio.run_coroutine_threadsafe(coro, h.loop)
    return fut.result(timeout)


class Handlers(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready = None

    def __getattr__(self, item):
        return self[item]

    async def prepare(self):
        """ Handler启动预处理，通常预启动，做初始化工作。启动标志在该方法设置。"""
        self._ready = asyncio.Event(loop=asyncio.get_running_loop())
        result = await asyncio.gather(*[handler.prepare() for handler in self.values()])
        self._ready.set()
        return result

    async def start(self):
        """ 此方法用于启动Handler的异步工作Handler.run()方法。"""
        result = await asyncio.gather(*[handler.start() for handler in self.values()])
        self._ready = None
        return result

    async def close(self):
        await self._wait_for_ready()
        return await asyncio.gather(*[handler.close() for handler in self.values()])

    async def _wait_for_ready(self):
        """ 等待Handler准备就绪。"""
        ready = self._ready
        if ready is not None:
            await ready.wait()

    async def pause(self):
        await self._wait_for_ready()
        return await asyncio.gather(*[handler.pause() for handler in self.values()])

    async def join(self):
        await self._wait_for_ready()
        return await asyncio.gather(*[handler.join() for handler in self.values()])


class _HandlerReference(threading.local):
    # handlers 异步上下文。
    __context__ = ContextVar('handlers dict')

    def __init__(self):
        # handlers 线程上下文事件循环
        self._loop = None

    @property
    def loop(self):
        return self._loop

    @property
    def owner(self):
        return self.__context__.get()

    @contextmanager
    def enter(self, handlers, loop=None):
        assert self._loop or loop
        if loop:
            if not isinstance(loop, weakref.ProxyType):
                loop = weakref.proxy(loop)
            self._loop = loop

        if not isinstance(handlers, weakref.ProxyType):
            handlers = weakref.proxy(handlers)

        token = self.__context__.set(handlers)

        yield self
        self.__context__.reset(token)

    def __getattr__(self, item):
        return self.__context__.get()[item]

    def __iter__(self):
        return iter(self.__context__.get().values())

    iter_all = __iter__


h = _HandlerReference()


class Handler:
    name = None

    parent = None
    _future = None

    def add_parent(self, parent):
        self.parent = parent

    async def prepare(self, *args, **kwargs):
        pass

    async def start(self):
        assert not self._future or self._future.done()
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._future = future
        try:
            result = await self.run()
        finally:
            future.set_result(None)

    async def run(self, *args, **kwargs):
        raise NotImplementedError

    async def pause(self, *args, **kwargs):
        raise NotImplementedError

    async def close(self, *args, **kwargs):
        raise NotImplementedError

    def __repr__(self):
        return f'<Handler name={self.name}>'

    async def join(self):
        return await self._future

    def info_getter(self):
        return None


# TODO: 在多下载源的情况下对下载源之间经过资源数据采样校验，通过后作为响应基准
class SampleValidate(Handler):
    name = 'uri_validate'


class GatherException(Handler):
    """ 下载异常状态集合。

    负责工作：
        1. 收集下载过程中发生的异常
        2. 提供对异常的外部推送
    """
    name = 'exception'

    def __init__(self):
        # 实现异常获取的线程安全
        self._exceptions = defaultdict(list)
        self._cond = threading.Condition(threading.Lock())

        # async 异步异常获取回调
        self._waiter_callbacks = set()

        self._stopped = False

    def handler_error(self, exception):
        """ 推送handler异常

        Args:
            exception:  发生的异常对象
        """
        with self._cond:
            self._exceptions[HandlerError].append(format_exc())
            # 释放线程锁
            self._cond.notify_all()

            # 释放异步锁
            for waiter in self._waiter_callbacks:
                waiter()

    def client_error(self, exception):
        """ 推送client客户端异常

        Args:
            exception:  发生的异常对象
        """
        with self._cond:
            self._exceptions[ClientError].append(format_exc())
            # 释放线程锁
            self._cond.notify_all()
            # 释放异步锁
            for waiter in self._waiter_callbacks:
                waiter()

    def _fetch_exceptions(self, exception_type=None):
        if exception_type is None:
            exceptions = []
            for v in self._exceptions.values():
                exceptions.extend(v)
        else:
            exceptions = list(self._exceptions[exception_type])

        return exceptions

    def acquire_threadsafe(self, exception_type=None, *, just_new_exception=True):
        """ 线程安全获取异常

        以生成器的形式获取内部发生的异常，当下载任务暂停或者完成后将中断生成器的迭代。

        Args:
            exception_type: 指定异常类型，可选ClientError、HandlerError。默认None则获取所有异常。
            just_new_exception: 是否忽略当前时间前的旧异常，仅返回之后的新异常。

        Yields:
            内部出现的client或handler异常对象。
        """
        old_exc_list = []
        if just_new_exception:
            old_exc_list = self._fetch_exceptions()
        while True:
            with self._cond:
                if self._stopped:
                    break

                # 在上一次异常推送过程中是否有新的异常被忽略
                # 如果有忽略的异常就不需要等待，先处理被忽略的异常
                before_new_exc = self._fetch_exceptions()
                before_new_diff = sorted(
                    set(before_new_exc).difference(old_exc_list),
                    key=before_new_exc.index)

                if not before_new_diff:
                    self._cond.wait()

            if not before_new_diff:
                new_exc_list = self._fetch_exceptions(exception_type)
                new_exc_set = set(new_exc_list).difference(old_exc_list)
            else:
                new_exc_list = before_new_exc
                new_exc_set = before_new_diff

            if not new_exc_set:
                continue

            for exc in sorted(new_exc_set, key=new_exc_list.index):
                yield exc
            old_exc_list = new_exc_list

    async def acquire(self, exception_type=None, *, just_new_exception=True):
        """ 异步获取异常

        acquire的异步化方法，具体作用参看acquire()方法。

        Args:
            exception_type: 指定异常类型，可选ClientError、HandlerError。默认None则获取所有异常。
            just_new_exception: 是否忽略当前时间前的旧异常，仅返回之后的新异常。

        Yields:
            内部出现的client或handler异常对象。
        """
        def release_waiter():
            nonlocal cond, loop

            async def _release():
                async with cond:
                    cond.notify_all()
            asyncio.run_coroutine_threadsafe(_release(), loop=loop)

        loop = asyncio.get_running_loop()
        cond = asyncio.Condition(asyncio.Lock())
        self._waiter_callbacks.add(release_waiter)

        old_exc_list = []
        if not just_new_exception:
            old_exc_list = self._fetch_exceptions(exception_type)
        while True:
            with self._cond:
                if self._stopped:
                    break
                before_new_exc = self._fetch_exceptions()
                before_new_diff = sorted(
                    set(before_new_exc).difference(old_exc_list),
                    key=before_new_exc.index)

            if not before_new_diff:
                async with cond:
                    await cond.wait()

            if not before_new_diff:
                new_exc_list = self._fetch_exceptions(exception_type)
                new_exc_set = set(new_exc_list).difference(old_exc_list)
            else:
                new_exc_list = before_new_exc
                new_exc_set = before_new_diff

            if not new_exc_set:
                continue

            for exc in sorted(new_exc_set, key=new_exc_list.index):
                yield exc
            old_exc_list = new_exc_list

    async def run(self):
        self._stopped = False
        self._exceptions.clear()

    async def close(self):
        pass

    async def pause(self):
        self._stopped = True
        with self._cond:
            self._cond.notify_all()

        for waiter in self._waiter_callbacks:
            waiter()

    def __repr__(self):
        count = {k: len(v) for k, v in self._exceptions.items()}
        return f'<GatherException {count} future={self._future}>'


class URIStatus:
    def __init__(self, uri):
        self.source_uri = uri
        self._used = 0
        self._success = 0
        self._timeout = 0
        self._fatal = 0

        self._logs = []
        self._users = {}

        self._conn_delay_moving_avg = [0 for _ in range(8)]
        self._conn_delay = float('inf')

    def log(self, resp):
        self._logs.append(resp)

    def _response_delay(self, time_s):
        moving_avg = self._conn_delay_moving_avg
        moving_avg.append(time_s)
        moving_avg.pop(0)
        failure_count = moving_avg.count(float('inf'))
        if failure_count >= 5:
            self._conn_delay = float('inf')
        else:
            self._conn_delay = sum([delay for delay in moving_avg
                                    if delay != float('inf')]) / (8 - failure_count)

    def use(self, block):
        self._used += 1
        self._users[block] = UsageInfo(lambda: block.progress.walk_length)

    def timeout(self, block, resp):
        self._timeout += 1
        self.log(f'{block} {resp}')

    def success(self, block, resp):
        self._success += 1
        self.log(f'{block} {resp}')
        # TODO: 在多下载源的情况下对下载源之间经过资源数据采样校验，通过后作为响应基准
        if self.source_uri.getresponse() is None:
            self.source_uri.set_response(resp)
        self._response_delay(self._users[block].timelength())

    def fatal(self, block, resp):
        self._fatal += 1
        self.log(f'{block} {resp}')

    def disuse(self, block):
        self._used -= 1
        del self._users[block]

    def is_available(self):
        """ 返回当前下载源是否超过有效使用次数。 """
        return self.source_uri.max_conn is None or self.source_uri.max_conn > self._used

    @property
    def users(self):
        return self._users

    def get_copy(self):
        """ 返回URI下载源对象的副本。"""
        return copy(self.source_uri)

    def transfer_rate(self):
        """ 返回下载源的传输速率。"""
        return sum([user.rate for user in self._users.values()])

    def average_speed(self):
        """ 返回当下载源的平均连接的传输速率。"""
        users = [user.rate for user in self._users.values()]
        return sum(users) / len(users)

    def refresh(self):
        """ 刷新当前下载源的状态使用信息。"""
        for user in self._users.values():
            user.refresh()

    def __repr__(self):
        return (f'<URIStatus {self.transfer_rate() / 1024} kb/s [{self._conn_delay * 1000} ms]'
                f'(used={self._used}, success={self._success}, timeout={self._timeout}, fatal={self._fatal})>')

    def info(self):
        return {
            'transfer_rate': self.transfer_rate(),
            'used': self._used,
            'success': self._success,
            'timeout': self._timeout,
            'fatal': self._fatal,
            'connection_delay': self._conn_delay
        }


class URIStatusManager(Handler):
    """ URI状态管理器使用URIStatus对象管理URI下载源。

    负责工作：
        1. 管理和调配URI下载源
        2. 监控URI下载源工作状态
    """

    name = 'uri_mgr'

    def __init__(self):
        self._uri_status = {}
        self._cond = None
        self._stopped = False

    async def prepare(self):
        self._cond = asyncio.Condition()
        for uri in self.parent.uris:
            self._uri_status.setdefault(uri.id, URIStatus(uri))

    async def get_uri(self):
        """  返回URI状态对象供客户端使用。

        以下载源的使用次数为主，尽可能的覆盖所有的下载源，之后根据单连接的下载源传输速度快慢
        分配下载源。

        Returns:
            被分配的URIStatus对象。
        """
        avl_uris = self._find_avl_uris()
        while not avl_uris:
            await self._cond.wait()
            avl_uris = self._find_avl_uris()

        uri = avl_uris[0]
        if uri._used > 0:
            uri = sorted(avl_uris, key=lambda u: u.average_speed(), reverse=True)[0]
        return uri

    def _find_avl_uris(self):
        more_used = sorted(self._uri_status.values(), key=attrgetter('_used'))
        return list(filter(lambda u: u.is_available(), more_used))

    def success(self, resp):
        block = _lookup_block()
        self._uri_status[block.current_uri().id].success(block, resp)

    def timeout(self, resp):
        block = _lookup_block()
        self._uri_status[block.current_uri().id].timeout(block, resp)

    def fatal(self, resp):
        block = _lookup_block()
        self._uri_status[block.current_uri().id].fatal(block, resp)

    async def run(self):
        self._stopped = False
        async_sleep = asyncio.sleep

        uri_status = self._uri_status
        while True:
            await async_sleep(1)
            if self._stopped:
                break

            for status in uri_status.values():
                status.refresh()

        self._cond = None

    async def pause(self):
        self._stopped = True

    async def close(self):
        pass

    def __repr__(self):
        return f'<URIStatusManager {self._uri_status} future={self._future}>'

    def info_getter(self):
        return {k: v.info() for k, v in self._uri_status.items()}


class ClientWorker(Handler):
    """ （主处理器）异步客户端调配工作器。

    负责工作：
        1. 客户端会话管理
        2. 下载块工作调配
        3. 工作进度检测
    """
    name = 'client_worker'

    def __init__(self):
        self._block_queue = None
        self._working_blocks = set()
        self._client_session = {}
        self._stopped = False
        self._executors = None
        self._tasks = set()

    async def prepare(self):
        self._stopped = False

        self._block_queue = asyncio.Queue()
        self._executors = ThreadPoolExecutor(
            max_workers=self.parent.config.max_concurrent,
            thread_name_prefix=self.parent.file.name
        )

    async def run(self):
        def goto_work(blo):
            """ 后台执行下载块。 """
            def cb(fut):
                # 回调移除工作下载块，并交由下载块检测
                self._block_queue.put_nowait(blo)
                self._working_blocks.remove(blo)

            task = asyncio.run_coroutine_threadsafe(
                self._worker(blo), loop)
            self._working_blocks.add(blo)
            task.add_done_callback(cb)
            return task

        loop = asyncio.get_running_loop()
        config = self.parent.config
        block_group = self.parent.block_grp

        # 准备未完成的下载块
        unfinished_blocks = block_group.unfinished_blocks()
        # 提交下载块到工作区
        while unfinished_blocks:
            block = unfinished_blocks.pop(0)
            await self.submit(block)

        # 对下载块做出处理决策
        work_queue = self._block_queue
        resume_capability = config.resume_capability
        while True:
            block = await work_queue.get()
            work_queue.task_done()
            if block is None:
                break
            if block.unused_length():
                # 重试下载块
                goto_work(block)
            else:
                # 检查任务是否完成
                if block_group.is_walk_finished():
                    missing = block_group.integrity_check()
                    if missing:
                        h.exception.handler_error(f'Missing Blocks: {missing}')
                    if unfinished_blocks:
                        await work_queue.put(unfinished_blocks.pop(0))
                        continue
                    break
                # 已完成其中一下载块后允许对未完成下载块进行切片补充并发量
                if resume_capability:
                    if len(block_group.unfinished_blocks()) < config.max_concurrent:
                        if unfinished_blocks:
                            goto_work(unfinished_blocks.pop(0))
                        else:
                            h.slicer.request()

        # 任务完成或暂停，清除冗余队列信息
        while not work_queue.empty():
            await work_queue.get()
            work_queue.task_done()

        # 待所有下载块退出
        while self._working_blocks:
            await work_queue.get()
            work_queue.task_done()

        self._executors.shutdown(False)
        # 非阻塞执行关闭所有handler
        self.parent.pause(0)

    async def submit(self, block):
        """ 提交下载块到工作区。
        Args:
            block: 下载块Block对象。
        """
        if self._stopped:
            return False
        await self._block_queue.put(block)

    async def _worker(self, block):
        """ 客户端工作worker。
        Args:
            block: 下载块Block对象。
        """
        def run_client_threadsafe():
            nonlocal cli, loop, handlers_ref, block
            token = block_context.set(block)
            with h.enter(handlers_ref, loop):
                try:
                    return cli.run()
                except BaseException as e:
                    h.exception.client_error(e)
                finally:
                    block_context.reset(token)

        if self._stopped:
            return
        handlers_ref = h.owner
        loop = asyncio.get_running_loop()
        config = self.parent.config

        # 准备下载源
        uri = await h.uri_mgr.get_uri()

        source_uri = uri.get_copy()
        resume_capability = config.resume_capability
        client_policy = config.client_policy

        solution = client_policy.get_solution(source_uri.protocol)

        # 准备客户端会话
        session = self._client_session.get(solution, None)
        if session is None:
            session = solution.get_session()
            self._client_session[solution] = session

        # 准备客户端处理器
        client = solution.get_client(
            session, source_uri, block.progress, resume_capability)

        # 为下载块准备客户端进行下载
        async with block.request(client) as cli:
            uri.use(block)
            try:
                if solution.is_async():
                    fut = cli.run()
                else:
                    fut = loop.run_in_executor(self._executors, run_client_threadsafe)
                result = await fut
            except BaseException as err:
                h.exception.client_error(err)
            uri.disuse(block)
        return result

    async def close(self):
        async def close_sess(sess):
            """ 关闭客户端会话。"""
            coro_or_result = sess.close()
            if asyncio.iscoroutine(coro_or_result):
                await coro_or_result
        await asyncio.gather(*[close_sess(session) for session in self._client_session.values()])
        self._client_session.clear()

    async def pause(self):
        async def pause_cli(blo):
            """ 安全暂停关闭客户端。"""
            while True:
                if blo not in self._working_blocks:
                    # 若下载块已退出，跳过客户端暂停
                    return
                if blo.client is None:
                    # 等待客户端进入，同时关闭
                    await asyncio.sleep(0)
                else:
                    break
            await blo.client.pause()

        if not self._stopped:
            self._stopped = True
            await asyncio.gather(*[pause_cli(block) for block in self._working_blocks])
            await self._block_queue.put(None)

    def __repr__(self):
        return f'<ClientWorker {self._working_blocks} future={self._future}>'

    def info_getter(self):
        return {
            'actives': set(self._working_blocks)
        }


class BlockSlicer(Handler):
    """ 下载块切片器。

    负责工作：
        1. 下载块切片请求和响应
    """
    name = 'slicer'

    def __init__(self):
        self._waiters = set()
        self._lock = threading.Lock()

    async def divide_into(self, n):
        """ 下载块切片器分成n份。

        该方法不建议在在下载块工作过程中进行调用，
        否则可能会出现传输数据冗余的问题。

        Args:
            n: 分成n份。
        """
        for i in range(n):
            self.request()
            while self._waiters:
                block = self._waiters.pop()
                self._slice(block)

    def _slice(self, source_block):
        req_range = source_block.half_unused()
        if req_range:
            result = source_block.slice(req_range)
            if result:
                block = self.parent.block_grp.insert(result)
                return block

        return None

    async def response(self):
        """ 客户端用于响应切片器是否需要对其进行切片。

        若切片器希望对当前下载块进行切片，调用该方法允许切片器安全的对当前下载块进行切片。
        安全的前提是该方法在不影响下载区间的地方调用。
        若当前下载块未在期望切片队列则直接跳过。
        """
        if self._waiters:
            with self._lock:
                source_block = _lookup_block()
                if source_block not in self._waiters:
                    return
                self._waiters.remove(source_block)
                resp = self._slice(source_block)
            if resp is not None:
                await h.client_worker.submit(resp)

    def response_threadsafe(self):
        with self._lock:
            if not self._waiters and _lookup_block() not in self._waiters:
                return False
        await_coroutine_threadsafe(self.response())

    def request(self):
        """ 请求一次下载块切片。

        使用最大剩余block大小策略来选择被切块对象，该方法并未对下载块进行切片，
        需要客户端配合response()方法来响应切片请求。
        """
        len_waiting = len(self._waiters)
        blocks = sorted(self.parent.block_grp.unfinished_blocks(), key=lambda i: i.unused_length(), reverse=True)
        self._waiters = set(blocks[:len_waiting + 1])
        return len(self._waiters) == len_waiting + 1

    async def prepare(self):
        # 下载块切片以保证下载块的最大并发量。
        config = self.parent.config
        if config.resume_capability:
            blocks_len = len(self.parent.block_grp.unfinished_blocks())
            if blocks_len < config.max_concurrent:
                await self.divide_into(config.max_concurrent - blocks_len)

    async def run(self):
        pass

    async def close(self):
        pass

    async def pause(self):
        self._waiters.clear()

    def __repr__(self):
        return f'<BlockSlicer {self._waiters} future={self._future}>'

    def info_getter(self):
        return {
            'waiters': set(self._waiters)
        }


class SpeedAdjuster(Handler):
    """ 速度调节器。

    负责工作：
        1. 最大速度限制
        2. 实时速度信息刷新
    """
    name = 'speed_adjuster'

    def __init__(self):
        self._opened = False
        self._stopped = True
        self._thread_cond = threading.Condition(threading.RLock())
        self._sema_value = 0
        self._async_cond = None

    async def _release_all(self):
        with self._thread_cond:
            async with self._async_cond:
                self._sema_value = float('inf')
                self._thread_cond.notify_all()
                self._async_cond.notify_all()

    def acquire_threadsafe(self):
        if self._opened:
            while True:
                with self._thread_cond:
                    value = self._sema_value
                    if value > 0:
                        self._sema_value -= 1
                        break
                    self._thread_cond.wait()
        return False

    async def acquire(self):
        if self._opened:
            while True:
                with self._thread_cond:
                    async with self._async_cond:
                        value = self._sema_value
                        if value > 0:
                            self._sema_value -= 1
                            break
                        await self._async_cond.wait()
        return False

    async def prepare(self):
        assert self._stopped
        self._async_cond = asyncio.Condition()
        self._stopped = False

    async def run(self):

        async_sleep = asyncio.sleep
        block_grp = self.parent.block_grp
        config = self.parent.config
        max_speed = config.max_speed
        fraction = 0
        if max_speed is not None:
            self._opened = True
        while True:
            if self._stopped:
                break
            await async_sleep(config.interval)

            # 刷新总的下载块实时传输速率
            block_grp.usage_info.refresh()

            # 当最大下载速度配置有变化后则响应相应的速度限速开关
            if config.max_speed != max_speed:
                # 最大速度限制参数被修改
                max_speed = config.max_speed
                if max_speed is None:
                    self._opened = False
                    await self._release_all()
                else:
                    self._opened = True
                    fraction = 0

            # 如果限制的下载速率就处理信号量
            if max_speed is not None:
                value = config.max_speed * config.interval / 8196

                # 由于下载客户端以单次读数据粒度进行限速，所以为了更细化的限速
                # 对计算出来的信号量粒度小数保留下来留给下次累加。
                fraction += value % 1
                value = int(value)
                if fraction >= 1:
                    value += 1
                    fraction -= 1
                with self._thread_cond:
                    async with self._async_cond:
                        self._sema_value = value
                        self._thread_cond.notify_all()
                        self._async_cond.notify_all()

    async def close(self):
        pass

    async def pause(self):
        if not self._stopped:
            self._stopped = True
            self._opened = False
            await self._release_all()

    def __repr__(self):
        return f'<SpeedAdjuster max_speed={self.parent.config.max_speed} future={self._future}>'

    def info_getter(self):
        return {
            'value': self._sema_value
        }


class FileTempData(Handler):
    """ 下载文件缓冲和保存的IO读写器。

    负责工作：
        1. 文件缓冲和写入
        2. 下载状态的保存
    """

    name = 'file_data'

    def __init__(self):
        self._buffers = defaultdict(list)
        self._counter = 0
        self._unreleased = None
        self._lock = threading.RLock()
        self._stopped = True

    async def saving_state(self):
        """ 保存当前下载状态。

        以cfg的文件形式保存当前下载配置以备文件下载状态的恢复。
        """
        dumpy = self.parent.dumps()
        async with h.aio.open(f'{self.parent.file.pathname}{self.parent.config.downloading_ext}.cfg', mode='w') as f:
            await f.write(json.dumps(dumpy))

    async def _release(self):
        buffers = self._buffers
        counter = self._counter
        self._counter = 0
        self._buffers = defaultdict(list)
        return await self._unreleased.put((counter, buffers))

    def store_threadsafe(self, data):
        """ 线程安全保存临时下载数据。"""
        with self._lock:
            block = _lookup_block()
            self._buffers[block.progress].append(data)
            self._counter += len(data)
            if self.parent.config.buffer_size <= self._counter:
                await_coroutine_threadsafe(self._release())

    async def store(self, data):
        """ 缓冲传输数据。

        当缓冲的数据超过了buffer_size，将对缓冲进行释放写入文件。

        Args:
            data: 要被缓冲的传输数据
        """
        block = _lookup_block()
        self._buffers[block.progress].append(data)
        self._counter += len(data)
        if self.parent.config.buffer_size <= self._counter:
            await self._release()

    async def prepare(self):
        assert self._stopped
        self._unreleased = asyncio.Queue()
        self._stopped = False

    async def run(self):
        unreleased = self._unreleased
        file = self.parent.file
        filepath = f'{file.pathname}{self.parent.config.downloading_ext}'

        # 通过下载块是否有walk_length的情况来判断是否需要重写文件。
        if not self.parent.block_grp.done_length():
            async with h.aio.open(f'{file.pathname}{self.parent.config.downloading_ext}', mode='wb') as fd:
                if file.size is not None:
                    await fd.seek(file.size - 1)
                    await fd.write(b'\x00')

        async with h.aio.open(filepath, mode='rb+') as fd:
            while True:
                result = await unreleased.get()
                if result is None:
                    unreleased.task_done()
                    break
                counter, buffers = result
                for pg, lines in buffers.items():
                    await fd.seek(pg.begin + pg.done_length)
                    await fd.writelines(lines)
                    pg.done(sum([len(line) for line in lines]))

                # 删除引用，尽快回收垃圾
                del lines
                del result
                del buffers
                await self.saving_state()
                unreleased.task_done()

    async def pause(self):
        if not self._stopped:
            self._stopped = True
            await h.client_worker.join()
            await self._release()
            await self._unreleased.put(None)

    async def close(self):
        pass

    def info_getter(self):
        return {
            'size': self._counter,
            'ready': 1
        }

    def __repr__(self):
        return f'<FileTempData counter={self._counter} future={self._future}>'


class AIOReaderWriter(Handler):
    """ AIO读写工作线程。

    为了避免IO的文件读写阻塞影响下载工作线程，该处理器实现异步文件IO读写方法

    负责工作：
        1. 管理IO读写线程
    """
    name = 'aio'

    def __init__(self):
        self._executor = None
        self._writers = set()

    async def prepare(self):
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f'BufferWriter {self.parent.file.name}')

    @asynccontextmanager
    async def open(self, file, mode='r', *args, **kwargs):
        """ 异步打开文件。

        Args:
            file: 参见io.open()方法参数file
            mode: 参见io.open()方法参数mode
            args: 参见io.open()方法参数的列表参数
            kwargs: 参见io.open()方法参数字典参数

        Returns:
            异步文件对象AsyncIOFile，对耗时IO文件操作进行异步定义。
        """
        def async_open():
            return open(file, mode, *args, **kwargs)

        executor = self._executor
        assert executor
        loop = asyncio.get_running_loop()
        fd = await loop.run_in_executor(executor, async_open)
        aiofile = AIOFile(executor, fd, loop=loop)
        self._writers.add(aiofile)
        yield aiofile
        # 关闭文件
        await loop.run_in_executor(executor, fd.close)
        self._writers.remove(aiofile)

    async def run(self):
        pass

    async def close(self):
        for handler in h.iter_all():
            if handler != self:
                await handler.join()
        self._executor.shutdown(False)

    async def pause(self):
        pass


class AIOFile:
    """ 异步文件读写对象。

    由AIOReaderWriter的工作线程处理的异步读写对象，将耗时的IO读写由工作线程执行。
    """
    _async_attr = frozenset(
        {'read', 'readline', 'readlines', 'write', 'writeline',
         'writelines', 'seek', 'flush', 'truncate'})

    def __init__(self, executor, fd, loop=None):
        self._executor = executor
        self._fd = fd
        self._loop = loop

    def __getattr__(self, item):
        func = getattr(self._fd, item)
        if item in self._async_attr:
            def ready(*args, loop=None, **kwargs):
                if loop is None:
                    loop = asyncio.get_running_loop()

                if kwargs:
                    handler = partial(getattr(self._fd, item), **kwargs)
                else:
                    handler = getattr(self._fd, item)
                fut = loop.run_in_executor(self._executor, handler, *args)
                return fut
            func = ready

        return func

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __repr__(self):
        return f'<AIOFile {self._fd}>'
