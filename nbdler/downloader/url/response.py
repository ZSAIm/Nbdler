# -*- coding: UTF-8 -*-
from ...utils.misc import Component
from .base import BaseUrl
from base64 import b64decode


class UrlResponse(Component, BaseUrl):
    def __init__(self, url, headers, code, length):
        super(UrlResponse, self).__init__(url, headers)
        self.code = code
        self.length = length

        # extract HTTP headers
        self.etag = self.headers.get('etag')
        self.content_type = self.headers.get('content-type')
        self.date = self.headers.get('date')
        self.last_modified = self.headers.get('last-modified')
        self.content_range = self.headers.get('content-range')
        self.content_md5 = self.headers.get('content-md5')

        self.md5 = None
        if self.content_md5:
            # RFC1864
            self.md5 = b64decode(self.content_md5).hex()

    def getheaders(self):
        return self.headers

    def __snapshot__(self):
        return {
            'url': self.url,
            'headers': list(self.headers.items()),
            'code': self.code,
            'length': self.length
        }

    def __iter__(self):
        return iter((self.url, self.headers.items(), self.code, self.length))

