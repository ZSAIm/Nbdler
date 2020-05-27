from wsgiref.headers import Headers
from urllib.parse import urlparse
from base64 import b64decode
from typing import AnyStr, Sequence


class BaseURI:
    def __init__(self, uri: AnyStr, headers):
        self._uri = None
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
        self.uri = uri

    @property
    def uri(self):
        return self._uri

    @uri.setter
    def uri(self, value):
        self._uri = value
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


class SourceURI(BaseURI):
    def __init__(self, id, uri, headers, cookies=None, proxies=None,
                 max_conn=None, range_field=None, name=None, response=None, **kwargs):
        super(SourceURI, self).__init__(uri, headers)
        self.id = id
        self.cookies = cookies
        self.proxies = proxies
        self.max_conn = max_conn

        self.range_field = range_field

        self.name = name
        self._response = URIResponse.loads(response) if response else None
        self.kwargs = kwargs

    def getresponse(self):
        return self._response

    def set_response(self, resp):
        self._response = resp

    def dumps(self):
        kwargs = {
            'id': self.id,
            'uri': self.uri,
            'headers': self.headers.items(),
            'cookies': self.cookies,
            'proxies': self.proxies,
            'max_conn': self.max_conn,
            'range_field': self.range_field,
            'name': self.name,
            'response': self._response and self._response.dumps()
        }
        kwargs.update(self.kwargs)
        return kwargs

    @classmethod
    def loads(cls, dumpy):
        return cls(**dumpy)

    def __repr__(self):
        return f'<SourceURI id={self.id} name={self.name} uri="{self._uri}">'


class URIResponse(BaseURI):
    def __init__(self, uri,
                 headers,
                 code,
                 msg,
                 length,
                 content_type,
                 range,
                 resume_capability,
                 **kwargs):
        """
        Args:
            uri: 响应URI
            headers: 响应头
            code: 响应代码
            msg: 响应消息
            length: 资源总长
            content_type: 资源类型
            range: 资源范围
            resume_capability: 是否支持断点续传
            **kwargs: 额外参数
        """
        super().__init__(uri, headers)
        self.code = code
        self.length = length
        self.range = range
        self.msg = msg
        self.content_type = content_type
        self.resume_capability = resume_capability
        self.kwargs = kwargs

        # extract HTTP headers
        self.etag = self.headers.get('etag')
        self.date = self.headers.get('date')
        self.last_modified = self.headers.get('last-modified')
        self.content_range = self.headers.get('content-range')
        self.content_md5 = self.headers.get('content-md5')
        self.expires = self.headers.get('expires')
        self.md5 = None
        if self.content_md5:
            # RFC1864
            try:
                self.md5 = b64decode(self.content_md5).hex()
            except:
                pass

    def dumps(self):
        kwargs = {
            'uri': self.uri,
            'headers': list(self.headers.items()),
            'code': self.code,
            'length': self.length,
            'range': self.range,
            'content_type': self.content_type,
            'msg': self.msg,
            'resume_capability': self.resume_capability
        }
        kwargs.update(self.kwargs)
        return kwargs

    @classmethod
    def loads(cls, dumpy):
        return cls(**dumpy)

    def __repr__(self):
        return (f"<UriResponse [{self.code} {self.msg}]'{self.uri}' "
                f"range={self.range}, resume_capability={self.resume_capability}>")


class URIs:
    """ 下载源管理器。 """
    def __init__(self):
        self._uris = []

    def __len__(self):
        return len(self._uris)

    def __getitem__(self, item):
        return self._uris.__getitem__(item)

    def __iter__(self):
        return iter(self._uris)

    def put(self, uri,
            headers=None,
            cookies=None,
            proxies=None,
            max_conn=None,
            range_field=None,
            name=None,
            **kwargs):
        """ 添加新的下载源。 """
        put_id = self.__newid()
        if name is None:
            name = str(put_id)
        src_url = SourceURI(put_id, uri, headers, cookies, proxies, max_conn, range_field, name, **kwargs)

        self._uris[put_id] = src_url
        return self._uris[put_id]

    def __newid(self):
        """ 内部用于生成新ID号的函数。 """
        try:
            index = self._uris.index(None)
        except ValueError:
            index = len(self._uris)
            self._uris.append(None)
        return index

    def dumps(self):
        return [uri.dumps() for uri in self._uris]

    @classmethod
    def loads(cls, dumpy):
        uris = cls()
        for uri in dumpy:
            uris._uris.append(SourceURI(**uri))
        return uris

    @classmethod
    def load_from_source_uris(cls, source_uris: Sequence[SourceURI]):
        uris = cls()
        uris.import_uris(source_uris)
        return uris

    def import_uris(self, source_uris: Sequence[SourceURI]):
        for uri in source_uris:
            self.put(uri.uri, uri.headers.items(), uri.cookies, uri.proxies, uri.max_conn,
                     uri.range_field, uri.name, **uri.kwargs)

    def __repr__(self):
        return f'<URIs {self._uris}>'
