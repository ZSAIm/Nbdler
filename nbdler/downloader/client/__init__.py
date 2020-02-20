# ==================================================
# Name:     nbdler/downloader/client/__init__.py
# Author:   ZSAIM
#
# Created:  2020-2-19
# License:  Apache-2.0
# ==================================================

from . import http_client

__all__ = ['get_client']


# 协议注册表
_registry = {}


def get_client(protocol):
    """ 返回指定协议的下载处理客户端。 """
    return _registry[protocol]


def register(protocol, client_hdl):
    """ 注册指定协议的下载客户端。 """
    if protocol not in _registry:
        _registry[protocol] = client_hdl


def main():
    # HTTP协议
    register('http', http_client.HTTPClient)
    register('https', http_client.HTTPClient)


# 注册下载客户端
main()

