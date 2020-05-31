
import json
import mimetypes
import os
import asyncio
from concurrent.futures.thread import ThreadPoolExecutor
from .utils import forever_loop_in_executor

from .download import Downloader
from .client import get_policy
from .uri import URIs
from .progress import Progress
from .error import MaxRetriesExceeded
from .block import BlockGroup
from .file import File
from .request import Request


__all__ = [
    'dlopen',
]


def dlopen(request, handlers=None, *, do_async=True, executors=None):
    """ 打开下载请求Request对象，并构造返回Downloader。
    Args:
        request: 下载请求对象或下载配置文件路径。
        handlers: 添加的Handler对象列表，仅适用于打开下载配置文件
        do_async: 是否使用异步打开
        executors: 使用指定的concurrent.futures.thread打开，默认新创线程执行。
    """
    async def open_request():
        # 打开请求Request对象
        client_policy = request.client_policy
        if client_policy is None:
            client_policy = get_policy()

        uris = URIs.load_from_source_uris(request.uris)
        progress = Progress((0, None))
        source_uri = None
        resp = None
        exceptions = []

        max_retries = request.max_retries
        if request.max_retries is None:
            max_retries = float('inf')

        while True:
            for source_uri in uris:
                try:
                    client_cls = client_policy.get_solution(source_uri.protocol)
                    resp = await client_cls.dlopen(
                        source_uri, progress, **source_uri.kwargs)
                except BaseException as err:
                    exceptions.append(err)
                    max_retries -= 1
                    if max_retries < 0:
                        raise MaxRetriesExceeded(f'max_retries: {request.max_retries}', exceptions)
                else:
                    break
            else:
                continue
            break

        source_uri.set_response(resp)
        path, name = os.path.split(request.file_path)
        if not name:
            name = source_uri.path.rsplit('/', 1)[-1]
            if not name:
                ext = mimetypes.guess_extension(resp.content_type)
                name = f'{source_uri.hostname}{ext or ""}'
        size = resp.length

        block_grp = BlockGroup(request.chunk_size, size)
        block_grp.insert((0, size))
        opts = request.opts
        opts.update(dict(
            client_policy=client_policy,
            resume_capability=resp.resume_capability,
        ))
        return Downloader(
            File(path, name, size),
            uris,
            block_grp,
            **opts
        )

    async def open_cfg():
        # 打开下载配置文件
        file = request
        if not os.path.isfile(file):
            raise FileNotFoundError(f'下载数据配置文件{file}未找到。')
        with open(file, mode='r') as fd:
            dumpy_json = fd.read()
        dumpy = json.loads(dumpy_json)
        return Downloader.loads(dumpy, handlers)

    async def do_open():
        if isinstance(request, Request):
            return await open_request()
        else:
            return await open_cfg()

    def callback(fut):
        executors.shutdown(False)

    new_executor = False
    if executors is None:
        executors = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='Nbdler.dlopen() Worker')
        new_executor = True

    exec_fut = forever_loop_in_executor(executors)
    if new_executor:
        exec_fut.add_done_callback(callback)

    loop = exec_fut.get_loop()
    if do_async:
        def done_stop_loop(fut):
            nonlocal exec_fut
            exec_fut.close()

        future = asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(do_open(), loop=loop))
        future.add_done_callback(done_stop_loop)
        result = _AsyncDownloadOpenContextManager(future)
    else:
        result = exec_fut.result()
        exec_fut.close()
    return result


class _AsyncDownloadOpenContextManager:
    __slots__ = '_future', '_result'

    def __init__(self, future):
        self._future = future
        self._result = None

    def __await__(self):
        return self._future.__await__()

    def __iter__(self):
        return self.__await__()

    async def __aenter__(self):
        self._result = await self._future
        return await self._result.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._result.__aexit__(exc_type, exc_val, exc_tb)
