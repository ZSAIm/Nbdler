

from nbdler.url.basic import BasicUrl, UrlInfo
from nbdler.url.response import UrlResponse
from wsgiref.headers import Headers
from nbdler.struct.misc import RangeFormat
from nbdler.struct.dump import SourceUrlDumpedData, UrlResponseDumpedData


class SourceUrl(BasicUrl):
    def __init__(self, id, url, headers=None, cookie=None,
                 proxy=None, max_conn=None, rangef=None, name=None):

        self.__origin_url = url
        self.id = id
        super(SourceUrl, self).__init__(url, headers)
        self.cookie = cookie
        self.proxy = proxy
        self.max_conn = max_conn

        if rangef is None:
            rangef = RangeFormat({'Range': 'bytes={begin}-{end_with}'})
        elif type(rangef) is dict:
            rangef = RangeFormat(rangef)
        elif type(rangef) is RangeFormat:
            pass
        else:
            raise TypeError()

        self._rangef = rangef
        self.name = name
        self._response = None

    def http_request_header(self, range):
        scheme, netloc, path, params, query, fragment = list(self._urlparse)

        query = query + ''.join([i + '=' + j for i, j in self._rangef.getquery(range).items()])
        query = query.lstrip('&')
        if query:
            path = path + '?' + query
        headers = Headers(self.headers.items())
        for i, j in self._rangef.getheader(range).items():
            headers.add_header(i, j)

        if self.cookie:
            headers.add_header('Cookie', self.cookie)

        path = path.strip().replace(' ', '%20')
        return path, headers

    def http_redirect(self, redurl):
        self.url = redurl
        return self

    def response(self, url, headers, code, length):
        self._response = UrlResponse(url=url, headers=headers, code=code, length=length)

    def reset(self):
        self.url = self.__origin_url
        self._response = None

    def dump_data(self):
        return SourceUrlDumpedData(url=self.__origin_url, headers=dict(self.headers),
                                   cookie=self.cookie, proxy=self.proxy, max_conn=self.max_conn,
                                   rangef=dict(self._rangef), name=self.name,
                                   response=tuple(self._response.dump_data()))

    def load(self, dumped_data):
        data = UrlResponse(*dumped_data)
        self.response(data.url, data.headers, data.code, data.length)

    def getinfo(self):
        return UrlInfo(url=self.__origin_url, headers=list(self.headers.items()),
                       cookie=self.cookie, proxy=self.proxy, max_conn=self.max_conn,
                       rangef=dict(self._rangef), name=self.name, response=self._response)
