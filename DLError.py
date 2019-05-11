
import threading






class DLUrlError(Exception):
    def __init__(self, thread, conn, res):
        self.thread = thread

        self.connection = conn
        self.respond = res


class HTTPErrorCounter:
    ERR_4XX_THRESHOLD = 3
    ERR_TIMEOUT_THRESHOLD = 10
    ERR_UNKNOWN_THRESHOLD = 10
    def __init__(self):
        self._counter = {}

    def http_timeout(self, conn, res):

        self._counter['timeout'] = self._counter.get('timeout', 0) + 1
        if self._counter['timeout'] % HTTPErrorCounter.ERR_TIMEOUT_THRESHOLD == 0:
            raise DLUrlError(threading.current_thread(), conn, res)

    def http_4xx(self, conn, res):
        self._counter[res.status] = self._counter.get(res.status, 0) + 1
        if self._counter[res.status] % HTTPErrorCounter.ERR_4XX_THRESHOLD == 0:
            raise DLUrlError(threading.current_thread(), conn, res)

    def http_unknown(self, conn, res):
        self._counter['unknown'] = self._counter.get('unknown', 0) + 1
        if self._counter['unkown'] % HTTPErrorCounter.ERR_UNKNOWN_THRESHOLD == 0:
            raise DLUrlError(threading.current_thread(), conn, res)

    def getCounter(self, status):
        return self._counter[status]

    def clear(self):
        self._counter = {}
