# -*- coding: UTF-8 -*-
import httplib, urllib, re
from contentType import content_type

class URLinfo(object):
    def __init__(self, url=None, host=None, path=None, port=None, cookie=''):
        self.url = None
        self.host = None
        self.path = None
        self.protocol = None
        self.port = None

        self.cookie = ''
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        self.res_headers = {}
        self.base_url = None
        self.__history = []

        if url is not None:
            self.base_url = [url, host, path, port, cookie]
            if self.load(url, host, path, port, cookie) is False:
                raise Exception('UrlError')

    def get_filename(self):
        assert self.url is None
        if self.res_headers['content-disposition'] is not None:
            filename = re.findall(r'filename="(.*?)"', self.res_headers['content-disposition'])
            if filename != []:
                return filename[0]

        filename = self.path.split('?')[0].split('/')[-1]


        if filename != '':
            if '.' not in filename or filename.split('.')[-1] == '':
                extension = unicode(content_type(self.res_headers['content-type']))
                filename = filename + extension
        else:
            filename = None
        return filename



    def add_headers(self, **args):
        for i, j in args.items():
            for k in self.headers.keys():
                if i.lower() == k.lower():
                    self.headers[k] = j
                    break
            else:
                self.headers[i] = j

    def load(self, url, host=None, path=None, port=None, cookie=''):

        self.protocol, s1 = urllib.splittype(url)
        _host, self.path = urllib.splithost(s1)
        self.host, self.port = urllib.splitport(_host)

        if self.port is None:
            if self.protocol == 'http':
                self.port = 80
            elif self.protocol == 'https':
                self.port = 443

        if host:
            self.host = host
        if path:
            self.path = path
        if port:
            self.port = port

        self.cookie = cookie
        if self.base_url is not None:
            self.base_url = [url, host, path, port, cookie]

        if self.host:
            for i in self.__history:
                if url == i[0]:
                    break
            else:
                self.__history.append([url, host, path, port, cookie])
            try:
                self.__get_request()
                if self.res_headers == {}:
                    return False
                else:
                    return True
            except:
                return False
        else:
            return False

    # def dump(self):
    #     _dump_dict = dict(
    #         host=self.host,
    #         https=self.https,
    #         path=self.path,
    #         port=self.port,
    #         cookie=self.cookie,
    #         headers=self.headers,
    #         content_type=self.content_type,
    #         content_length=self.content_length,
    #         res_headers=self.res_headers,
    #         _URLinfo__history=self.__history
    #     )
    #
    #     return _dump_dict
    #
    # def load(self, _data):
    #     _type = [list, int, str, tuple, int, bool, float, long, dict]
    #
    #     for i, j in _data.items():
    #         for k in _type:
    #             if isinstance(getattr(self, i), k) is True:
    #                 break
    #         else:
    #             if j is not None:
    #                 getattr(self, i).load(j)
    #                 continue
    #
    #         setattr(self, i, j)


    def __get_request(self):
        _count = 5
        while _count:
            try:
                conn = None
                if self.protocol == 'https':
                    conn = httplib.HTTPSConnection("%s:%s" % (self.host, self.port))
                elif self.protocol == 'http':
                    conn = httplib.HTTPConnection("%s:%s" % (self.host, self.port))

                assert conn is not None
                conn.timeout = 5
                conn.request('GET', self.path, {'cookie': self.cookie}.update(self.headers))
                res = conn.getresponse()
            except:
                _count -= 1
                continue

            self.res_headers = res.msg.dict

            if res.status == 302:
                if res.getheader('location') != self.url:
                    if res.getheader('set-cookie') is not None:
                        self.load(res.getheader('location'), cookie=res.getheader('set-cookie'))
                    else:
                        self.load(res.getheader('location'))

                    break
                else:
                    _count -= 1
                    continue

                # 'url seems to be invalid.'
            elif res.status == 405 or res.status == 404 or res.status == 500:
                _count -= 1
                continue
            conn.close()
            break
        else:
            self.res_headers = {}
            # return False

        # return True
    def reload_validate(self, url):
        for i in self.__history:
            if url == i[0]:
                return self.__restore()
        else:
            self.__history.append([url, None, None, None, ''])
        _last_length = self.res_headers['content-length']

        if self.load(url) is True:
            if self.res_headers['content-length'] != _last_length:
                return self.__restore()
        else:
            return self.__restore()

        return True
    # def url_dict(self):
    #     return {
    #         'url': self.url,
    #         'host': self.host,
    #         'path': self.path,
    #         'port': self.port,
    #         'cookie': self.cookie,
    #         'content-length': self.res_headers['content-length']
    #     }

    # def __restore(self, _bak_dict):
    #     self.load(
    #         _bak_dict['url'],
    #         _bak_dict['host'],
    #         _bak_dict['path'],
    #         _bak_dict['port'],
    #         _bak_dict['cookie']
    #     )
    def __restore(self):
        self.__history = []
        return self.load(self.base_url[0], self.base_url[1], self.base_url[2], self.base_url[3], self.base_url[4])

