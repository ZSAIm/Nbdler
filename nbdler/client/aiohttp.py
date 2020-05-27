

import aiohttp
import asyncio
from urllib.parse import urlunparse, urlparse
from nbdler.uri import URIResponse
from .base_http import BaseHTTPClient, content_range_fullsize, content_type_mimetype
from traceback import format_exc
from nbdler.handler import h
import logging
import nbdler

log = logging.getLogger(__name__)


class AIOHTTPClient(BaseHTTPClient):
    TIMEOUT = 10

    async def connect(self):
        session = self.session
        source_uri = self.source_uri
        proxies = source_uri.proxies or {}
        proxy = None
        if not proxies.get(source_uri.scheme):
            if source_uri.kwargs.get('trust_env', False):
                for scheme, proxy_info in aiohttp.helpers.proxies_from_env().items():
                    if scheme == source_uri.scheme:
                        proxy = str(proxy_info.proxy)
                        proxy_auth = proxy_info.proxy_auth
                        if proxy_auth is not None:
                            # 将代理验证添加入代理链接
                            username = proxy_auth.login
                            password = proxy_auth.password
                            proxy_parse = urlparse(str(proxies))
                            scheme, netloc, path, params, query, fragment = list(proxy_parse)
                            netloc = f'{username}:{password}@{netloc}'
                            proxy = urlunparse([scheme, netloc, path, params, query, fragment])
                        break

        cookies = source_uri.cookies
        uri, headers = self._build_uri_headers()

        timeout = self.kwargs.get('timeout', None) or AIOHTTPClient.TIMEOUT
        timeout = aiohttp.ClientTimeout(sock_connect=timeout, sock_read=timeout)

        try:
            resp = await session.get(
                uri,
                headers=headers,
                cookies=cookies,
                proxy=proxy,
                timeout=timeout,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            raise nbdler.error.TimeoutError(f"{uri}") from error
        except BaseException as error:
            log.debug(f'{error}', format_exc())
            raise nbdler.error.FatalError() from error
        else:
            total_length = content_range_fullsize(resp.headers.get('content-range'))
            response = URIResponse(str(resp.url), list(resp.headers.items()), resp.status, resp.reason,
                                   total_length, content_type_mimetype(resp.headers.get('content-type')),
                                   self.progress.range, resp.status == 206)

        if self.resume_capability is None:
            if resp.status not in (206, 200):
                raise nbdler.error.FatalError(f"[{resp.status} {resp.reason}] '{resp.url}'")
            self.resume_capability = resp.status == 206

        elif self.resume_capability is True:
            if not resp.status == 206:
                raise nbdler.error.FatalError(f"[{resp.status} {resp.reason}] '{resp.url}'")

        self.session = session
        self.resp = resp
        return response

    async def fetch(self):
        session, resp = self.session, self.resp
        pg = self.progress

        speed_adjuster = h.speed_adjuster
        slicer = h.slicer
        uri_mgr = h.uri_mgr
        file_data = h.file_data

        pg.start()

        uri_mgr.success(resp)

        receive_data = resp.content.read
        data = b''
        while True:
            if self._closed:
                break

            await speed_adjuster.acquire()
            await slicer.response()

            previous_len = len(data)
            remain_len = pg.total_length - pg.walk_length
            try:
                if remain_len >= 8192:
                    data += await receive_data(8192)
                elif remain_len > 0:
                    data += await receive_data(remain_len)
                else:
                    break
            except asyncio.TimeoutError as err:
                uri_mgr.timeout(err)
                break
            except BaseException as err:
                uri_mgr.fatal(err)
                break

            walk_len = len(data) - previous_len
            if not walk_len:
                if resp.content_length is None:
                    pg.set_walk_finish()
                break

            pg.walk(walk_len)

            if pg.walk_length >= pg.total_length:
                break
            elif len(data) >= 65536:  # 64 KB
                await file_data.store(data)
                data = b''
        if data:
            await file_data.store(data)

        pg.stop()

    async def run(self):
        if self.resp:
            self.close()

        await h.slicer.response()
        try:
            resp = await self.connect()
        except nbdler.error.UriError as err:
            h.uri_mgr.fatal(err)
            raise
        else:
            h.uri_mgr.success(resp)

            # self.validate_token(resp)
            if not self._closed:
                await self.fetch()

    def close(self):
        session = self.session
        resp = self.resp
        self.session = None
        self.resp = None
        if resp:
            resp.release()
            resp.close()

    @classmethod
    async def dlopen(cls, source, progress, **kwargs):
        async with ClientSession() as session:
            async with cls(session, source, progress, None, **kwargs) as cli:
                resp = await cli.connect()
                size = resp.length
                progress._range = (0, size)

        return resp


NAME = 'aiohttp'
PROTOCOL_SUPPORT = ('http', 'https')
ASYNC_EXECUTE = True

ClientHandler = AIOHTTPClient


class ClientSession(aiohttp.ClientSession):
    async def close(self) -> None:
        await super().close()

        # doc: https://docs.aiohttp.org/en/latest/client_advanced.html#graceful-shutdown
        # 会话关闭强制等待避免异常
        await asyncio.sleep(0.25)

