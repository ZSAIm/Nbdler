
from nbdler.url.basic import BasicUrl
from nbdler.struct.dump import UrlResponseDumpedData


class UrlResponse(BasicUrl):
    def __init__(self, url, headers, code, length):
        super(UrlResponse, self).__init__(url, headers)
        self.code = code
        self.length = length

    def dump_data(self):
        return UrlResponseDumpedData(url=self.url, headers=dict(self.headers),
                                     code=self.code, length=self.length)

