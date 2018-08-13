
from progress import *
from DLThread import *
import math, os
import socket,ssl

class DLManager(object):
    """Manager All segments of file, [ThreadsList], [Each Downloading INFO]"""
    def __init__(self, URLinfo, fileInfo, ThreadCount):
        self.url = URLinfo
        self.file = fileInfo
        self.ThreadCount = ThreadCount
        # self.fileObj = None
        self.ranges = self.__fileRanges(self.file.size, self.ThreadCount)
        self.threads = [None for i in range(ThreadCount)]

        self.GlobalProg = None
        self.__queueLock = threading.Lock()

        self.pauseFlag = False


    def __releasebuff(self, buff, startPos, progress):

        thd = WriteThread(self.file.object, buff, startPos, self.__queueLock, progress)

        thd.start()

    def __downloading(self,threadId, range):

        if range[0] == range[1]:
            return
        self.GlobalProg.progress[threadId] = progress(threadId, range, self.GlobalProg)

        thd = DownloadThread(self.__getdata__, threadId, range)
        self.threads[threadId] = thd
        thd.start()

    def __getdata__(self, startPos, endPos, threadId, MaxBufflen=1024 * 1024 * 5):
        # RECORD DOWNLOAD PROGRESS INFORMATION.
        runinfo = self.GlobalProg.progress[threadId]

        self.ip = socket.gethostbyname(self.url.host)
        if self.url.https:
            sock = ssl.wrap_socket(socket.socket())
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.settimeout(5)

        try:
            sock.connect((self.ip, self.url.port))

            packet = 'GET {0} HTTP/1.1\r\n'.format(self.url.path) + \
                     'Host: {0}\r\n'.format(self.url.host) + \
                     'Connection: keep-alive\r\n' + \
                     'User-Agent: Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36\r\n' + \
                     'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8\r\n' + \
                     'Accept-Encoding: gzip, deflate, br\r\n' + \
                     'Accept-Language: zh-CN,zh;q=0.9\r\n' + \
                     'Range: bytes={0}-{1}'.format(startPos, endPos) + \
                     '\r\n\r\n'

            sock.send(packet)

            buff = sock.recv(1024)
        except:
            # CONNECT TIME OUT EXCEPTION.
            time.sleep(1)
            self.__downloading(threadId, [startPos, endPos])
            return

        buff = buff[(buff.index('\r\n\r\n') + 4):]
        increment = 0
        runinfo.go(len(buff))
        # print len(buff)
        while True:
            if self.pauseFlag:
                if buff:
                    self.__releasebuff(buff, startPos + increment, runinfo)
                self.ranges[threadId] = [startPos + increment + len(buff), endPos]
                break

            try:
                rest = endPos - startPos - increment - len(buff)
                if rest == 0:
                    self.__releasebuff(buff, startPos + increment, runinfo)

                    break
                elif rest < 4096:
                    buff += sock.recv(rest)
                    runinfo.go(rest)

                else:
                    one = len(buff)
                    buff += sock.recv(4096)

                    runinfo.go(len(buff) - one)


            except Exception as x:
                # print "TimeOut", x
                # TIME OUT , WRITE THE BUFF, OR NOT, THEN RESTART.
                # WRITE IT DOWN IS NOT NECESSARY.
                self.__releasebuff(buff, startPos + increment, runinfo)
                if increment + len(buff) >= endPos - startPos:
                    # END OF DOWNLOAD.
                    pass
                else:
                    # print 'need to make a new thread to download the rest.'
                    sock.close()
                    time.sleep(1)
                    # REDOWNLOAD THIS SEGMENT.
                    self.__downloading(threadId, [startPos + increment + len(buff), endPos])
                break

            if not buff:
                # SOMETHING PROBLEM IN sock.recv() SO THAT STUCK IN LOOP. HAVE TO RESTART THIS PART.
                # OF COURSE ! MAKE A NEW THREAD.
                # print 'stuck in while'
                self.__downloading(threadId, [startPos, endPos])

                break

            # WHEN THE BUFFER IS FULL, WRITE AND CLEAR.
            if len(buff) >= MaxBufflen:

                self.__releasebuff(buff, startPos + increment, runinfo)
                increment += len(buff)
                buff = ''
                if len(buff) + increment >= self.file.size:
                    break

        sock.close()

    def getinsSpeed(self):
        """global instant speed"""
        sumspeed = 0
        for i in self.GlobalProg.progress:
            sumspeed += i.getinsSpeed()
        return sumspeed

    def getaverSpeed(self):
        """global average speed"""
        sumspeed = 0
        for i in self.GlobalProg.progress:
            sumspeed += i.getaverSpeed()
        return sumspeed
    def getLeft(self):
        """get global left of the downloading."""
        sum = 0
        for i in self.GlobalProg.progress:
            sum += i.getLeft()
        return sum
    def __fileRanges(self, size, segNum):

        _range = []
        unit = int(math.ceil(float(size) / segNum))
        for i in range(segNum):
            if (i + 1) * unit > size:
                _range.append([i * unit, size])
            else:
                _range.append([i * unit, (i + 1) * unit])

        return _range

    def start(self):

        if self.__isRuning():
            return
        if not self.pauseFlag:
            self.file.make_file()
            self.file.object = open((self.file.path + self.file.name + '.download').decode('UTF-8'), 'wb')
            self.GlobalProg = GlobalProg(self.ranges, self.file.object, self)

            for index in range(self.ThreadCount):
                self.__downloading(index, self.ranges[index])


        else:
            self.file.object = open((self.file.path + self.file.name + '.download').decode('UTF-8'), 'rb+')
            self.GlobalProg = GlobalProg(self.ranges, self.file.object, self)
            for index in range(self.ThreadCount):
                self.__downloading(index, self.ranges[index])

        self.pauseFlag = False

    def isAlive(self):
        """return weather is running or not"""
        return not self.GlobalProg.endFlag

    def pause(self):
        self.pauseFlag = True
        self.GlobalProg.pauseFlag = True

    def __isRuning(self):
        if not self.file.object:
            return False

        if not self.file.object.closed:
            return True
        else:
            return False

    def __close(self):

        _name = (self.file.path + self.file.name).decode('utf-8')
        _count = 0

        while True:
            if _count:
                try:
                    dot_index = _name.rindex('.')
                    if os.path.exists(_name[:dot_index] +
                                  u'(' + str(_count).decode('unicode-escape') + u')' +
                                  _name[dot_index:]):
                        _count += 1
                        continue

                    os.rename(_name + u'.download',
                              _name[:dot_index] +
                              u'(' + str(_count).decode('unicode-escape') + u')' +
                              _name[dot_index:])
                    break
                except:
                    os.rename(_name + u'.download', _name + u'(' + str(_count).decode('unicode-escape') + u')')
                    break
            else:
                if not os.path.exists(_name):
                    os.rename(_name + u'.download', _name)
                    break
                else:
                    _count += 1
