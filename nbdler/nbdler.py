# -*- coding: UTF-8 -*-

from DLHandler import *
# import DLHandler
import logging

LOG_FORMAT = "%(asctime)s,%(msecs)03d - %(levelname)s - %(threadName)-12s - (%(progress)s)[%(urlid)s] - %(message)s"

logging.basicConfig(format=LOG_FORMAT, datefmt="%m/%d/%Y %H:%M:%S", level=logging.CRITICAL)

logger = logging.getLogger('nbdler')


def yeild_data(iter_list, default, n):
    for i in range(n):
        if len(iter_list) == 0:
            yield default
        elif len(iter_list) == 1:
            yield iter_list[0]
        elif len(iter_list) == n:
            yield iter_list[i]
        else:
            raise Exception('IterLenError')


def url_params_default():
    return (('urls', ''),
            ('cookies', ''),
            ('hosts', None),
            ('ports', None),
            ('paths', None),
            ('headers', None),
            ('max_threads', -1))


def url_zip_yield(kwargs, zip_len):
    pack_yield = []
    for i, j in url_params_default():
        pack_yield.append(yeild_data(kwargs.get(i, []), j, zip_len))

    return zip(*pack_yield)

def open(fp=None, **kwargs):

    dlh = Handler()

    if fp:
        if 'read' in dir(fp):
            fp.seek(0)
            packet = fp.read()
        else:
            with io.open(fp + '.nbdler', 'rb') as f:
                packet = f.read()

        packet = eval(zlib.decompress(packet))

        dlh.unpack(packet)

    else:

        dlh.file.name = kwargs.get('filename', '')
        dlh.file.path = kwargs.get('filepath', '')
        dlh.file.BLOCK_SIZE = kwargs.get('block_size', 1024*1024)
        dlh.file.buffer_size = kwargs.get('buffer_size', 20*1024*1024)

        dlh.url.max_conn = kwargs.get('max_conn', 5)
        dlh.url.max_speed = kwargs.get('max_speed', -1)
        urls = kwargs.get('urls', [])
        if urls:
            for i, j, k, l, m, n, o in url_zip_yield(kwargs, len(urls)):
                dlh.addNode(id=-1, url=i, cookie=j, host=k, port=l, path=m, headers=n, max_thread=o)


    return dlh



