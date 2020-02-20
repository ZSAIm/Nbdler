# -*- coding: UTF-8 -*-

from ..url.source import SourceUrl, UrlResponse
from ...error import URLCriticalError, URLTimeoutError, URLUnknownError, NetworkBrokenError, MaxUsedExceededError
from ...utils.misc import Component
from copy import copy


class SourceWrapper(Component):
    """ 下载源原件。 """
    _MAX_UNAVAILABLE = 10
    _MAX_TIMEOUT = 20
    _MAX_UNKNOWN = 20
    _MAX_NETWORK_BROKEN = 10

    def __init__(self, sid, source, max_used):
        self._used = 0
        self.__id = sid
        self._MAX_USED = max_used
        self._unavailable = 0
        self._timeout = 0
        self._unknown = 0
        self._network_broken = 0
        self.__source = source
        self._response = None

    def __contains__(self, item):
        return self.__id == item.id

    @property
    def response(self):
        return self._response

    @property
    def id(self):
        return self.__id

    @property
    def used(self):
        return self._used

    def use_anyway(self):
        """ 客户端强制使用该下载源。 """
        self._used += 1

    def use(self):
        """ 客户端在规范下使用该下载源。 """
        self._used += 1
        if self._MAX_USED is not None and self._MAX_USED < self._used:
            self._used -= 1
            raise MaxUsedExceededError()

    def disuse(self):
        """ 客户端取消使用该下载源。 """
        self._used -= 1

    def unavailable(self):
        """ 下载源不可用错误。 """
        self._unavailable += 1
        if self._MAX_UNAVAILABLE is not None and self._unavailable > self._MAX_UNAVAILABLE:
            raise URLCriticalError()

    def timeout(self):
        """ 下载源超时错误。 """
        self._timeout += 1
        if self._MAX_TIMEOUT is not None and self._timeout > self._MAX_TIMEOUT:
            raise URLTimeoutError()

    def unknown(self):
        """ 客户端未知网络错误。 """
        self._unknown += 1
        if self._MAX_UNKNOWN is not None and self._unknown > self._MAX_UNKNOWN:
            raise URLUnknownError()

    def network_broken(self):
        """ 网络断开无法连接。 """
        self._network_broken += 1
        if self._MAX_NETWORK_BROKEN is not None and self._network_broken > self._MAX_NETWORK_BROKEN:
            raise NetworkBrokenError()

    def success(self):
        """ 客户端连接成功。 """
        self._network_broken = 0
        self._unavailable = 0
        self._timeout = 0
        self._unknown = 0

    def get(self):
        """ 生成下载源副本。 并且重置下载源副本的响应信息。 """
        src = copy(self.__source)
        src.reset()
        return src

    def is_available(self):
        """ 返回下载源是否有效的。
        有效的判定是错误次数在有效之内，若客户端成功连接后将清除所有的错误计数。
        """
        try:
            if self._MAX_UNAVAILABLE is not None and self._unavailable > self._MAX_UNAVAILABLE:
                raise URLCriticalError('unavailable(%d) >= _MAX_UNAVAILABLE(%d)' % (
                    self._unavailable, self._MAX_UNAVAILABLE))
            if self._MAX_NETWORK_BROKEN is not None and self._network_broken > self._MAX_NETWORK_BROKEN:
                raise NetworkBrokenError('network_broken(%d) >= _MAX_NETWORK_BROKEN(%d)' % (
                    self._network_broken, self._MAX_NETWORK_BROKEN))
            if self._MAX_TIMEOUT is not None and self._timeout > self._MAX_TIMEOUT:
                raise URLTimeoutError('timeout(%d) >= _MAX_TIMEOUT(%d)' % (
                    self._timeout, self._MAX_TIMEOUT))
            if self._MAX_UNKNOWN is not None and self._unknown > self._MAX_UNKNOWN:
                raise URLUnknownError('unknown(%d) >= _MAX_UNKNOWN(%d)' % (
                    self._unknown, self._MAX_UNKNOWN))
            if self._MAX_USED is not None and self._MAX_USED <= self._used:
                raise MaxUsedExceededError('max_used(%d) >= MAX_USED(%d)' % (
                    self._MAX_USED, self._MAX_USED))
        except (NetworkBrokenError, URLCriticalError, URLTimeoutError, URLUnknownError, MaxUsedExceededError):
            return False

        return True

    def is_max_used(self):
        """ 返回下载源是否达到最大的使用限制。 """
        if self._MAX_USED is not None and self._MAX_USED <= self._used:
            return True
        return False

    def setresponse(self, url, headers, code, length):
        """ 设置下载源的响应。
        为了更好的评估一个下载源的状态，这里作为下载源的全局进行设置响应，
        是用于第一次成功建立客户端后返回的响应信息。
        """
        self._response = UrlResponse(url=url, headers=headers, code=code, length=length)
        self.__source._response = self._response

    def __snapshot__(self):
        source = self.__source.__snapshot__()
        response = self.response and self.response.__snapshot__()
        return {
            'source': source,
            'response': response,

            'used': self._used,
            'unavailable': self._unavailable,
            'timeout': self._timeout,
            'unknown': self._unknown,
            'network_broken': self._network_broken
        }

    def reset(self):
        """ 重置所有的计数。 """
        self._used = 0
        self._network_broken = 0
        self._unavailable = 0
        self._timeout = 0
        self._unknown = 0

    def __repr__(self):
        return '<SourceWrapper %s - [%d, %d, %d, %d, %d]>' % (
            self.__id, self._used, self._unavailable, self._timeout, self._unknown, self._network_broken)


