from collections import namedtuple
from wsgiref.headers import Headers
from six.moves.urllib.parse import urlparse

UrlInfo = namedtuple('UrlInfo', 'url headers cookie proxy max_conn rangef name response')
UrlInfo.__new__.__defaults__ = (None,)


class BasicUrl:
    def __init__(self, url, headers):
        self._url = None
        self._urlparse = None

        if headers is None:
            headers = Headers([])
        elif isinstance(headers, dict):
            headers = Headers(list(headers.items()))
        elif isinstance(headers, list):
            headers = Headers(headers)
        else:
            raise TypeError()
        self.headers = headers
        self.url = url

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        self._url = value
        self._urlparse = urlparse(value)

    @property
    def hostname(self):
        if not self._urlparse:
            return None
        return self._urlparse.hostname

    @property
    def port(self):
        if not self._urlparse:
            return None
        return self._urlparse.port

    @property
    def path(self):
        if not self._urlparse:
            return None
        return self._urlparse.path

    @property
    def scheme(self):
        if not self._urlparse:
            return None
        return self._urlparse.scheme

    @property
    def query(self):
        if not self._urlparse:
            return None
        return self._urlparse.query

    @property
    def netloc(self):
        if not self._urlparse:
            return None
        return self._urlparse.netloc


