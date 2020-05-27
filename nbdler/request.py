# -*- coding: UTF-8 -*-

from nbdler.uri import SourceURI
from typing import Sequence, Mapping, AnyStr, Union, Optional
from nbdler.client import ClientPolicy
import bisect


class RequestConfig:
    def __init__(self, *, file_path: AnyStr,
                 max_concurrent: int=5,
                 buffer_size: int=20*1024*1024,
                 chunk_size: int=64*1024,
                 max_retries: Optional[int]=3,
                 timeout: Optional[int]=10,
                 client_policy: Optional[ClientPolicy]=None,
                 **kwargs):
        """
        Args:
            file_path: 目标文件的路径名称
            max_concurrent: 最大并发数
            buffer_size: 最大请求次数仅用于dlopen的时候尝试的次数。
            chunk_size: 下载客户端的最大线程数量。
            max_retries: 内存缓冲的最大值。
            timeout: 下载客户端的超时参数。None一般代表着时无限阻塞链接。
            client_policy: 指定客户端处理策略，默认策略由 nbdler.client.__init__._DEFAULT_POLICY 指定
            **kwargs: 保存提供的额外参数，以在后续提供给下载客户端来让客户端进行选择调整。
                      - downloading_ext: 下载中文件扩展名
                      - interval: 心跳刷新间隔
        """
        self.file_path = file_path
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.buffer_size = buffer_size
        self.timeout = timeout
        self.client_policy = client_policy
        self.handlers = []
        self.kwargs = kwargs

    def add_handler(self, *handlers):
        """ 添加或更新下载处理器。
        Args:
            *handlers: 继承nbdler.handler.Handler类的处理器列表参数，
                       通过名称标识处理器，类变量name作为处理器唯一标识。
                       与内置处理器重名则替换内置处理器。
                       内置处理器有:
                       - client_worker: 客户端调配控制器
                       - slicer: 下载块切片器
                       - speed_adjuster: 速度调节器，用于限速和实时速率刷新
                       - uri_mgr: 下载源状态管理器
                       - exception: 异常收集处理器
                       - file_data: 文件缓冲区
                       - aio: 异步文件读写工作线程
        """
        for handler in handlers:
            bisect.insort(self.handlers, handler)

    def __repr__(self):
        return f'<BaseRequest {self.file_path}>'


class Request(RequestConfig):

    def __init__(self, uri=None, headers=None, cookies=None, proxies=None,
                 max_conn=None, range_field=None, name='main', *, file_path, **kwargs):
        """
        Args:
            uri,headers,cookies,proxies,max_conn,range_field,name: 参考put()方法。
            **kwargs: 参考RequestConfig的__init__()方法
        """
        super(Request, self).__init__(file_path=file_path, **kwargs)
        self._uris = []
        if uri:
            kwargs = {k: kwargs[k] for k in set(kwargs).difference(self.__dict__)}
            self.put(uri, headers, cookies, proxies=proxies,
                     max_conn=max_conn, range_field=range_field, name=name, **kwargs)

    def put(self, uri: AnyStr,
            headers: Optional[Union[Sequence, Mapping[str, str]]]=None,
            cookies: Optional[Mapping[str, str]]=None,
            proxies: Optional[Mapping]=None,
            max_conn: Optional[int]=None,
            range_field: Optional[Mapping[str, str]]=None,
            name: Optional[str]=None,
            **kwargs):
        """ 添加下载源。
        Args:
            uri: URI链接
            headers: 请求头
            cookies: 下载源请求传递的Cookie，要求传递字典dict类型
            proxies: 代理服务器，带auth例子：{'http': 'http://user:pass@some.proxy.com'}
            max_conn: 最大连接数
            range_field: 范围请求定义，要求提供字典类型，如 {'Range': 'bytes={begin}-{end_with}'}
            name: 下载源名称，仅用于标记，默认不提供，系统自动编号
            **kwargs: 允许根据下载源参数指定客户端的特定操作。
                - trust_env:          使用系统代理

        Returns:
            返回未经编号的下载源。
        """
        uri = uri.strip()
        src_url = SourceURI(None, uri, headers, cookies, proxies, max_conn, range_field, name, **kwargs)
        self._uris.append(src_url)
        return src_url

    @property
    def opts(self):
        """ 返回请求中的配置字典信息。

        Returns:
            返回配置信息字典，具体键值参考RequestConfig。
        """
        opts = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        opts.update(opts.pop('kwargs'))
        return opts

    @property
    def uris(self):
        return self._uris

    def __repr__(self):
        return f'<Request {self._uris and self._uris[0].uri}>'

    def dumps(self):
        return {
            'config': self.opts,
            'uris': [uri.dumps() for uri in self._uris]
        }

    @classmethod
    def loads(cls, dumpy):
        request = cls(**dumpy['config'])
        for uri in dumpy['uris']:
            request.put(**uri)
