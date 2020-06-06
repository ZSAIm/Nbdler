

class Error(Exception):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return f'<{self.__class__.__name__} args={self.args} kwargs={self.kwargs}>'


class GatherableError(Error):
    def __init__(self, exception, exc_info, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = exception
        self.exc_info = exc_info

    def __repr__(self):
        return f'<{self.__class__.__name__} exc="{self.exception}">'


class ClientError(GatherableError):
    pass


class HandlerError(GatherableError):
    pass


class UriError(Error):
    pass


class TimeoutError(UriError):
    pass


class FatalError(UriError):
    pass


class MaxRetriesExceeded(ClientError):
    pass
