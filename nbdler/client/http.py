
from six.moves.http_client import HTTPSConnection as HTTPSConnection_origin, HTTPConnection

from nbdler.client.abstract_client import AbstractClient
from six.moves.urllib.error import URLError, HTTPError
from nbdler.exception import URLUnknownError, HTTP4XXError, URLConnectFailed
from nbdler.struct.signal import SIGNAL_TASK_BUFF, SIGNAL_TASK_SLICE, ID_TASK_SLICE, SIGNAL_THREAD_END, ID_TASK_PAUSE, \
    SIGNAL_GAIERROR, SIGNAL_CRASH, SIGNAL_TIMEOUT, SIGNAL_UNKNOWN, \
    SIGNAL_EMPTY_RECV, SIGNAL_URL_STATUS, SIGNAL_NORMAL, ID_SWITCH, ID_WAIT

from six.moves.queue import Queue
from nbdler.struct.misc import Slice, InitialResult, ClientException
import re
import ssl
import socket
from time import sleep


https_context = ssl._create_unverified_context()

HTTPSConnection = lambda **kwargs: HTTPSConnection_origin(context=https_context, **kwargs)


class HTTPClient(AbstractClient):
    __connected = False

    def __init__(self, source, progress):
        self.source = source
        self.progress = progress

        self._response = None
        self._connection = None

        self._callback = None
        self.__signal = Queue()

    def geturl(self):
        return self.source.url

    def _buffer(self, buff):
        if buff:
            self.progress.buffer(buff)
            self._callback.put_nowait(SIGNAL_TASK_BUFF(len(buff)))

    def _build_connection(self):
        if self.source.scheme == 'http':
            client_handler = HTTPConnection
        elif self.source.scheme == 'https':
            client_handler = HTTPSConnection
        else:
            raise ValueError('http client got an unexpected url protocol (%s).' %
                             self.source.scheme)

        conn = client_handler(host=self.source.hostname, port=self.source.port, timeout=5)

        req_range = (self.progress.begin + self.progress.go_inc, self.progress.end)
        path, headers = self.source.http_request_header(req_range)
        conn.request('GET', path, '', dict(headers))

        return conn

    def _conn_response(self, conn):
        res = conn.getresponse()
        sleep(0.01)
        if res.code in (301, 302, 303, 307):
            redurl = res.getheader('location', None)
            self.source.http_redirect(redurl)
            res.close()
            conn.sock.shutdown(socket.SHUT_RDWR)
            conn.close()
            conn = self._build_connection()
            return self._conn_response(conn)
        elif 400 <= res.code < 500:
            raise HTTP4XXError("(%d)URL: %s " % (res.code, self.source.url))
        elif res.code not in (200, 206):
            self._callback.put_nowait(
                SIGNAL_URL_STATUS(SIGNAL_UNKNOWN(self))
            )
            raise URLUnknownError()
        return conn, res

    def connect(self):
        conn = self._build_connection()
        conn, res = self._conn_response(conn)
        self._connection = conn
        self._response = res
        self.source.response(self.source.url, res.getheaders(), res.getcode(), res.length)
        self.__connected = True
        return res

    def retrieve(self):

        self.progress.start()
        self._callback.put_nowait(
            SIGNAL_URL_STATUS(SIGNAL_NORMAL(ClientException(client=self, exception=None)))
        )
        buff = b''
        while True:
            if not self.__signal.empty():
                signal = self.__signal.get()
                if signal.id == ID_TASK_SLICE:
                    putrange = self.progress.slice_check(signal.content)
                    self._callback.put_nowait(
                        SIGNAL_TASK_SLICE(Slice(client=HTTPClient, range=putrange))
                    )
                elif signal.id == ID_TASK_PAUSE:
                    self._buffer(buff)
                    self.__signal.task_done()
                    break
                elif signal.id == ID_WAIT:
                    sleep(signal.content)

                self.__signal.task_done()

            prv_len = len(buff)
            remain = self.progress.length - self.progress.go_inc
            try:
                if remain >= 8192:
                    buff += self._response.read(8192)
                elif remain > 0:
                    buff += self._response.read(remain)
                else:
                    self._buffer(buff)
                    break
            except (socket.gaierror, URLError, HTTPError, socket.timeout, Exception) as e:
                self._buffer(buff)
                self._exception_handler(e)
                break

            if len(buff) - prv_len == 0:
                self._buffer(buff)
                if self._response.chunked and not self._response.fp:
                    self.progress.force_to_finish_go()

                self._callback.put_nowait(SIGNAL_EMPTY_RECV(self))
                break
            self.progress.go(len(buff) - prv_len)

            if self.progress.go_inc >= self.progress.length:
                self._buffer(buff)
                break
            elif len(buff) >= 1048576:  # 1 MB
                self._buffer(buff)
                del buff
                buff = b''

        self.progress.stop()

    def close(self):
        response = self._response
        connection = self._connection
        self._response = None
        self._connection = None
        self.__connected = False

        if response:
            response.close()
        if connection:
            if connection.sock:
                connection.sock.shutdown(socket.SHUT_RDWR)
            connection.close()

    def getheader(self, name, default=None):
        return self._response.getheader(name, default)

    def run(self, callback):
        self._callback = callback

        if not self.__signal.empty():
            signal = self.__signal.get()
            if signal.id == ID_TASK_SLICE:
                putrange = self.progress.slice_check(signal.content)
                self._callback.put_nowait(
                    SIGNAL_TASK_SLICE(Slice(client=HTTPClient, range=putrange))
                )
            elif signal.id == ID_SWITCH:
                self.source = signal.content
            elif signal.id == ID_TASK_PAUSE:
                self._callback = None
                callback.put_nowait(SIGNAL_THREAD_END(self))
            elif signal.id == ID_WAIT:
                sleep(signal.content)
            self.__signal.task_done()

        try:
            if not self.__connected:
                self.connect()
            self.retrieve()
        except (socket.gaierror, socket.timeout, URLUnknownError,
                HTTP4XXError, URLError, HTTPError, Exception) as e:
            self._exception_handler(e)
        finally:
            self.close()

        self._callback = None
        callback.put_nowait(SIGNAL_THREAD_END(self))

    def open_only(self, callback):
        self._callback = callback

        res = None
        try:
            res = self.connect()
        except (socket.gaierror, socket.timeout, URLUnknownError,
                HTTP4XXError, URLError, HTTPError, Exception) as e:
            self._exception_handler(e)

        self._callback = None
        return res

    def _exception_handler(self, exception):
        client_exc = ClientException(client=self, exception=exception)
        if type(exception) in (URLError, HTTPError, socket.timeout):
            signal_type = SIGNAL_TIMEOUT
        elif type(exception) is socket.gaierror:
            signal_type = SIGNAL_GAIERROR
        elif type(exception) is HTTP4XXError:
            signal_type = SIGNAL_CRASH
        else:
            signal_type = SIGNAL_UNKNOWN

        self._callback.put_nowait(
            SIGNAL_URL_STATUS(signal_type(client_exc))
        )

    def install_callback(self, callback):
        self._callback = callback

    def clear_callback(self):
        self._callback = None

    def send_signal(self, signal):
        self.__signal.put_nowait(signal)

    def write_to_file(self, fp):
        if not self.progress.is_empty_buff():
            fp.seek(self.progress.begin + self.progress.done_inc)
            fp.writelines(self.progress.fetch_buffer())

    def getprogress(self):
        return self.progress

    def getsource(self):
        return self.source

    def getresonse(self):
        return self._response

    def clear_signal(self):
        del self.__signal
        self.__signal = Queue()


def build_initial_opener(source, progress, callback):
    client = HTTPClient(source, progress)
    client.install_callback(callback)
    res = client.open_only(callback)

    if not res:
        raise URLConnectFailed()

    filesize = res.length
    filename = None

    cont = client.getheader('content-disposition')
    if cont:
        filename = re.search('filename="?(.*)"?', cont).group(1)

    if not filename:
        filename = source.path.split('/')[-1]

    if not filename:
        filename = None

    progress.range = (0, filesize)

    if not res.chunked and not filesize:
        raise AssertionError()

    client.clear_callback()
    return InitialResult(client=client, filename=filename, filesize=filesize or float('inf'),
                         unspecified_size=res.chunked, response=res)

