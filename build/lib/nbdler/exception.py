
class Error(Exception):
    pass


# class ProcessRuntimeError(Error):
#     pass

class ManagerError(Error):
    pass


class ChildProcessDisable(ManagerError):
    pass


class HandlerError(Error):
    pass


class ClientError(Error):
    pass


class FileAlreadyExisted(HandlerError):
    pass


class HandlerBusy(HandlerError):
    pass


class HTTP4XXError(ClientError):
    pass


class UnknownError(HandlerError):
    pass


class URLError(Error):
    pass


class URLPoolEmpty(URLError):
    pass


class InvalidURLError(URLError):
    pass


class URLCrash(URLError):
    pass


class URLTimeout(URLError):
    pass


class URLUnknownError(URLError):
    pass


class NetworkDisconnected(URLError):
    pass


class MaxUsedExceedError(URLError):
    pass


class URLConnectFailed(URLError):
    pass


class URLMaxRetriesExceeded(URLError):
    pass







