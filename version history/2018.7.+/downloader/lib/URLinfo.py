# -*- coding: UTF-8 -*-
import httplib, time

class URLinfo(object):
    def __init__(self, url, host=None, path=None, port=None, cookie=''):
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

        self.cookies = cookie
        self.content_type = None
        self.content_length = 0
        self.accept_ranges = False
        self.changeCount = 3

        if host:
            self.host = host
        if path:
            self.path = path
        if port:
            self.port = port



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

    def __get_file_info(self):
        try:
            if self.url.https:
                conn = httplib.HTTPSConnection("{0}:{1}".format(self.url.host, self.url.port))
            else:
                conn = httplib.HTTPConnection("{0}:{1}".format(self.url.host, self.url.port))

            conn.request('GET', self.url.path, 'cookie:' + self.cookies)
            res = conn.getresponse()
        except:
            time.sleep(0.5)
            self.changeCount -= 1
            if self.changeCount != 0:
                return self.__get_file_info()
            else:
                # "CONNECT ERROR, THIS URL DON'T REACTE."
                return False
        print res.status
        if res.status == 302:

            if res.getheader('location') != self.url.url:

                self.url = URLinfo(res.getheader('location'))

                self.__get_file_info()

            else:
                # 'url seems to be invalid.'
                return False
        elif res.status == 405 or res.status == 404 or res.status == 500:
            self.changeCount -= 1
            if self.changeCount != 0:
                return self.__get_file_info()
            else:
                # "CONNECT ERROR, THIS URL DON'T REACTE."
                return False
        else:
            self.url.content_length = int(res.getheader('content-length'))

        if res.getheader('accept-ranges'):
            self.url.accept_ranges = True
        conn.close()
        return True

    def isURL(self):
        if self.host:
            return True
        else:
            return False

