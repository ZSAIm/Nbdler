# -*- coding: UTF-8 -*-

import time,os
from DLManager import DLManager
from lib.FileInfo import FileInfo
from lib.URLinfo import URLinfo

class downloader:
    def __init__(self):

        self.file = FileInfo()
        self.url = []
        self._kwargs = None


    def config(self, **kwargs):
        """specify [name,[path,[thread_count]

        args:
            ::param:    file_name       :
            ::param:    file_path       :
            ::param:    thread_count    :
            ::param:    force           :
            ::param:    complete_validate:
            ::param:    fix_damage      :
            ::param:    block_size      :


        """

        self.file.path = unicode(kwargs.get('file_path', ''))

        if kwargs.get('file_name') is not None:
            self.file.name = unicode(kwargs.get('file_name'))


        self.file.force = kwargs.get('force', False)

        self._kwargs = kwargs


    def add_server(self, url, host=None, path=None, port=None, cookie='', headers=None):
        """append server. in order to multi-server to download."""
        # self.__is_multi_serves = True
        # if isinstance(self.url, list) is True:
        self.url.append(URLinfo(url, host, path, port, cookie))
        if headers is not None:
            self.url[-1].add_headers(headers)
        # else:
        #     self.url = []

    def clear_servers(self):
        self.url = []

    def __config(self):
        """inner config, ready to open url.
        , and make sure no problem."""

        _size = self.url[0].content_length
        for i in self.url:
            if _size != i.content_length:
                raise Exception("ContentLenNoMatch", _size, i.content_length)

        self.file.make_name(self.url[0], self.file.name)

        self.file.size = _size

        if os.path.exists(os.path.join(self.file.path, self.file.name)):
            self.file.exist = True


    def open(self, **kwargs):
        """open url to get ready to download.

        args:
            ::param:    file_name       :
            ::param:    file_path       :
            ::param:    thread_count    :
            ::param:    force           :
            ::param:    complete_validate:
            ::param:    fix_damage      :
            ::param:    block_size      :

        """
        if not self.url:
            raise AttributeError
        if kwargs:
            self.config(**kwargs)

        self.__config()

        if self.file.force is not True and self.file.exist is True:
            raise Exception('FileExistsError')

        if self._kwargs is not None:
            return DLManager(self.url, self.file, **self._kwargs)
        else:
            return DLManager(self.url, self.file)

    def load(self, path, name):

        import cPickle

        if os.path.exists(os.path.join(path, name + '.pkl')) is True:
            with open(os.path.join(path, name + '.pkl'), 'rb') as f:

                pkl = cPickle.Unpickler(f)
                self.url = pkl.load()
                self.file = pkl.load()

                return DLManager(self.url, self.file, pkl.load())
            # return None
        else:
            return None

if __name__ == '__main__':


    from ___progressbar import progressBar

    _list = []
    _bar = []
    for index in range(3):
        _list.append(downloader())
        _list[-1].config(file_name=str(index), thread_count=10, force=True)
        _list[-1].add_server('http://xiazai.xiazaiba.com/Soft/T/TIM_2.2.0_XiaZaiBa.zip')
        _list[-1].add_server('http://dblt.xiazaiba.com/Soft/T/TIM_2.2.0_XiaZaiBa.zip')

        a = _list[-1].open()
        a.start()
        _list[-1] = a
        _bar.append(progressBar(index, a.file.size))


    while True:
        _end = True
        for i, j in enumerate(_list):
            if j.isDone() is False:
                _end = False
                _bar[i].update(j.file.size - j.getLeft(), str(int(j.getinsSpeed() / 1024)) + ' kb/s')
        time.sleep(0.5)
        if _end is True:
            break