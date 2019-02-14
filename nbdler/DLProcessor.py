

import socket, ssl
import threading
# import DL.progress
import time
# import sys
import DLInfos
# import math
import logging


logger = logging.getLogger('nbdler')

RECV_EMPTY_RETRY_THRESHOLD = 5
RECV_404_RETRY_THREADSOLD = 5
MAX_BUFFER_SIZE = 1024 * 1024 * 1

socket.setdefaulttimeout(3)

class OpaReq:
    def __init__(self):
        self.cut = []
        self.pause = False
        self.switch = False
        self.wait = 0

    def clear(self):
        self.cut = []
        self.pause = False
        self.switch = False
        self.wait = 0


class Processor(object):
    def __init__(self, Progress, Urlid):
        self.progress = Progress
        self.url = None
        self.urlid = Urlid
        self.buff = ''

        self.opareq = OpaReq()
        self.__opa_lock__ = threading.Lock()

        self.target = None

        self.__thread__ = None
        self.__run_lock__ = threading.Lock()
        self.__404_counter__ = 0

        self.__buff__lock__ = threading.Lock()

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        if key == 'urlid':
            if self.progress.globalprog.handler.url.dict.has_key(self.urlid):
                self.url = self.progress.globalprog.handler.url.dict[self.urlid]
                self.target = DLInfos.Target(self.url.url, None, self.url.headers)
            else:
                self.url = None
                self.target = None

    def run(self):
        with self.__run_lock__:
            if not self.url:
                if not self.progress.globalprog.handler.url.dict.has_key(self.urlid):
                    msg = 'UrlidNoFound: (Urlid = %d) - about to getSwitch()' % self.urlid
                    extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
                    logger.warning(msg, extra=extra)
                    self.getSwitch()
                    # raise Exception('UrlidNoFound')

                self.url = self.progress.globalprog.handler.url.dict[self.urlid]
                self.target = DLInfos.Target(self.url.url, None, self.url.headers)

            if not self.progress.status.go_end and not self.progress.status.pauseflag:
                if not self.__thread__ or (self.__thread__ and not self.__thread__.isAlive()):
                    if self.opareq.pause:
                        self.getPause()
                        return
                    if self.opareq.cut:
                        self.getCut()
                    self.progress.status.startGo()
                    self.__thread__ = threading.Thread(target=self.__getdata__, name='Processor')
                    self.__thread__.start()

                    msg = 'RunThread: %s' % self.__thread__
                    extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
                    logger.debug(msg, extra=extra)

            else:
                self.close()


    def __getdata__(self):
        if self.opareq.cut:
            self.getCut()
        if self.opareq.pause:
            self.getPause()
            return
        sock, buff = self.__make_socket__()
        if self.opareq.cut:
            self.getCut()
        if self.opareq.pause:
            self.getPause()
            return
        if not sock:
            msg = 'SocketNotBuilt: ->rerun.'
            extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
            logger.warning(msg, extra=extra)
            self.target = DLInfos.Target(self.url.url, None, self.url.headers)
            # sock.shutdown(socket.SHUT_RDWR)
            time.sleep(2)
            self.run()
            return
        else:

            status, res_headers = self.__parse_http__(buff[:(buff.index('\r\n\r\n'))])

            if status == 302:
                self.__302__(sock, res_headers)
                return
            elif status == 404:
                self.__404__(sock)
                return
                # raise Exception('404')
            elif status != 206:
                msg = 'ErrorCode: %d' % status
                extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
                logger.critical(msg, extra=extra)
                self.__404__(sock)
                return
                # raise Exception('UrlExpire', status)

            self.__404_counter__ = 0

            buff = buff[(buff.index('\r\n\r\n') + 4):]

            # assert self.progress.length >= len(buff)
            #
            if self.progress.length < len(buff):
                msg = 'BufferLenExceed'
                logger.warning(msg, extra={'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end)})
                # raise Exception('BufferLenExceed', self.progress.end - self.progress.begin, len(buff))
                return
                # print(self.progress.end - self.progress.begin, len(buff))

            self.progress.go(len(buff))
            self.__recv_loop__(sock, buff)

            sock.shutdown(socket.SHUT_RDWR)

    def __make_socket__(self):
        msg = 'SocketConnect: ++++++++++++'
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.debug(msg, extra=extra)
        sock = None
        buff = ''

        try:
            ip = socket.gethostbyname(self.target.host)
        except:

            msg = 'GetHostTimeOut'
            extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
            logger.warning(msg, extra=extra)
            return


        if self.target.protocol == 'https':
            sock = ssl.wrap_socket(socket.socket())
        elif self.target.protocol == 'http':
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        assert sock is not None

        if self.opareq.pause:
            self.getPause()
            return None, ''

        try:
            sock.connect((ip, self.target.port))
            packet = 'GET %s HTTP/1.1\r\n' % self.target.path + \
                     'Host: %s\r\n' % self.target.host + \
                     'Connection: keep-alive\r\n' + \
                     'Range: bytes=%d-%d\r\n' % (self.progress.begin + self.progress.go_inc, self.progress.end) + \
                     '%s' + \
                     '\r\n'

            pack_format = ''
            for i, j in self.url.headers.items():
                pack_format += i + ': ' + j + '\r\n'

            packet = packet % pack_format
            sock.send(packet)
            buff = sock.recv(1024)
        except:
            # sock.shutdown(socket.SHUT_RDWR)
            sock = None
        else:
            if not buff:
                sock.shutdown(socket.SHUT_RDWR)
                sock = None
            else:
                while '\r\n\r\n' not in buff:
                    buff += sock.recv(512)
                    if 'HTTP' not in buff:
                        sock.shutdown(socket.SHUT_RDWR)
                        sock = None
                        break
        msg = 'SocketConnect: ------------'
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.debug(msg, extra=extra)

        return sock, buff

    def __302__(self, sock, headers):
        if headers.get('location', None):
            # with self.url.target_lock:
            self.target = DLInfos.Target(headers.get('location'), None, headers)
        sock.shutdown(socket.SHUT_RDWR)

        msg = 'HTTP 302: ->continue("%s")' % headers.get('location', None)
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.debug(msg, extra=extra)

        self.run()


    def __404__(self, sock):
        self.__404_counter__ += 1
        self.target = DLInfos.Target(self.url.url, None, self.url.headers)
        sock.shutdown(socket.SHUT_RDWR)

        msg = 'HTTP 404: ->rerun.'
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.warning(msg, extra=extra)


        time.sleep(2)
        if self.__404_counter__ > RECV_404_RETRY_THREADSOLD:
            self.getSwitch()
        self.run()

    def __parse_http__(self, http_head):
        status_bar = http_head[:http_head.index('\r\n')+2]
        status = int(status_bar.split(' ')[1])

        header = http_head[http_head.index('\r\n')+2:]

        res_headers = {}

        for i in header.split('\r\n'):
            if i:
                name = i[:i.index(':')].lower().strip()
                value = i[i.index(':')+1:].lstrip()

                if res_headers.has_key(name):
                    res_headers[name] = res_headers[name] + ';\n' + value
                else:
                    res_headers[name] = value

        self.target.headers = res_headers

        return status, res_headers


    def __recv_loop__(self, sock, buff):

        recv_empty_count = 0

        while True:
            if self.opareq.cut:
                self.getCut()

            if self.opareq.pause:
                self.buffer(buff)
                self.getPause()
                break

            # if self.opareq.wait:
            #     self.getWait()

            last_len = len(buff)
            rest = self.progress.length - self.progress.go_inc
            try:
                if rest == 0:
                    if len(buff) != 0:
                        self.buffer(buff)
                    break
                elif rest < 4096:
                    buff += sock.recv(rest)
                else:
                    buff += sock.recv(4096)
            except:
                self.buffer(buff[:last_len])
                sock.shutdown(socket.SHUT_RDWR)
                msg = 'RecvTimeOut: ->rerun.'
                extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
                logger.warning(msg, extra=extra)
                # logger.warning(msg, extra={'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end)})
                # raise Exception('RecvTimeOut')
                return

            if len(buff) == last_len:
                recv_empty_count += 1
                if recv_empty_count >= RECV_EMPTY_RETRY_THRESHOLD:
                    sock.shutdown(socket.SHUT_RDWR)

                    if len(buff) != 0:
                        self.buffer(buff)
                        buff = ''

                    msg = 'RecvEmpty: ->rerun.'
                    extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
                    logger.warning(msg, extra=extra)
                    # logger.warning(msg, extra={'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end)})
                    # raise Exception('RecvEmpty')
                    return
                continue
            else:
                recv_empty_count = 0

            if len(buff) - last_len > rest:
                # raise Exception('RecvExceed')
                msg = 'RecvExceed: ->discard'
                extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
                logger.warning(msg, extra=extra)
                # logger.warning(msg, extra={'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end)})

            self.progress.go(len(buff) - last_len)

            if self.progress.go_inc >= self.progress.length:
                self.buffer(buff[:self.progress.length - self.progress.done_inc - len(self.buff)])
                self.close()
                break
            elif len(buff) >= 1024 * 1024:
                self.buffer(buff)
                buff = ''

    def selfCheck(self):
        if not self.progress.status.go_end:
            if not self.__thread__ or (self.__thread__ and not self.__thread__.isAlive()):
                if not self.progress.status.pauseflag:

                    self.run()

    def close(self):
        self.progress.globalprog.checkAllGoEnd()
        self.opareq.clear()
        msg = 'Close: '
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.info(msg, extra=extra)

    def pause(self):
        # with self.__opa_lock__:
        self.opareq.pause = True

    def getPause(self):
        # with self.__opa_lock__:
        self.progress.status.pause()
        self.opareq.pause = False


    def getWait(self):
        time.sleep(self.opareq.wait)

    def getSwitch(self):

        while True:
            next_available_urlid = self.urlid + 1
            if next_available_urlid >= len(self.progress.globalprog.handler.url.id_map):
                next_available_urlid = 0
            if self.progress.globalprog.handler.url.id_map[next_available_urlid]:
                break

        msg = 'UrlSwitch: %d->%d' % (self.urlid, next_available_urlid)
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.warning(msg, extra=extra)

        self.urlid = next_available_urlid
        self.__404_counter__ = 0

    def buffer(self, buff):
        with self.__buff__lock__:
            self.buff += buff
            self.progress.globalprog.checkBuffer(self.progress, len(buff))

    def isOnline(self):
        return self.__thread__ and self.__thread__.isAlive()

    def isEnd(self):
        return self.progress.status.go_end

    def cutRequest(self, Range):

        last_range = [self.progress.begin, self.progress.end]

        self.opareq.cut = [Range[0], Range[1]]

        msg = 'CutRequest: %010d-%010d' % (Range[0], Range[1])
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.info(msg, extra=extra)

        while True:
            if not self.opareq.cut or self.progress.status.go_end or self.progress.status.pauseflag:
                break
            time.sleep(0.1)

        return [self.progress.end, last_range[1]] if last_range[1] != self.progress.end else []

    def setNewRange(self, Range):
        self.progress.begin = Range[0]
        self.progress.end = Range[1]

    def getCut(self):
        while self.progress.begin + self.progress.go_inc >= self.opareq.cut[0]:
            self.opareq.cut[0] += self.progress.globalprog.handler.file.BLOCK_SIZE

        retrange = [] if self.opareq.cut[0] >= self.opareq.cut[1] else self.opareq.cut

        if retrange:
            with self.progress.globalprog.__progresses_lock__:
                self.progress.globalprog.progresses['%d-%d' % (self.progress.begin, retrange[0])] = self.progress
                del self.progress.globalprog.progresses['%d-%d' % (self.progress.begin, self.progress.end)]
                self.setNewRange([self.progress.begin, retrange[0]])

        msg = 'GetCut: %010d-%010d' % (self.opareq.cut[0], self.opareq.cut[1])
        extra = {'progress': '%-10d-%10d' % (self.progress.begin, self.progress.end), 'urlid': self.urlid}
        logger.info(msg, extra=extra)

        self.opareq.cut = []


