# -*- coding: UTF-8 -*-

from ..utils.misc import Component
import io
import os


class File(Component):
    __slots__ = '_name', '_path', '_size', '_downloading_extension', '_closed', '_fp'

    def __init__(self, path, name, size, overwrite, downloading_extension=None):
        """
        :param
            path    : 文件路径（不包括文件名）
            name    : 文件名称
            size    : 文件大小
            downloading_extension: 安全扩展名（如 '.downloading'）,不指定的话不开启安全扩展名。
        """
        self._name = name
        self._path = path
        self._size = size
        self._downloading_extension = downloading_extension
        self._overwrite = overwrite
        self._closed = True
        self._fp = None

    @property
    def ext(self):
        return os.path.splitext(self._name)[-1]

    @property
    def safe_ext(self):
        return self._downloading_extension

    @property
    def path(self):
        return self._path

    @property
    def name(self):
        return self._name

    @property
    def size(self):
        return self._size

    @property
    def full_path(self):
        """ 如果文件的全路径名。 """
        return os.path.join(self._path, self._name + (self._downloading_extension or ''))

    def open(self):
        """ 打开文件。 """
        fp = io.open(self.full_path, mode='rb+')
        self._fp = fp
        self._closed = False
        return self

    def makefile(self):
        """ 创建指定大小空文件。 """
        if not self._overwrite and os.path.isfile(os.path.join(self._path, self._name)):
            raise FileExistsError('文件 %s 已经存在了。' % os.path.isfile(os.path.join(self._path, self._name)))

        with io.open(self.full_path, mode='wb') as fp:
            if self._size != float('inf'):
                fp.seek(self._size - 1)
                fp.write(b'\x00')

    def write(self, s):
        return self._fp.write(s)

    def writelines(self, lines):
        self._fp.writelines(lines)

    def close(self):
        if self._fp is not None:
            self._fp.close()
            self._fp = None
            self._closed = True

    def is_closed(self):
        return self._closed

    def remove_downloading_extension(self):
        """ 移除下载中文件扩展名。"""
        assert self._closed and self._downloading_extension
        assert os.path.isfile(self.full_path)
        try:
            os.rename(self.full_path, os.path.join(self._path, self._name))
        except FileExistsError:
            if self._overwrite:
                os.remove(os.path.join(self._path, self._name))
                os.rename(self.full_path, os.path.join(self._path, self._name))

    def seek(self, offset, whence=0):
        return self._fp.seek(offset, whence)

    def flush(self):
        self._fp.flush()

    def __snapshot__(self, base_info=False):
        return {
            'name': self._name,
            'path': self._path,
            'size': self._size,
            'overwrite': self._overwrite,
            'downloading_extension': self._downloading_extension
        }

    def __del__(self):
        self.close()

    def __repr__(self):
        return '<File %s>' % os.path.join(self.path, self.name)
