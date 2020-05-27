

from wsgiref.headers import Headers
from urllib.parse import urlunparse
from .abstract import AbstractClient
from ..utils import update_range_field
import logging

log = logging.getLogger(__name__)


class BaseHTTPClient(AbstractClient):
    NAME = 'base_http'
    PROTOCOL_SUPPORT = ('http', 'https')
    ASYNC_EXECUTE = None
    TIMEOUT = 10

    def _build_uri_headers(self):
        source_uri = self.source_uri
        pg = self.progress
        uri = source_uri.uri
        headers = Headers(source_uri.headers.items())

        if self.resume_capability is not False:
            range_field = source_uri.range_field
            if range_field is None:
                range_field = {
                    'Range': 'bytes={begin}-{end_with}'
                }

            scheme, netloc, path, params, query, fragment = list(source_uri.urlparse)
            req_range = (pg.begin + pg.walk_length, pg.end)
            query = (query + ''.join(
                [f'{k}={update_range_field(v, req_range)}'
                 for k, v in range_field.items() if k.startswith('&')]
            )).lstrip('&')

            for k, v in range_field.items():
                if not k.startswith('&'):
                    headers.add_header(k, update_range_field(v, req_range))

            # 由于一些浏览器地址栏会直接把空格显示出来而不进行编码，所以这里单独对空格编码。
            uri = urlunparse((scheme, netloc, path, params, query, fragment)).replace(' ', '%20')

        return uri, headers

    def close(self):
        session = self.session
        resp = self.resp
        self.session = None
        self.resp = None
        if resp:
            resp.close()

    async def pause(self):
        self._closed = True

    def validate_token(self, current_resp):
        resp = self.resp
        if resp is None:
            raise ValueError('cannot validate on a unconnected client.')

        source_resp = self.source_uri.getresponse()

        # TODO: 在多下载源的情况下对下载源之间经过资源数据采样校验，通过后作为响应基准
        if source_resp is None:
            raise ValueError('下载源没有经过校验的资源响应基准。')

        validate_name = ['length', 'etag', 'content_md5', 'content_type', 'last_modified']

        if not all([getattr(current_resp, name) == getattr(source_resp, name)
                    for name in validate_name]):
            log.warning([f'{name}: ({getattr(current_resp, name)}) ?= ({getattr(source_resp, name)})'
                         for name in validate_name])
            raise ValueError('connection resource token not match.')
        return True


def content_range_fullsize(content_range):
    """ 从HTTP响应头中的Content-Range中获取文件总长。"""
    if content_range is None:
        return None
    return int(content_range.rsplit('/', 1)[-1])


def content_type_mimetype(content_type_header):
    """ 从HTTP响应头中的Content-Type中获取文件mimetype类型。"""
    if content_type_header is None:
        return None
    return content_type_header.split(';', 1)[0] or None
