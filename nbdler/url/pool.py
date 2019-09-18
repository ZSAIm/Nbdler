
from nbdler.url.source import SourceUrl
from nbdler.exception import URLCrash, URLTimeout, URLUnknownError, NetworkDisconnected, MaxUsedExceedError
from nbdler.struct.dump import UrlDumpedData, SourceUrlDumpedData
from copy import copy

DEFAULT_CRASH_THRESHOLD = 10
DEFAULT_TIMEOUT_THRESHOLE = 50
DEFAULT_UNKNOWN_THRESHOLD = 150
DEFAULT_NETWORKDOWN_THRESHOLD = 10


class SourceWrapper:
    __slots__ = ('source', 'used', '_crash', '_timeout', '_unknown', '_network_down', '_max_used')

    def __init__(self, source, max_used):
        self.used = 0
        self._max_used = max_used
        self._crash = 0
        self._timeout = 0
        self._unknown = 0
        self._network_down = 0
        self.source = source

    def __contains__(self, item):
        return self.source.id == item.id

    def use_anyway(self):
        self.used += 1

    def use(self):
        self.used += 1
        if self._max_used is not None and self._max_used < self.used:
            self.used -= 1
            raise MaxUsedExceedError()

    def disuse(self):
        self.used -= 1

    def crash(self):
        self._crash += 1
        if DEFAULT_CRASH_THRESHOLD is not None and self._crash > DEFAULT_CRASH_THRESHOLD:
            raise URLCrash()

    def timeout(self):
        self._timeout += 1
        if DEFAULT_TIMEOUT_THRESHOLE is not None and self._timeout > DEFAULT_TIMEOUT_THRESHOLE:
            raise URLTimeout()

    def unknown(self):
        self._unknown += 1
        if DEFAULT_UNKNOWN_THRESHOLD is not None and self._unknown > DEFAULT_UNKNOWN_THRESHOLD:
            raise URLUnknownError()

    def network_down(self):
        self._network_down += 1
        if DEFAULT_NETWORKDOWN_THRESHOLD is not None and self._network_down > DEFAULT_NETWORKDOWN_THRESHOLD:
            raise NetworkDisconnected()

    def clear_counter(self):
        self._network_down = 0
        self._crash = 0
        self._timeout = 0
        self._unknown = 0

    def get(self):
        src = copy(self.source)
        src.reset()
        return src

    def is_available(self):
        try:
            if DEFAULT_CRASH_THRESHOLD is not None and self._crash > DEFAULT_CRASH_THRESHOLD:
                raise URLCrash()
            if DEFAULT_NETWORKDOWN_THRESHOLD is not None and self._network_down > DEFAULT_NETWORKDOWN_THRESHOLD:
                raise NetworkDisconnected()
            if DEFAULT_TIMEOUT_THRESHOLE is not None and self._timeout > DEFAULT_TIMEOUT_THRESHOLE:
                raise URLTimeout()
            if DEFAULT_UNKNOWN_THRESHOLD is not None and self._unknown > DEFAULT_UNKNOWN_THRESHOLD:
                raise URLUnknownError()
            if self._max_used is not None and self._max_used <= self.used:
                raise MaxUsedExceedError()
        except (NetworkDisconnected, URLCrash, URLTimeout, URLUnknownError, MaxUsedExceedError):
            return False

        return True

    def is_max_used(self):
        if self._max_used is not None and self._max_used <= self.used:
            return True
        return False


class Url:
    def __init__(self):
        self._sources = []

    def put(self, url, headers=None, cookie=None, *,
            proxy=None, max_conn=None, rangef=None, name=None):
        putid = self._newid()
        if name is None:
            name = str(putid)
        srcurl = SourceUrl(putid, url, headers, cookie, proxy, max_conn, rangef, name)
        self._sources[putid] = SourceWrapper(srcurl, max_conn)
        return srcurl

    def get(self, k, default=None):
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
        return tuple(self._sources)

    def _newid(self):
        try:
            index = self._sources.index(None)
        except ValueError:
            index = len(self._sources)
            self._sources.append(None)
        return index

    def get_min_avl_used(self):
        min_max_used = sorted(self._sources, key=lambda i: i.used)
        for i in min_max_used:
            if i.is_available():
                return i
        return None

    def get_min_used(self):
        min_max_used = sorted(self._sources, key=lambda i: i.used)
        return min_max_used[0]

    def get_next(self, srcid):
        try:
            return self._sources[srcid + 1]
        except IndexError:
            return self._sources[0]

    def open_request(self, dlrequest):
        for v in dlrequest:
            self.put(url=v.url, headers=v.headers, cookie=v.cookie,
                     proxy=v.proxy, max_conn=v.max_conn,
                     rangef=v.rangef, name=v.name)

    def is_all_crashed(self):
        for i in self._sources:
            if i.is_available():
                return False

        return True

    def getwrapper(self, source, default=None):
        for i in self._sources:
            if source in i:
                return i
        return default

    def clear_counter(self):
        for i in self._sources:
            i.clear_counter()

    def dump_data(self):
        urls_data = []
        for wrapper in self._sources:
            urls_data.append(tuple(wrapper.source.dump_data()))
        return UrlDumpedData(sources=urls_data)

    def load(self, dumped_data):
        data = UrlDumpedData(*dumped_data)
        for source_data in data.sources:
            srcdata = SourceUrlDumpedData(*source_data)
            source = self.put(srcdata.url, srcdata.headers, srcdata.cookie,
                              proxy=srcdata.proxy, max_conn=srcdata.max_conn,
                              rangef=srcdata.rangef, name=srcdata.name)
            if srcdata.response:
                source.load(srcdata.response)

