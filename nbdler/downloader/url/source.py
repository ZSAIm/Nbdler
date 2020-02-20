# -*- coding: UTF-8 -*-

from .base import BaseUrl
from ..struct.misc import FormatRange
from ...utils.misc import Component
from .response import UrlResponse


class SourceUrl(Component, BaseUrl):
    def __init__(self, id, url, headers=None, cookie=None, proxies=None, max_conn=None, format_range=None, name=None):
        self.id = id
        self.__origin_url = url
        super(SourceUrl, self).__init__(url, headers)
        self.cookie = cookie
        self.proxies = proxies
        self.max_conn = max_conn

        if format_range is None:
            format_range = FormatRange({'Range': 'bytes={begin}-{end_with}'})
        elif type(format_range) is dict:
            format_range = FormatRange(format_range)
        elif type(format_range) is FormatRange:
            pass
        else:
            raise TypeError()

        self.format_range = format_range
        self.name = name
        self._response = None

    @property
    def response(self):
        return self._response

    def get_origin_url(self):
        return self.__origin_url

    def redirect(self, location):
        self.url = location
        return self

    def reset(self):
        self.url = self.__origin_url
        self._response = None

    def setresponse(self, url, headers, code, length):
        self._response = UrlResponse(url, dict(headers), code, length)

    def __snapshot__(self):
        return {
            'url': self.url,
            'headers': list(self.headers.items()),
            'cookie': self.cookie,
            'proxies': self.proxies,
            'max_conn': self.max_conn,
            'format_range': dict(self.format_range),
            'name': self.name
        }





