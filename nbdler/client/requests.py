

import requests
from nbdler.uri import URIResponse
from traceback import format_exc
from .base_http import BaseHTTPClient, content_range_fullsize, content_type_mimetype
from nbdler.handler import h
import logging
import nbdler
from requests.utils import get_environ_proxies

log = logging.getLogger(__name__)


class HTTPClient(BaseHTTPClient):
    TIMEOUT = 10

    def connect(self):
        session = self.session
        source_uri = self.source_uri
        proxies = source_uri.proxies or {}
        if not proxies.get(source_uri.scheme):
            if source_uri.kwargs.get('trust_env', False):
                # Set environment's proxies.
                no_proxy = proxies.get('no_proxy') if proxies is not None else None
                env_proxies = get_environ_proxies(source_uri.uri, no_proxy=no_proxy)
                for (k, v) in env_proxies.items():
                    proxies.setdefault(k, v)

        cookies = source_uri.cookies
        verify = source_uri.kwargs.get('verify', True)
        uri, headers = self._build_uri_headers()
        timeout = self.kwargs.get('timeout', None) or HTTPClient.TIMEOUT
        try:
            resp = requests.get(
                source_uri.uri,
                headers=headers,
                proxies=proxies,
                cookies=cookies,
                timeout=timeout,
                stream=True,
                verify=verify
            )
        except requests.exceptions.Timeout as error:
            raise nbdler.error.TimeoutError(f"{uri}") from error
        except BaseException as error:
            log.debug(f'{error}', format_exc())
            raise nbdler.error.FatalError() from error
        else:
            total_length = content_range_fullsize(resp.headers.get('content-range'))
            response = URIResponse(str(resp.url), list(resp.headers.items()), resp.status_code, resp.reason,
                                   total_length, content_type_mimetype(resp.headers.get('content-type')),
                                   self.progress.range, resp.status_code == 206)

        if self.resume_capability is None:
            if resp.status_code not in (206, 200):
                raise nbdler.error.FatalError(f"[{resp.status_code} {resp.reason}] '{resp.url}'")
            self.resume_capability = resp.status_code == 206

        elif self.resume_capability is True:
            if not resp.status_code == 206:
                raise nbdler.error.FatalError(f"[{resp.status_code} {resp.reason}] '{resp.url}'")

        self.session = session
        self.resp = resp
        return response

    def fetch(self):
        session, resp = self.session, self.resp
        pg = self.progress

        speed_adjuster = h.speed_adjuster
        slicer = h.slicer
        uri_mgr = h.uri_mgr
        file_data = h.file_data
        receive_data = resp.raw.read

        pg.start()

        uri_mgr.success(resp)

        data = b''
        while True:
            if self._closed:
                break

            speed_adjuster.acquire_threadsafe()
            slicer.response_threadsafe()

            previous_len = len(data)
            remain_len = pg.total_length - pg.walk_length
            try:
                if remain_len >= 8192:
                    data += receive_data(8192)
                elif remain_len > 0:
                    data += receive_data(remain_len)
                else:
                    break
            except requests.exceptions.Timeout as err:
                uri_mgr.timeout(err)
                break
            except BaseException as err:
                uri_mgr.fatal(err)
                break

            walk_len = len(data) - previous_len
            if not walk_len:

                if resp.headers.get('content-length') is None:
                    pg.set_walk_finish()
                break

            pg.walk(walk_len)

            if pg.walk_length >= pg.total_length:
                break
            elif len(data) >= 65536:  # 64 KB
                file_data.store_threadsafe(data)
                data = b''
        if data:
            file_data.store_threadsafe(data)

        pg.stop()

    def run(self):
        h.slicer.response_threadsafe()
        try:
            resp = self.connect()
        except nbdler.error.UriError as err:
            h.uri_mgr.fatal(err)
            raise
        else:
            h.uri_mgr.success(resp)

            self.validate_token(resp)
            if not self._closed:
                self.fetch()

    @classmethod
    async def dlopen(cls, source, progress, **kwargs):
        with cls(None, source, progress, None, **kwargs) as cli:
            resp = cli.connect()
            return resp


def session_without_trust_env():
    session = requests.Session()
    # 默认创建不使用环境中的代理的会话，如要使用设置下载源的trust_env参数。
    session.trust_env = False
    return session


NAME = 'requests'
PROTOCOL_SUPPORT = ('http', 'https')
ASYNC_EXECUTE = False

ClientHandler = HTTPClient
ClientSession = session_without_trust_env

