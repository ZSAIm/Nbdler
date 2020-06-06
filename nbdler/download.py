
from concurrent.futures.thread import ThreadPoolExecutor
from nbdler.handler import (
    SpeedAdjuster,
    AIOReaderWriter,
    BlockSlicer,
    FileTempData,
    ClientWorker,
    URIStatusManager,
    GatherException,
    h, Handlers)
from .client import get_policy, ClientPolicy
from .version import VERSION
from .utils import forever_loop_in_executor
from traceback import format_exc
import weakref
import warnings
import asyncio
import os

__all__ = (
    'Downloader',
)


class DownloadConfigure:
    ADJUSTABLE = frozenset(
        {'max_concurrent', 'max_speed', 'buffer_size', 'timeout', 'interval', 'client_policy'})

    def __init__(self, resume_capability, max_concurrent, chunk_size, buffer_size, timeout=10,
                 max_speed=None, downloading_ext='.downloading', interval=0.5, client_policy=None, **kwargs):

        self.version = VERSION
        self.resume_capability = resume_capability
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.buffer_size = buffer_size
        self.timeout = timeout
        self.interval = interval
        self.max_speed = max_speed
        self.downloading_ext = downloading_ext
        self.client_policy = client_policy
        self.kwargs = kwargs

    def set(self, **kwargs):
        """ 设置配置。
        Args:
            **kwargs:
                max_concurrent: 最大并发数
                max_speed: 最大速度限制
                buffer_size: 最大文件缓冲大小
                timeout: 客户端连接接收超时时间
                interval: 速度调节间隙
                client_policy: 客户端处理策略
        """
        attrs = set(kwargs).intersection(DownloadConfigure.ADJUSTABLE)
        for attr in attrs:
            self.__setattr__(attr, kwargs[attr])

    def dumps(self):
        opts = dict(self.__dict__)
        client_policy = self.client_policy
        opts['client_policy'] = dict(client_policy)
        opts.update(opts.pop('kwargs'))
        return opts

    @classmethod
    def loads(cls, dumpy):
        config = cls(**dumpy)
        if not isinstance(config.client_policy, ClientPolicy):
            config.client_policy = get_policy(**config.client_policy)
        return config

    def __repr__(self):
        return (f'<DownloadConfigure version={self.version} max_concurrent={self.max_concurrent} '
                f'resume_capability={self.resume_capability}>')


