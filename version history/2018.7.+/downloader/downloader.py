# -*- coding: UTF-8 -*-

import httplib,time,os

from DLManager import DLManager
from lib.FileInfo import FileInfo
from lib.URLinfo import URLinfo


class downloader(object):
    def __init__(self):

        self.file = FileInfo()
        self.url = None
        self.ThreadCount = 5

        self.changeCount = 3
        self.__fileExists = False

    def config(self, name=None, path='', thread_count=5, url=None, url_host=None, url_path=None, url_port=None):
        """specify [name,[path,[thread_count]"""
        self.file.path = path
        self.file.name = name
        self.ThreadCount = thread_count
        if url:
            self.url = URLinfo(url, url_host, url_path, url_port)
            self.file.make_name(self.url, self.file.name)
        if os.path.exists(self.file.path + self.file.name):
            self.__fileExists = True


    def __config(self):
        """inner config, ready to open url.
        , and make sure no problem."""
        self.file.make_name(self.url, self.file.name)
        self.file.size = self.url.content_length

        if os.path.exists((self.file.path + self.file.name).decode('utf-8')):
            self.__fileExists = True
            return False
        return True
    def __get_file_info(self):
        """update file and url information,
        and check if it works.."""
        try:
            if self.url.https:
                conn = httplib.HTTPSConnection("{0}:{1}".format(self.url.host, self.url.port), timeout=10)
            else:
                conn = httplib.HTTPConnection("{0}:{1}".format(self.url.host, self.url.port), timeout=10)

            conn.request('GET', self.url.path, '')
            res = conn.getresponse()
        except:
            time.sleep(0.5)
            self.changeCount -= 1
            if self.changeCount != 0:
                return self.__get_file_info()
            else:

                # "CONNECT ERROR, THIS URL DON'T REACTE."
                return False


        if res.status == 302:
            if res.getheader('location') != self.url.url:
                self.url = URLinfo(res.getheader('location'))
                self.__get_file_info()
            else:
                # print 'url seems to be invalid.'
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






    def open(self, url=None, host=None, path=None, port=None):
        """open url to get ready to download."""
        if self.__fileExists:
            raise Exception('FileExistsError')
            # return None
        try:
            if url:
                self.url = URLinfo(url, host, path, port)
            else:
                if not self.url:
                    raise Exception('NOURL')

        except:
            raise Exception('URLError')


        if not self.__get_file_info():
            raise Exception("URLConnectError: CONNECT ERROR, THIS URL DON'T REACTE.")
            # return None

        if not self.__config():
            raise Exception('FileExistsError')

        return DLManager(self.url, self.file, self.ThreadCount)





if __name__ == '__main__':

    from ___progressbar import progressBar

    address = ['https://sm.myapp.com/original/Office/DeskGo_2_9_1027_127_lite-15000.exe',
               'https://sm.myapp.com/original/Office/DeskGo_2_9_1027_127_lite-15000.exe',
               'https://sm.myapp.com/original/Office/DeskGo_2_9_1027_127_lite-15000.exe',
               'https://sm.myapp.com/original/Office/DeskGo_2_9_1027_127_lite-15000.exe',
               'https://sm.myapp.com/original/Office/DeskGo_2_9_1027_127_lite-15000.exe',
               'https://sm.myapp.com/original/Office/DeskGo_2_9_1027_127_lite-15000.exe']

    #address =  ['https://dldir1.qq.com/qqfile/qq/TIM2.1.8/23475/TIM2.1.8.exe']
    # address =  ['http://xiazai.xiazaiba.com/Soft/T/TIM_2.2.0_XiaZaiBa.zip']
    # address =  ['http://xiazai.xiazaiba.com/Soft/M/MarvelousDesigner7_Personal_4_1_100_XiaZaiBa.zip']

    list = []
    bar = []
    for index, x in enumerate(address):
        list.append(downloader())
        list[-1].config(str(index), thread_count=5)
        a = list[-1].open(x)
        a.start()
        list[-1] = a
        bar.append(progressBar(index, a.file.size))

    while True:
        for i, j in enumerate(list):
            bar[i].update(j.file.size - j.getLeft())
            if not j.isAlive():
                break
        time.sleep(0.5)
