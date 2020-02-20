# -*- coding: UTF-8 -*-
import gzip
import bz2
import zlib
import json
import pickle


def _pickle_loads(data):
    return pickle.loads(data)


_compress_libs = {
    'gzip': gzip.compress,
    'bz2': bz2.compress,
    'zlib': zlib.compress
}

_decompress_libs = {
    'gzip': gzip.decompress,
    'bz2': bz2.decompress,
    'zlib': zlib.decompress
}

_dumps_libs = {
    'json': json.dumps,
    'pickle': pickle.dumps,

}


_loads_libs = {
    'json': json.loads,
    'pickle': pickle.loads,

}


def dump(file, obj, method, encoding='utf-8'):
    """ 基本数据类型转存。"""
    data = obj
    for m in method:
        if m.lower() in _dumps_libs:
            data = _dumps_libs[m](data)
            continue
        if m.lower() in _compress_libs:
            # 压缩方法需要时已经进行了序列化的对象。
            if type(data) is str:
                data = data.encode(encoding)
            data = _compress_libs[m](data)
            continue
    with open(file, 'wb') as f:
        f.write(data)


def load(file, method):
    with open(file, 'rb') as f:
        data = f.read()

    for m in method:
        if m.lower() in _decompress_libs:
            data = _decompress_libs[m](data)
            continue
        if m.lower() in _loads_libs:
            data = _loads_libs[m](data)
            continue

    return data