class Downloader:
    def __init__(self, file, uris, block_grp, *, handlers=None, **kwargs):

        self.file = file
        self.uris = uris
        self.block_grp = block_grp
        self.config = DownloadConfigure.loads(kwargs)

        self._executor = None

        self._loop = None
        self._future = None
        self._closed = False
        self._handlers = Handlers()

        if handlers is None:
            handlers = []

        buildin_handlers = [
            ClientWorker,
            SpeedAdjuster,
            FileTempData,
            AIOReaderWriter,
            BlockSlicer,
            GatherException,
            URIStatusManager,
        ]
        handlers.extend(buildin_handlers)
        for handler in handlers:
            if handler.name in self._handlers:
                continue
            if isinstance(handler, type):
                handler = handler()

            handler.add_parent(weakref.proxy(self))
            self._handlers[handler.name] = handler

    def exceptions(self, exception_type=None, *, just_new_exception=True):
        """ 线程安全获取异常

        以生成器的形式获取内部发生的异常，当下载任务暂停或者完成后将中断生成器的迭代。
        使用方式：
            for exception in dl.exceptions():
                do_some_works(exception)

        Args:
            exception_type: 指定异常类型，可选ClientError、HandlerError。默认None则获取所有异常。
            just_new_exception: 是否忽略当前时间前的旧异常，仅返回之后的新异常。

        Yields:
            内部出现的client或handler异常对象。
        """
        yield from self._handlers.exception.acquire_threadsafe(
            exception_type, just_new_exception=just_new_exception)

    def aexceptions(self, exception_type=None, *, just_new_exception=True):
        """ 异步返回异常错误。 具体参见exceptions()方法。
        使用方式：
            async for exception in dl.aexceptions():
                do_some_works(exception)
        """
        return self._handlers.exception.acquire(
            exception_type, just_new_exception=just_new_exception)

    async def astart(self):
        """ 在当前事件循环中运行下载器。"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')
        loop = asyncio.get_running_loop()
        self._loop = loop
        if self.block_grp.is_done_finished():
            raise RuntimeError('download is completed.')

        self._future = loop.create_future()

        async def handler_worker(hd):
            try:
                return await hd.start()
            except BaseException as err:
                h.exception.handler_error(format_exc())
                self.pause(0)

        with h.enter(self._handlers, loop):
            self.block_grp.activate()
            # prepare()
            await self._handlers.prepare()
            # start()
            result = await asyncio.gather(
                *[handler_worker(handler) for handler in h.iter_all()]
            )
            # join()
            await self._handlers.join()
            self.block_grp.deactivate()

        self._future.set_result(result)

    def start(self, *, loop=None):
        """ 在指定的循环中运行下载器。

        若loop=None不指定事件循环，那么将创建新的线程作为下载器的事件循环。

        Args:
            loop: 指定事件循环运行下载器

        Returns:
            返回下载器运行的concurrent.future.Future对象
        """

        if self._closed:
            raise RuntimeError('Downloader is already closed.')

        if self.block_grp.is_finished():
            raise RuntimeError('download is already finished.')

        if self._loop is not None:
            loop = self._loop

        if loop is None:
            def cb(f):
                nonlocal executor
                executor.shutdown(False)

            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix=f'Downloader {self.file.name} {self.file.size}')
            exec_fut = forever_loop_in_executor(executor)
            exec_fut.add_done_callback(cb)
            self._executor = executor
            loop = exec_fut.get_loop()

        fut = asyncio.run_coroutine_threadsafe(self.astart(), loop=loop)
        self._loop = loop
        return fut

    async def apause(self):
        """ 异步暂停等待。"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')
        result = await self._await_loopsafe(self._handlers.pause())
        await self.ajoin()
        return result

    async def aclose(self):
        """ 异步关闭下载器。"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')

        if not self._future.done():
            raise RuntimeError('cannot close a running Downloader.')
        result = await self._await_loopsafe(self._handlers.close())
        await self.ajoin()
        self._closed = True

        if self._executor:
            self._loop.call_soon_threadsafe(self._loop.stop)

        # 若文件已完毕，去除.downloading后缀
        if self.block_grp.is_done_finished():
            file = self.file
            filepath = f'{file.pathname}{self.config.downloading_ext}'
            start_filepath = file.pathname
            target_filepath = start_filepath
            postfix = 0
            while True:
                try:
                    os.rename(filepath, target_filepath)
                except FileExistsError:
                    postfix += 1
                    target_filepath = os.path.join(file.path, file.number_name(postfix))
                else:
                    if postfix != 0:
                        file.name = file.number_name(postfix)
                    break

            # 删除下载配置文件
            os.unlink(f'{start_filepath}{self.config.downloading_ext}.cfg')
        return result

    async def ajoin(self):
        """ 异步等待下载器结束。"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')
        return await self._await_loopsafe(self._future)

    async def _await_loopsafe(self, *coros_or_futures):
        """ 事件循环安全的异步等待。

        Args:
            *coros_or_futures: coroutine或future对象列表。

        Returns:
            返回coros_or_futures的返回结果列表。
        """
        current_loop = asyncio.get_running_loop()
        loop = self._loop
        if loop is None:
            loop = current_loop

        async def _execute_loop():
            with h.enter(self._handlers):
                r = await asyncio.gather(*coros_or_futures)
                return r
        fut = asyncio.run_coroutine_threadsafe(_execute_loop(), loop)
        result = await asyncio.wrap_future(fut)

        return result

    def _call_threadsafe(self, coroutine, timeout=None):
        """ 下载器的异步操作线程安全化。
        Args:
            coroutine: 异步操作协程
            timeout: 超时等待事件

        Returns:
            当timeout=0时，返回concurrent.future.Future对象，
            否则，协程coroutine的执行结果或抛出超时异常。
        """
        loop = self._loop
        assert loop
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        if timeout == 0:
            return future
        return future.result(timeout)

    def pause(self, timeout=None):
        """ 线程安全暂停下载器。具体参见apause方法"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')
        return self._call_threadsafe(self.apause(), timeout=timeout)

    def close(self, timeout=None):
        """ 线程安全关闭下载器。具体参见aclose方法"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')
        return self._call_threadsafe(self.aclose(), timeout=timeout)

    def join(self, timeout=None):
        """ 线程安全等待下载器。具体参见ajoin方法"""
        if self._closed:
            raise RuntimeError('Downloader is already closed.')
        return self._call_threadsafe(self.ajoin(), timeout=timeout)

    def dumps(self):
        dumpy = {
            'config': self.config.dumps(),
            'file': self.file.dumps(),
            'uris': self.uris.dumps(),
            'block_grp': self.block_grp.dumps(),
        }
        return dumpy

    @classmethod
    def loads(cls, dumpy, handlers=None):
        from nbdler.uri import URIs
        from nbdler.file import File
        from nbdler.block import BlockGroup

        uris = URIs.loads(dumpy['uris'])
        file = File(**dumpy['file'])
        block_grp = BlockGroup.loads(dumpy['block_grp'])
        return cls(file, uris, block_grp, handlers=handlers, **dumpy['config'])

    transfer_rate = property(lambda self: self.block_grp.transfer_rate)

    average_speed = property(lambda self: self.block_grp.average_speed)

    walk_length = property(lambda self: self.block_grp.walk_length)

    done_length = property(lambda self: self.block_grp.done_length)

    remaining_length = property(lambda self: self.block_grp.remaining_length)

    remaining_time = property(lambda self: self.block_grp.remaining_time)

    percent_complete = property(lambda self: self.block_grp.percent_complete)

    is_walk_finished = property(lambda self: self.block_grp.is_walk_finished)

    is_done_finished = property(lambda self: self.block_grp.is_done_finished)

    def is_finished(self):
        """ 返回文件是否下载完毕。"""
        return self.block_grp.is_finished() and (not self._future or self._future.done())

    def set_config(self, **kwargs):
        """ 配置下载器。参见DownloadConfigure.set()方法。"""
        self.config.set(**kwargs)

    def __repr__(self):
        running = False
        if self._future is not None and not self._future.done():
            running = True
        return f'<Downloader filename={self.file.name} running={running} closed={self._closed}>'

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.aclose()

    def __del__(self, _warnings=warnings):
        if not self._closed:
            self.close()


