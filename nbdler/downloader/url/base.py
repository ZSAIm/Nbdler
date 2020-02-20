# -*- coding: UTF-8 -*-

from wsgiref.headers import Headers
from urllib.parse import urlparse


class BaseUrl:
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
    def urlparse(self):
        return self._urlparse

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

    protocol = scheme

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


