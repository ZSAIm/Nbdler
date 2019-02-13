
from progress import *
from TaskAssign import TaskAssign
import math, os
from lib.FileInfo import FileInfo
from lib.URLinfo import URLinfo
import socket,ssl
import random




class DLManager(object):
    """Manager All segments of file, [ThreadsList], [Each Downloading INFO]"""
    def __init__(self, url_infos=None, file_info=None, _data=None, **kwargs): # thread_count, block_size=None,

        self.servers = url_infos
        self.file = file_info
        self.GlobalProg = None
        if _data is not None:

            self.load(_data)
        elif url_infos is not None and file_info is not None:

            self.__getkwargs__(**kwargs)
            self._fix_count = 0
            self.GlobalProg = GlobalProgress(self)
            if len(self.servers) > self.thread_count:
                self.thread_count = len(self.servers)


        else:
            raise AttributeError


        self.task = TaskAssign(self.servers, self.GlobalProg, self)
        self.__write_lock = threading.Lock()
        self.auto_assign_thread = None

    def __getkwargs__(self, **kwargs):
        # print kwargs
        self.thread_count = kwargs.get('thread_count', 5)

        self._complete_validate = kwargs.get('complete_validate', True)

        self._fix_damage = kwargs.get('fix_damage', True)

        if kwargs.get('block_size') is None:
            if self.file.size <= 10*1024*1024:
                self.BLOCK_SIZE = 64 * 1024
            elif self.file.size <= 100*1024*1024:
                self.BLOCK_SIZE = 512 * 1024
            else:
                self.BLOCK_SIZE = 1024 * 1024  # 1MB
        else:
            self.BLOCK_SIZE = kwargs.get('block_size')



    def __release_buffer(self, buff, _progress):

        if _progress.GlobalProg.save is True:
            self.__buffer_to_file(buff, _progress, _progress.begin + _progress.increment)
        else:

            _progress.buffer_piece[_progress.begin + _progress.increment] = buff
            _progress.done(len(buff))

        _progress.increment += len(buff)

    def __buffer_to_file(self, buff, _progress, startPos):
        with self.__write_lock:
            with open(os.path.join(self.file.path, self.file.name + '.download'), 'rb+') as f:
                f.seek(startPos)
                f.write(buff)
                _progress.done(len(buff))


    def __build_download(self, server, _range):
        if server is None or None in _range:
            return
        if _range[0] == _range[1]:
            return
        _prog = self.GlobalProg.append_progress(server, _range)

        self.launch(_prog)

    def launch(self, _progress):
        with _progress.lock:
            if _progress.thread is None or _progress.thread.isAlive() is False:
                thd = threading.Thread(target=self.__getdata__, args=(_progress, _progress.server))
                _progress.thread = thd
                thd.start()

    def __retry__(self, _progress):
        if _progress.GlobalProg.save is True:
            _progress.retry_count += 1
            if _progress.retry_count >= 5:

                self.__switch_server(_progress)
                # print 'Switch Server, [%d, %d]' % (_progress.begin, _progress.end)
                _progress.retry_count = 0

        self.launch(_progress)

    def __switch_server(self, _progress):
        _progress.server = self.servers[(self.servers.index(_progress.server) + 1) % len(self.servers)]

    def __getdata__(self, _progress, server=None, MaxBuffSize=1024 * 1024 * 5):

        _progress.wait.acquire()

        if server is None:
            server = _progress.server

        _empty_count = 0

        ip = socket.gethostbyname(server.host)
        if server.https:
            sock = ssl.wrap_socket(socket.socket())
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.settimeout(5)
        try:
            sock.connect((ip, server.port))
            packet = 'GET %s HTTP/1.1\r\n' % server.path + \
                     'Host: {0}\r\n'.format(server.host) + \
                     'Connection: keep-alive\r\n' + \
                     'User-Agent: Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36\r\n' + \
                     'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8\r\n' + \
                     'Accept-Encoding: gzip, deflate, br\r\n' + \
                     'Accept-Language: zh-CN,zh;q=0.9\r\n' + \
                     'Range: bytes=%d-%d' % (_progress.begin + _progress.go_inc, _progress.end) + \
                     '\r\n\r\n'
            sock.send(packet)
            buff = sock.recv(1024)
        except:
            # CONNECT TIME OUT EXCEPTION.
            time.sleep(3)
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except:
                # print '[Errno 10057]'
                pass
            self.__retry__(_progress)
            return

        if not buff:
            sock.shutdown(socket.SHUT_RDWR)
            self.__retry__(_progress)
            return
        _one = len(buff)
        while '\r\n\r\n' not in buff:
            buff += sock.recv(512)
            if 'HTTP' not in buff:
                sock.shutdown(socket.SHUT_RDWR)
                time.sleep(2)
                self.__retry__(_progress)
                return

        _headers = buff[:(buff.index('\r\n\r\n'))]
        _header_top, _headers_dict = self.__plain_header_(_headers)

        if '302' in _header_top:
            server.reload_validate(_headers_dict['location'])
            sock.shutdown(socket.SHUT_RDWR)
            self.__retry__(_progress)
            return
        elif '404' in _header_top:
            sock.shutdown(socket.SHUT_RDWR)
            time.sleep(3)
            self.__retry__(_progress)
            return
        elif '206' not in _header_top:
            sock.shutdown(2)
            time.sleep(5)
            self.__retry__(_progress)
            return


        buff = buff[(buff.index('\r\n\r\n') + 4):]


        if _progress.length < len(buff):
            buff = buff[:_progress.length]

        _progress.go(len(buff))

        while True:

            if self.GlobalProg.pauseFlag is True:
                if buff:
                    self.__release_buffer(buff, _progress)
                return
            _progress.wait.acquire()
            _last_buff_len = len(buff)
            try:
                rest = _progress.length - _progress.go_inc
                if rest == 0:
                    # print '--release_buff - 1--'
                    if len(buff) != 0:
                        self.__release_buffer(buff, _progress)
                    break
                elif rest < 4096:
                    buff += sock.recv(rest)
                else:
                    buff += sock.recv(4096)

                if len(buff) == _last_buff_len:
                    _empty_count += 1
                    if _empty_count >= 5:
                        sock.shutdown(socket.SHUT_RDWR)
                        time.sleep(3)
                        if len(buff) != 0:
                            self.__release_buffer(buff, _progress)
                            buff = ''
                        self.__retry__(_progress)
                        return
                if len(buff) - _last_buff_len > rest:
                    buff = buff[:_last_buff_len + rest]

                _progress.go(len(buff) - _last_buff_len)
            except Exception as x:              # Time Out

                sock.shutdown(socket.SHUT_RDWR)
                buff = buff[:_last_buff_len]
                self.__release_buffer(buff, _progress)
                buff = ''
                if _progress.increment + len(buff) != _progress.length:
                    time.sleep(3)
                    self.__retry__(_progress)
                    return
                else:
                    break
            # WHEN THE BUFFER IS FULL, WRITE AND CLEAR.
            if len(buff) >= MaxBuffSize:
                self.__release_buffer(buff, _progress)
                buff = ''
            elif _progress.go_inc >= _progress.length:
                buff = buff[:_progress.length - _progress.increment]
                self.__release_buffer(buff, _progress)
                break
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except:
            pass




    def __plain_header_(self, headers):

        headers_dict = {}
        # print headers
        _header_ = headers.split('\r\n')
        _header_top = _header_[0].strip()

        for i in _header_[1:]:
            _name = i[:i.index(':')].lower().strip()
            _value = i[i.index(':') + 1:].lstrip()

            if headers_dict.has_key(_name) is True:
                headers_dict[_name] = headers_dict[_name] + ';\r\n\r\n' + _value
            else:
                headers_dict[_name] = _value

        return _header_top, headers_dict

    def getinsSpeed(self):
        return self.GlobalProg.getinsSpeed()

    def getavgSpeed(self):
        return self.GlobalProg.getavgSpeed()


    def getLeft(self):
        return self.GlobalProg.getLeft()


    def __auto_AssignTask_(self):
        while True:
            if self.GlobalProg.pauseFlag is True:

                break
            if self.isDone() is True:
                # print self.GlobalProg.queue.keys()
                # print self.GlobalProg.map
                if self.file.closed is False:
                    if self._complete_validate is True:
                        if self._fix_count != 0:
                            if self.complete_validate(fix=False) is False:
                                raise NotImplementedError('Failed to fix the file')
                            self.__close()
                        else:
                            if self.complete_validate(fix=self._fix_damage) is True:
                                self.__close()
                    else:
                        self.__close()
                    break
                else:
                    break

            else:
                if len(self.GlobalProg.queue) < len(self.servers):
                    _server, _range = self.task.assign()
                    # print _range
                    self.__build_download(_server, _range)
                else:
                    if self.thread_count > self.GlobalProg.getOnlineQuantity():
                        # if self.getLeft() / self.file.size < 0.5:
                        _server, _range = self.task.assign()
                        # print _range
                        self.__build_download(_server, _range)
                # lef = self.getLeft()
                # print lef, self.GlobalProg.getOnlineQuantity(), self.getinsSpeed()/1024

            time.sleep(1)

    def start(self):

        if self.isRuning():
            return
        if self.GlobalProg.endFlag is False:
            if self.GlobalProg.pauseFlag is False:
                self.file.make_file()
                self.auto_assign_thread = threading.Thread(target=self.__auto_AssignTask_)
                self.auto_assign_thread.start()
                # self.GlobalProg.launch_monitor()
            else:

                self.GlobalProg._continue()
                self.auto_assign_thread = threading.Thread(target=self.__auto_AssignTask_)
                self.auto_assign_thread.start()
                # self.GlobalProg.launch_monitor()

        self.GlobalProg.pauseFlag = False

    def isDone(self):
        """return weather is running or not"""
        return self.GlobalProg.endFlag

    def pause(self):

        if self.GlobalProg.endFlag is False:
            self.GlobalProg.pause()
            self.save()

    def isRuning(self):

        if self.GlobalProg.monitor is None:
            return False
        return self.GlobalProg.monitor.isAlive()


    def __close(self):
        _name = unicode(self.file.name)
        _path_name = unicode(os.path.join(self.file.path, self.file.name))

        _count = 0
        if not self.file.force:
            self.file.validate_name()
        else:
            if os.path.exists(os.path.join(self.file.path, self.file.name)) is True:
                os.remove(os.path.join(self.file.path, self.file.name))
        os.rename(os.path.join(self.file.path, _name) + u'.download',
                  os.path.join(self.file.path, self.file.name))
        self.file.close()
        if os.path.exists(os.path.join(self.file.path, self.file.name + u'.pkl')) is True:
            os.remove(os.path.join(self.file.path, self.file.name + u'.pkl'))


    def server_validate(self, sample_size=1024):
        # _box_prog = []


        _begin = random.randint(0, self.file.size - sample_size)

        _range = [_begin, _begin + sample_size]

        _Global_prog = GlobalProgress(self, False)

        for index, value in enumerate(self.servers):
            _prog = _Global_prog.append_progress(value, _range)

            self.launch(_prog)

        # _Global_prog.launch_monitor()

        while True:
            if _Global_prog.isDone() is True:
                break
            time.sleep(1)
        _box_buff = []

        for i in _Global_prog.queue.values():
            _box_buff.append(i.merge_buffer_piece())
        _one = _box_buff[0]
        for i in _box_buff[1:]:
            # print i
            if i != _one:
                return False
        return True




    def complete_validate(self, server_index=0, fix=False):

        _index = server_index
        _server = self.servers[_index]
        _Global_prog = GlobalProgress(self, False)
        for i in self.GlobalProg.queue.keys():
            _range = [int(j) for j in i.split('-')]
            if _range[1] - _range[0] > 1024:
                _range[0] = _range[1] - 1024
            _prog = _Global_prog.append_progress(_server, _range)
            self.launch(_prog)

        # _Global_prog.launch_monitor()

        while True:
            if _Global_prog.isDone() is True:
                break
            time.sleep(1)

        _damage = []

        with open(os.path.join(self.file.path, self.file.name + u'.download'), 'rb') as f:
            for i, j in _Global_prog.queue.items():
                _range = [int(k) for k in i.split('-')]
                f.seek(_range[0])
                _file_buf = f.read(_range[1] - _range[0])
                _buff = j.merge_buffer_piece()
                if _file_buf != _buff:
                    _damage.append(_range)


        if fix is False:

            if _damage:
                return False
            else:
                return True
        else:
            if not _damage:
                return True
            _damage_prog = []
            for i, j in enumerate(_damage):
                _prog = self.GlobalProg.get_parent_prog(j)
                _damage_prog.append(_prog)
            self.__fix__(_damage_prog)

    def __fix__(self, _damage_prog):
        self._fix_count += 1
        for i in _damage_prog:
            i.re_init()
            self.launch(i)

        self.auto_assign_thread = threading.Thread(target=self.__auto_AssignTask_)
        self.auto_assign_thread.start()

        # self.GlobalProg.launch_monitor()

    def dump(self):


        _dump_dict = dict(
            thread_count=self.thread_count,
            _complete_validate=self._complete_validate,
            _fix_damage=self._fix_damage,
            BLOCK_SIZE=self.BLOCK_SIZE,
            _fix_count=self._fix_count,
            # servers=self.servers,
            # file=self.file,
            GlobalProg=self.GlobalProg.dump()
        )


        return _dump_dict

    def save(self):
        import cPickle

        with open(os.path.join(self.file.path, self.file.name + u'.pkl'), 'wb') as f:
            cPickle.dump(self.servers, f, protocol=cPickle.HIGHEST_PROTOCOL)
            cPickle.dump(self.file, f, protocol=cPickle.HIGHEST_PROTOCOL)
            cPickle.dump(self.dump(), f, protocol=cPickle.HIGHEST_PROTOCOL)

    def load(self, _data):


        _type = [list, int, str, tuple, int, bool, float, long, dict, URLinfo, FileInfo]
        _instance = {}
        for i, j in _data.items():
            for k in _type:
                if isinstance(j, k) is True:
                    if isinstance(j, dict) is False:
                        break
                    elif hasattr(self, i) is False or getattr(self, i) is not None:
                        break
            else:
                if j is not None:
                    _instance[i] = j
                    continue
            setattr(self, i, j)

        self.GlobalProg = GlobalProgress(self)

        for i, j in _instance.items():
            getattr(self, i).load(j)
