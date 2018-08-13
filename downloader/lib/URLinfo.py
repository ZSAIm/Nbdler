# -*- coding: UTF-8 -*-
import httplib

class URLinfo(object):
    def __init__(self, url=None, host=None, path=None, port=None, cookie=''):
        # self.id = id
        self.__history = []
        if url is not None:
            if self.reload_force(url, host, path, port, cookie) is False:
                raise Exception('UrlError')


    def add_headers(self, **args):

        for i, j in args.items():
            for k in self.headers.keys():
                if i.lower() == k.lower():
                    self.headers[k] = j
                    break
        # self.headers.update(args)


    def reload_force(self, url, host=None, path=None, port=None, cookie=''):
        self.url = url

        try:
            self.host = self.url_host()
            self.https = self.url_https()
            self.path = self.url_path()
            self.port = self.url_port()
        except:
            self.host = None
            self.path = None
            self.port = None

        self.cookie = cookie
        self.content_type = None
        self.content_length = 0
        self.res_headers = None
        # self.accept_ranges = False
        # self.changeCount = 3
        self.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        if host:
            self.host = host
        if path:
            self.path = path
        if port:
            self.port = port
        if self.isURL() is True:

            self.__get_file_info()
            self.__history.append([url, host, path, port, cookie])
            return True
        else:
            # raise Exception('UrlError')
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

    def url_host(self):
        """ host:port """
        txt = self.url.split(r'://')[-1]
        return txt[:txt.index(r'/')]

    def url_https(self):
        """https or http"""
        txt = self.url.split(r'://')[0].lower()

        if txt == 'https':
            return True
        elif txt == 'http':
            return False
        else:
            # 'Not A Valid Url or Not Http or Https!'

            return None

    def url_path(self):
        """ path """
        txt = self.url.split(r'://')[-1]
        if '/' in txt:
            return txt[txt.index(r'/'):]
        else:
            return ''


    def url_port(self):
        """split port from host and correct host, or default port"""
        # print self.host
        t = self.host.split(':')
        self.host = t[0]

        if len(t) > 1:

            return int(t[-1])
        else:
            if self.https:
                return 443
            else:
                return 80

    # def add_headers(self):
    #     self.header

    def __get_file_info(self):
        _count = 5
        while _count:
            try:
                if self.https:
                    conn = httplib.HTTPSConnection("%s:%s" % (self.host, self.port))
                else:
                    conn = httplib.HTTPConnection("%s:%s" % (self.host, self.port))
                conn.timeout = 5
                # self.header = ''
                conn.request('GET', self.path, {'cookie': self.cookie}.update(self.headers))
                res = conn.getresponse()
            except:
                _count -= 1
                continue

            self.res_headers = res.getheaders()

            if res.status == 302:
                if res.getheader('location') != self.url:
                    if res.getheader('set-cookie') is not None:
                        self.reload_force(res.getheader('location'), cookie=res.getheader('set-cookie'))
                    else:
                        self.reload_force(res.getheader('location'))

                    break
                else:
                    _count -= 1
                    continue

                # 'url seems to be invalid.'
            elif res.status == 405 or res.status == 404 or res.status == 500:
                _count -= 1
                continue
                    # "CONNECT ERROR, THIS URL DON'T REACTE."
            else:
                self.content_length = int(res.getheader('content-length'))


            if res.getheader('accept-ranges'):
                self.accept_ranges = True
            else:
                self.accept_ranges = None
            conn.close()
            break
        # print self.content_length
    def isURL(self):
        if self.host:
            return True
        else:
            return False

    # def reload_force(self, url, host):


    def reload_validate(self, url):
        if url not in self.__history:
            self.__history.append(url)
        else:
            return False
        self.__bak = self.url_dict()

        self.reload_force(url)

        if self.content_length != self.__bak['content_length']:
            self.__restore()
            return False

        return True

    def url_dict(self):
        # self.__bak =
        return {'url': self.url, 'host': self.host, 'path': self.path,
                'port': self.port, 'cookie': self.cookie, 'content_length': self.content_length}

    def __restore(self):
        self.reload_force(self.__bak['url'],self.__bak['host'],
                        self.__bak['path'], self.__bak['port'], self.__bak['cookie'])
        self.content_length = self.__bak['content_length']


