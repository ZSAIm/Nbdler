# -*- coding: UTF-8 -*-

from .base import BaseClient
from ...error import (URLError, NotAPartialResponse, UnknownError, RequestError)
from nbdler.event import (
    EVT_TASK_SLICE, EVT_TASK_PAUSING, EVT_CLIENT_WAIT, EVT_CLIENT_SWITCH, EVT_CLIENT_RECV_EMPTY,
    EVT_URL_TIMEOUT, EVT_URL_UNKNOWN, EVT_URL_GAIERROR, EVT_URL_NORMAL, EVT_URL_STATUS, EVT_URL_UNAVAILABLE,
    EVT_BUFFER_COUNT,
)
from urllib.error import URLError as urllib_URLError, HTTPError as urllib_HTTPError
from urllib.request import proxy_bypass, getproxies
from urllib.parse import urlunparse, urlparse
from http.client import HTTPConnection, HTTPSConnection
from wsgiref.headers import Headers
from time import sleep, time_ns
from re import search as re_search
from functools import partial as partial_func
import ssl
import socket


unverified_context = ssl._create_unverified_context()
verified_context = ssl.create_default_context()


class HTTP4XXError(URLError):
    """ HTTP Client Error. """


class HTTP5XXError(URLError):
    """ HTTP Server Error. """