class UrlManager(Component):
    """ 下载源管理器。 """
    def __init__(self):
        self._sources = []

    def put(self, url, headers=None, cookie=None,
            proxies=None, max_conn=None, format_range=None, name=None):
        """ 添加新的下载源。 """
        put_id = self.__newid()
        if name is None:
            name = str(put_id)
        src_url = SourceUrl(put_id, url, headers, cookie, proxies, max_conn, format_range, name)

        # 为了更好的管理记录，使用一个封装对象来处理下载源。
        wrapper = SourceWrapper(put_id, src_url, max_conn)
        self._sources[put_id] = wrapper
        return self._sources[put_id]

    def get(self, k, default=None):
        """ 通过ID号或者通过下载源名称获取下载源副本。 """
        if type(k) is int:
            try:
                return self._sources[k]
            except ValueError:
                pass
        elif type(k) is str:
            for i in self._sources:
                if i.cont.name == k:
                    return i

        return default

    def get_all(self):
        """ 返回全部的下载源"""
        return self._sources

    def __newid(self):
        """ 内部用于生成新ID号的函数。 """
        try:
            index = self._sources.index(None)
        except ValueError:
            index = len(self._sources)
            self._sources.append(None)
        return index

    def find_min_avl_used(self):
        """ 搜索最少使用并且有效的下载源。 """
        min_max_used = sorted(self._sources, key=lambda i: i.used)
        for i in min_max_used:
            if i.is_available():
                return i
        return None

    def find_min_used(self):
        """ 搜索最少使用的下载源。 """
        min_max_used = sorted(self._sources, key=lambda i: i.used)
        return min_max_used[0]

    def get_next(self, sid):
        """ 获取下一个ID下载源。 """
        try:
            return self._sources[sid + 1]
        except IndexError:
            return self._sources[0]

    def open_request(self, request):
        """ 打开一个请求下载对象的下载源。 """
        for v in request:
            self.put(url=v.url, headers=v.headers, cookie=v.cookie,
                     proxies=v.proxies, max_conn=v.max_conn,
                     format_range=v.format_range, name=v.name)

    def is_all_critical(self):
        """ 返回是否所有的下载源已失效。 """
        for i in self._sources:
            if i.is_available():
                return False

        return True

    def __iter__(self):
        return iter(self._sources)

    def __snapshot__(self):
        sources = [src.__snapshot__() for src in self._sources]
        return {
            'sources': sources
        }

    @staticmethod
    def load(snapshot):
        """ 从快照字典加载对象。"""
        url = UrlManager()
        for info in snapshot['sources']:
            source = info['source']
            wrap = url.put(source['url'], source['headers'], source['cookie'], source['proxies'],
                           source['max_conn'], source['format_range'], source['name'])
            response = info['response']
            wrap.setresponse(response['url'], response['headers'], response['code'], response['length'])
        return url
