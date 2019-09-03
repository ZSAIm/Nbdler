
import io
import os
from collections import namedtuple
from typing import AnyStr, List
from nbdler.struct.dump import FileDumpedData

FileInfo = namedtuple('FileInfo', 'name path size block_size')


class File:
    def __init__(self, path, name, size):
        self._name = name
        self._path = path
        self._size = size

        self._fp = None
        self._closed = True

    @property
    def ext(self):
        return os.path.splitext(self._name)[-1]

    def getpath(self):
        return self._path

    def getname(self):
        return self._name

    def getsize(self):
        return self._size

    def open(self):
        fp = io.open(os.path.join(self._path, self._name), mode='rb+')
        self._fp = fp
        self._closed = False
        return self

    def makefile(self):
        with io.open(os.path.join(self._path, self._name), mode='wb') as fp:
            if self._size != float('inf'):
                fp.seek(self._size - 1)
                fp.write(b'\x00')

    def write(self, s: AnyStr) -> int:
        return self._fp.write(s)

    def writelines(self, lines: List[AnyStr]) -> None:
        self._fp.writelines(lines)

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
            self._closed = True

    def isclosed(self):
        return self._closed

    def __del__(self):
        self.close()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._fp.seek(offset, whence)

    def flush(self) -> None:
        self._fp.flush()

    def dump_data(self):
        return FileDumpedData(path=self._path, name=self._name, size=self._size)


