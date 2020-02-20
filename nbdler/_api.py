# -*- coding: UTF-8 -*-
import os

from .request import Request, RequestGroup
from .downloader import Downloader
from .downloader.client import get_client
from .downloader.console import Console
from .downloader.file import File
from .downloader.struct.block import BlockManager
from .downloader.struct.progress import Progress
from .downloader.url.manager import UrlManager
from .error import RequestError, MaxRetriesExceededError, MissingBlockError
from .utils import saver


def dlopen(request, max_retries=None, **configure):
    """
    如果request提供的是str类型，那么将作为下载配置文件的路径读取导入下载器。
    如果request提供的是Request对象，那么将作为新的下载文件进行处理。

    :param
        request     : 下载请求对象Request
        max_retries : 最大重试次数

        基本下载配置属性：
        **configure : 下载配置
            max_thread  : 下载线程数。
            unit_size   : 下载块单元大小。
            max_buff    : 最大下载磁盘缓存大小。
            timeout     : 客户端连接超时时间。
    :return
        Downloader  : 下载器对象
    """
    if type(request) is str:
        dl = _dlopen_nbcfg(request, **configure)
    elif isinstance(request, Request):
        dl = _dlopen_request(request, max_retries, **configure)
    elif isinstance(request, RequestGroup):
        dl = _dlopen_group(request, **configure)
    else:
        raise TypeError('参数request不支持的类型。')

    return dl


def _dlopen_request(request, max_retries=None, **configure):
    """ 打开下载请求对象，并构建返回下载对象。"""
    # :::::建立下载配置，dlopen的配置信息优先于request的配置信息。
    actual_config = request.configure
    # 移除options选项，而是进行更新进来
    actual_config.pop('options')
    # 将额外参数添加到控制台配置的options参数里面，以提供给下载客户端。
    actual_config.update(request.options)
    actual_config.update(configure)

    # 预备构建下载对象。
    url = UrlManager()
    # 创建初始化打开进度
    progress = Progress((0,))
    url.open_request(request)

    max_retries = max_retries or actual_config.pop('max_retries')

    source_wrap = url.get(0)

    source = source_wrap.get()
    cli_hdl = get_client(source.protocol)

    while True:
        try:
            # 尝试使用下载客户端收集下载对象所需信息。
            cli, name, size, partial = cli_hdl.dlopen(source, progress, True, timeout=request.timeout)
        except RequestError as e:
            if max_retries is None or max_retries > 0:
                continue
            raise MaxRetriesExceededError(e)
        else:

            # :::::建立文件File对象
            size = size or float('inf')
            path, request_name = os.path.split(actual_config.pop('file_path'))
            if request_name:
                name = request_name
            overwrite = actual_config.pop('overwrite')
            downloading_extension = actual_config.get('downloading_extension', '.downloading')
            file = File(path, name, size, overwrite=overwrite, downloading_extension=downloading_extension)

            # :::::建立下载块实体和管理器对象
            # 更新进度文件信息。
            progress = Progress((0, size))
            # 更新客户端的进度对象，因为这个客户端在后续需要使用。
            cli.progress = progress
            # 构建下载块映射图对象。
            block_mgr = BlockManager(request.unit_size, file.size)
            block_mgr.insert(cli, progress)

            # :::::更新下载配置文件路径信息
            if not actual_config['nbcfg']:
                actual_config['nbcfg'] = os.path.join(file.path, file.name) + '.nbcfg'
            # 非partial请求的情况下强制最大线程数1条，避免多开线程。
            if not partial:
                actual_config['max_thread'] = 1

            # :::::创建配置控制台。
            console = Console(file, url, block_mgr, partial, **actual_config)
            # 装配下载器
            dl = Downloader(console, True)
            return dl


def _dlopen_nbcfg(request, fix_error=True, **configure):
    """ 打开nb下载配置文件，并构建返回下载器对象。"""
    # 下载配置文件路径
    snapshot = saver.load(request, method=('gzip', 'json'))
    console = Console.load(snapshot)
    # 更新下载配置文件。
    configure['nbcfg'] = request
    console.config(**configure)
    dl = Downloader(console, False)
    # 下载配置文件下载块完整性检查。
    missing = dl.block_mgr.integrity_check()
    if missing:
        if not fix_error:
            raise MissingBlockError(missing)
        else:
            # 自动填补缺失的下载块。
            source_wrap = dl.url.get(0)
            source = source_wrap.get()
            for r in missing:
                progress = Progress(r)
                client = get_client(source_wrap).dlopen(source, progress, True, timeout=dl.body.config['timeout'])
                dl.block_mgr.insert(client, progress)

    return dl


def _dlopen_group(request_group, **configure):
    """ 打开请求组建立下载管理池。"""
    from .manager.manager import Manager
    config = request_group.configure
    config.update(configure)
    mgr = Manager(**config)
    for request in request_group:
        mgr.putrequest(request)

    return mgr
