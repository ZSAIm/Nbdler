# -*- coding: UTF-8 -*-

from .utils.misc import BaseInfo, Component

DEFAULT_BLOCK_UNIT_SIZE = 512 * 1024
DEFAULT_MAX_BUFF_SIZE = 10 * 1024 * 1024
DEFAULT_OPEN_MAX_RETRIES = 5
DEFAULT_MAX_THREAD = 3
DEFAULT_TIMEOUT = 5
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/74.0.3729.169 Safari/537.36',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br'
}


class BaseRequest:

    def __init__(self, file_path='', max_thread=DEFAULT_MAX_THREAD, max_buff=DEFAULT_MAX_BUFF_SIZE,
                 unit_size=DEFAULT_BLOCK_UNIT_SIZE, max_retries=DEFAULT_OPEN_MAX_RETRIES, timeout=DEFAULT_TIMEOUT,
                 nbcfg=None, overwrite=False, **options):
        """
        :param
            file_path:  目标文件的路径名称
            max_thread: 下载块单元大小
            max_buff:   最大请求次数仅用于dlopen的时候尝试的次数。
            unit_size:  下载客户端的最大线程数量。
            max_retries:内存缓冲的最大值。
            timeout:    下载客户端的超时参数。None一般代表着时无限阻塞链接。
            nbcfg:      下载配置文件的路径名称，若不指定通常放在与下载文件的同一个路径并且使用nbcfg后缀。
            overwrite:  如果overwrite=False，程序会在名称添加(索引)来自动更新文件名来避免文件的覆盖。
            options:    保存提供的额外参数，以在后续提供给下载客户端来让客户端进行选择调整。
                        - downloading_extension:    下载中文件扩展名
                        - heartbeat_interval:       心跳刷新间隔
        """
        self.file_path = file_path
        self.unit_size = unit_size
        self.max_retries = max_retries
        self.max_thread = max_thread
        self.max_buff = max_buff
        self.timeout = timeout
        self.nbcfg = nbcfg
        self.overwrite = overwrite
        self.options = options

    def __snapshot__(self):
        return {
            'file_path': self.file_path,
            'unit_size': self.unit_size,
            'max_retries': self.max_retries,
            'max_thread': self.max_thread,
            'max_buff': self.max_buff,
            'timeout': self.timeout,
            'nbcfg': self.nbcfg,
            'overwrite': self.overwrite,
            'options': self.options
        }


class Request(BaseRequest, Component):
    def __init__(self, url=None, headers=None, cookie=None,
                 proxy=None, max_thread=None, range_format=None, name='main', **options):
        super(Request, self).__init__(**options)
        self._sources = []
        if url:
            self.put(url, headers, cookie, proxies=proxy,
                     max_conn=max_thread, format_range=range_format, name=name)

    def put(self, url, headers=None, cookie=None,
            proxies=None, max_conn=None, format_range=None, name=None):
        """ 添加下载源。 """
        url = url.strip()
        src_url = UrlInfo(url, headers, cookie, proxies, max_conn, format_range, str(name))
        self._sources.append(src_url)
        return src_url

    @property
    def configure(self):
        """ 返回请求的基本配置信息。"""
        return super(Request, self).__snapshot__()

    def __snapshot__(self):
        snapshot = self.configure
        snapshot.update({
            'sources': [url.dict() for url in self._sources]
        })
        return snapshot

    def __iter__(self):
        return iter(self._sources)

    @staticmethod
    def load(dict_data):
        sources = dict_data.pop('sources')
        # 为了使得以原参数名进入options，这里将options的参数字典更新进入dict_data
        options = dict_data.pop('options')
        dict_data.update(options)
        req = Request(**dict_data)
        for src in sources:
            req.put(**src)
        return req


class RequestGroup(Component):
    """ 请求组，以组为单位作为一个请求。"""
    def __init__(self, maxsize, subprocess=False, daemon=False, max_speed=None, max_buff=None):
        """
        :param
            maxsize     : 同时最大下载数
            daemon      : 下载器线程是否为守护线程
            subprocess  : 是否在子进程模式下运行
        """
        assert maxsize > 0
        self._requests = []
        self.maxsize = maxsize
        self.subprocess = subprocess
        self.daemon = daemon
        self.max_speed = max_speed
        self.max_buff = max_buff

    def put(self, request):
        """ 添加下载请求到请求池。 """
        self._requests.append(request)

    @property
    def configure(self):
        return {
            'maxsize': self.maxsize,
            'subprocess': self.subprocess,
            'daemon': self.daemon,
            'max_speed': self.max_speed,
            'max_buff': self.max_buff
        }

    def __snapshot__(self):
        snapshot = self.configure
        snapshot.update({
            'requests': [request.__snapshot__() for request in self._requests]
        })
        return snapshot

    def __iter__(self):
        return iter(self._requests)

    def __len__(self):
        return len(self._requests)


class UrlInfo(BaseInfo):

    def __init__(self, url, headers, cookie, proxies, max_conn, format_range, name):
        self.url = url
        self.headers = headers
        self.cookie = cookie
        self.proxies = proxies
        self.max_conn = max_conn
        self.format_range = format_range
        self.name = name


