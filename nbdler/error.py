

class Error(Exception):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class ClientError(Error):
    pass


class HandlerError(Error):
    pass


class UriError(Error):
    pass


class TimeoutError(UriError):
    pass


class FatalError(UriError):
    pass


class MaxRetriesExceeded(ClientError):
    pass