class HTTPClient(BaseClient):
    CONNECT_TIMEOUT = 10
    HTTPS_CONTEXT = verified_context

    def _create_connection(self):
        """ 创建HTTP/HTTPS客户端连接。"""
        # :::::代理
        # 添加系统环境代理
        is_proxied_https_request = False
        actual_host = self.source.hostname
        actual_port = self.source.port
        proxies = self.source.proxies
        proxy = None
        if proxies:
            # 若设置了代理直接走代理，不需要旁路判断
            if proxy_bypass(self.source.hostname):
                env_proxies = {}
            else:
                env_proxies = getproxies()
            for k, v in env_proxies.items():
                proxies.setdefault(k, v)

            # 选择代理
            proxy = proxies.get(self.source.protocol, None)
            if proxy is not None:
                if self.source.protocol == 'https':
                    is_proxied_https_request = True
                scheme, netloc, path, params, query, fragment = urlparse(proxy, 'http')
                if not netloc:
                    netloc, path = path, netloc
                proxy_url = urlunparse((scheme, netloc, path, params, query, fragment))
                parse = urlparse(proxy_url)

                actual_host = parse.hostname
                actual_port = parse.port

        # :::::建立连接
        if self.source.protocol == 'http':
            conn_hdl = HTTPConnection
        else:
            conn_hdl = partial_func(HTTPSConnection, context=self.options.get('https_context', HTTPClient.HTTPS_CONTEXT))

        conn = conn_hdl(host=actual_host, port=actual_port,
                        timeout=self.options.get('timeout', HTTPClient.CONNECT_TIMEOUT))

        # :::::构建请求头
        request_range = None
        if self.partial:
            request_range = (self.progress.begin + self.progress.increment_go, self.progress.end)
        
        request_uri, headers = self._build_request_headers(request_range)

        if is_proxied_https_request:
            conn.set_tunnel(self.source.netloc)
            conn.connect()

        # 若非代理下request_uri使用path_query
        if not proxy:
            parse_uri = urlparse(request_uri)
            request_uri = parse_uri.path
            if parse_uri.query:
                request_uri += '?' + parse_uri.query

        conn.request('GET', request_uri, None, dict(headers))

        return conn

    def _auto_redirect(self, conn):
        """ 自动处理重定向请求。"""
        res = conn.getresponse()
        # 设置一点延时来避免在短时间发出大量的请求而遭到服务器拒绝。
        sleep(0.01)
        if res.code in (301, 302, 303, 307):
            redirect = res.getheader('location', None)
            self.source.redirect(redirect)
            # 关闭无用连接并创建重定向的新连接。
            res.close()
            if conn.sock:
                conn.sock.shutdown(socket.SHUT_RDWR)
            conn.close()
            conn = self._create_connection()

            return self._auto_redirect(conn)
        elif 400 <= res.code < 500:
            raise HTTP4XXError("code: %s, url: %s" % (res.code, self.source.url))
        elif 500 <= res.code < 600:
            raise HTTP5XXError("code: %s, url: %s" % (res.code, self.source.url))
        elif res.code not in (206, 200):
            raise UnknownError("code: %s, url: %s" % (res.code, self.source.url))

        return conn, res

    def _build_request_headers(self, request_range=None):
        """
        :param
            request_range   : 根据请求的范围构建请求头，若是None则是返回不指定范围信息的请求头。
        """
        headers = Headers(self.source.headers.items())
        scheme, netloc, path, params, query, fragment = list(self.source.urlparse)
        # 添加cookie
        if self.source.cookie:
            headers.add_header('Cookie', self.source.cookie)

        # 若不提供分片范围则不添加信息到请求头。
        if request_range is not None:
            query = (query + ''.join(
                [k + '=' + v for k, v in self.source.format_range.get_query(request_range).items()]
            )).lstrip('&')

            # 构建请求头
            for k, v in self.source.format_range.get_headers(request_range).items():
                headers.add_header(k, v)

        # 由于一些浏览器地址栏会直接把空格显示出来而不进行编码，所以这里单独对空格编码。
        uri = urlunparse((scheme, netloc, path, params, query, fragment)).replace(' ', '%20')

        return uri, headers

    def connect(self):
        """ 完全建立起客户端连接，以从服务器拉取数据。"""
        self._conn_res = self._auto_redirect(self._create_connection())

        return self._conn_res

    def retrieve(self):
        """ 从网络拉取数据。"""
        conn, res = self._conn_res
        # 如果在partial请求中得到了200返回代码，放弃徐汇，抛出异常以避免获取数据错误。
        if self.partial is True and res.code != 206:
            # FIX: 出现这种情况，可能的原因是重定向后的连接过期导致的，重置下载源通常可以解决问题。
            self.source.reset()
            raise NotAPartialResponse((conn, res))

        # :::::开始取回数据。
        # 频繁使用的实例变量通过使用局部变量减少不必要的寻址
        progress = self.progress
        queue = self._queue

        progress.start()
        # 客户端连接成功，并且报告响应结果给控制台。
        self.source.setresponse(self.source.url, res.getheaders(), res.getcode(), res.length)
        urlresp = self.getresponse()
        self._report(EVT_URL_STATUS, EVT_URL_NORMAL, context={'info': urlresp})

        buff = b''
        while True:
            # 检查待处理控制信号队列。
            if not queue.empty():
                eid, value = queue.get()

                if eid == EVT_TASK_SLICE:
                    # 处理动态分片请求。
                    fb_range = progress.slice(value)
                    self._report(EVT_TASK_SLICE, fb_range)
                elif eid == EVT_TASK_PAUSING:
                    break
                elif eid == EVT_CLIENT_WAIT:
                    sleep(value)
                elif eid == EVT_CLIENT_SWITCH:
                    self.source = value

            # 如果开启了限速器，那么将通过限制工作线程的方式进行限速。
            self._cons.acquire()

            # 计算分片的剩余下载字节数。
            prv_len = len(buff)
            remain = progress.length - progress.increment_go
            try:
                if remain >= 8192:
                    buff += res.read(8192)
                elif remain > 0:
                    buff += res.read(remain)
                else:
                    break
            except (socket.gaierror, urllib_URLError, urllib_HTTPError, socket.timeout, Exception) as e:
                self.report_error(e)
                break

            if len(buff) - prv_len == 0:
                # 如果未接收到数据，可能重试就可以解决问题，
                # 所以这里采取反馈控制台，让控制台做出决策。

                if res.chunked and not res.fp:
                    # 在不是分片请求中，由于chunked编码的原因下载完后强制修改进度progress。
                    progress.force_to_finish_go()

                self._report(EVT_CLIENT_RECV_EMPTY)
                break

            # 更新下载进度。
            progress.go(len(buff) - prv_len)

            if progress.increment_go >= progress.length:
                break
            elif len(buff) >= 1048576:  # 1 MB
                # 一级缓存计数缓冲，避免频繁的反馈给控制台。
                self._buffer(buff)
                del buff
                buff = b''

        # 在退出客户端前缓存起未保存的数据。
        self._buffer(buff)
        del buff
        progress.stop()

    def close(self):
        """ 关闭客户端。 """
        conn, res = self._conn_res
        self._conn_res = (None, None)
        if res:
            res.close()
        if conn:
            # 由于直接让连接关闭，会导致sock未完全关闭，所以这里先完全shutdown，再关闭连接。
            try:
                if conn.sock:
                    conn.sock.shutdown(socket.SHUT_RDWR)
                conn.close()
            except ConnectionResetError:
                # 忽略错误异常 ConnectionResetError: [WinError 10054]:
                #     An existing connection was forcibly closed by the remote host
                pass

    def run(self, cons):
        """ 下载客户端处理函数。 """
        self._cons = cons
        # 客户端开始前处理队列的控制信号。
        while not self._queue.empty():
            eid, value = self._queue.get()
            if eid == EVT_TASK_SLICE:
                fb_range = self.progress.slice(value)
                self._report(EVT_TASK_SLICE, fb_range)
            elif eid == EVT_CLIENT_SWITCH:
                self.source = value
            elif eid == EVT_TASK_PAUSING:
                break
            elif eid == EVT_CLIENT_WAIT:
                sleep(value)

        else:
            try:
                if None in self._conn_res:
                    self.connect()
                self.retrieve()

            except (socket.gaierror, socket.timeout, UnknownError,
                    HTTP4XXError, urllib_URLError, urllib_HTTPError, Exception) as e:
                self.report_error(e)

        self.close()
        self._cons = None

    def report_error(self, exception):
        """ 客户端异常错误处理报告。 """
        if type(exception) in (socket.timeout, urllib_URLError, urllib_HTTPError):
            # 连接超时
            exception_type = EVT_URL_TIMEOUT
        elif type(exception) in (HTTP4XXError, HTTP5XXError, NotAPartialResponse):
            # 无法处理的连接错误
            exception_type = EVT_URL_UNAVAILABLE
        elif type(exception) is socket.gaierror:
            # 网络异常错误
            exception_type = EVT_URL_GAIERROR
        else:
            # 未知连接错误
            exception_type = EVT_URL_UNKNOWN

        if exception_type == EVT_URL_TIMEOUT:
            # FIX: 修复在高连接数的情况下会出现超时，可能是因为连接失效，
            #      所以这里重置下载源，由源地址服务器再重定向新的地址。
            self.source.reset()
        self._report(EVT_URL_STATUS, exception_type, context={'info': exception})

    def _buffer(self, data):
        """ 缓存下载数据，并反馈给控制台。 """
        if data:
            self._report(EVT_BUFFER_COUNT, data)

    @staticmethod
    def dlopen(source, progress=None, partial=True, **options):
        """ 用于打开下载源收集文件信息。 """
        from ..struct.progress import Progress

        if not progress:
            progress = Progress((0,))
        cli = HTTPClient(source, progress, partial, **options)
        try:
            conn, res = cli.connect()
        except (socket.gaierror, socket.timeout, UnknownError,
                HTTP4XXError, urllib_URLError, urllib_HTTPError, Exception) as err:
            raise RequestError(err)

        size = res.length
        name = None
        # 响应头提供的name
        if res.getheader('content-disposition', None):
            name = re_search(r'filename="?(.*)"?', res.getheader('content-disposition', None))
            if name:
                name = name.group(1)
        # 链接path提供的文件名
        if not name:
            name = source.path.split('/')[-1]
        # 默认未命名unnamed-时间戳
        if not name:
            name = 'unnamed-%s' % time_ns()
        cli.partial = not res.chunked

        return cli, name, size, cli.partial

    def __repr__(self):
        return '<HTTPClient ({})[{}-{}]> {:.2%}'.format(self.source.id, self.progress.begin, self.progress.end,
                                                        self.progress.percent / 100)
