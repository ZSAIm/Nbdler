# -*- coding: UTF-8 -*-


class BlockManagerBody:
    __slots__ = '_block_mgr'

    def __init__(self, block_mgr):
        self._block_mgr = block_mgr

    def __getitem__(self, item):
        """ 返回对应下载块的字典数据。"""
        if type(item) in (list, tuple):
            return [self._block_mgr[i].__snapshot__() for i in item]
        return self._block_mgr[item].__snapshot__()

    def get_all(self):
        """ 返回所有下载块字典数据的迭代对象。 """
        return self._block_mgr.__snapshot__()


class Body:
    """ 下载任务信息。"""
    def __init__(self, console):
        self._cfg = console.cfg
        self._file = console.file
        self._url = console.url
        self._block_mgr = BlockManagerBody(console.block_mgr)

    @property
    def config(self):
        return dict(self._cfg)

    @property
    def file(self):
        return self._file.__snapshot__()

    @property
    def url(self):
        return self._url.__snapshot__()

    @property
    def block_mgr(self):
        return self._block_mgr

    @property
    def all(self):
        return {
            'config': self.config,
            'file': self.file,
            'url': self.url,
            'block_mgr': self.block_mgr.get_all()
        }
