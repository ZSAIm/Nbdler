# -*- coding: UTF-8 -*-


class Error(Exception):
    """ 异常错误基类。 """
    def __init__(self, detail=None):
        self.detail = detail


class NetworkBrokenError(Error):
    """ 网络断开异常错误。 """


class ClientError(Error):
    """ 下载客户端错误。"""


class UnknownError(ClientError):
    """ 任何非确定出现的客户端连接错误。"""


class RequestError(Error):
    """ 下载请求打开错误。"""


class MaxRetriesExceededError(Error):
    """ 超出最大重试次数错误。 """


class MissingBlockError(Error):
    """ 下载块缺失错误。 """


# 确定的下载源错误。

class URLError(Error):
    """ 下载源连接错误。"""


class MaxUsedExceededError(URLError):
    """ 下载源超出连接上限错误。"""


class URLUnknownError(URLError):
    """ 下载源连接出现未知错误。 """


class URLTimeoutError(URLError):
    """ 下载源连接超时错误。 """


class URLCriticalError(URLError):
    """ 下载源无法处理连接错误。 """


class NotAPartialResponse(URLError):
    """ 分片请求返回非分片响应错误。 """


# 下载池管理器异常错误

class ManagerError(Error):
    """ 下载池管理器错误。"""
    def __init__(self, detail, tid=None):
        self.tid = tid
        self.detail = detail


class SubprocessUnavailableError(ManagerError):
    """ 子进程不可用错误。"""


class TaskNotReadyError(ManagerError):
    """ 任务未就绪错误。"""
