from nbdler.url.basic import UrlInfo
from nbdler.struct.dump import RequestDumpedData
from nbdler.collect import SIMPLE_CHROMIUM_HEADERS
DEFAULT_BLOCK_SIZE = 512 * 1024
DEFAULT_OPEN_MAX_RETRIES = 5


class Request:
    def __init__(self, url=None, headers=SIMPLE_CHROMIUM_HEADERS, cookie=None,
                 *, proxy=None, max_conn=None, range_format=None, name='main',
                 filepath='', block_size=DEFAULT_BLOCK_SIZE, max_retries=DEFAULT_OPEN_MAX_RETRIES,
                 max_thread=None, child_process=False, resume=False):

        self._sources = []
        self.filepath = filepath
        self.block_size = block_size
        self.max_retries = max_retries
        self.max_thread = max_thread
        self.child_process = child_process
        self.resume = resume
        if url:
            self.put(url, headers, cookie, proxy=proxy,
                     max_conn=max_conn, rangef=range_format, name=name)

    def put(self, url, headers=SIMPLE_CHROMIUM_HEADERS, cookie=None, *,
            proxy=None, max_conn=None, rangef=None, name=None):
        srcurl = UrlInfo(url=url, headers=headers, cookie=cookie, proxy=proxy,
                         max_conn=max_conn, rangef=rangef, name=str(name))
        self._sources.append(srcurl)
        return srcurl

    def __iter__(self):
        return iter(self._sources)

    def dump_data(self):
        sources = []
        for i in self:
            sources.append(tuple(i))
        return RequestDumpedData(sources=sources, resume=self.resume, block_size=self.block_size,
                                 max_retries=self.max_retries, max_thread=self.max_thread,
                                 child_process=self.child_process)

    @staticmethod
    def loads(dumped_data):
        data = RequestDumpedData(*dumped_data)

        req = Request(filepath=data.filepath, resume=data.resume, max_retries=data.max_retries,
                      child_process=data.child_process, max_thread=data.max_thread,
                      block_size=data.block_size)
        for i in data.sources:
            req.put(**dict(data))

        return req
