# -*- coding: UTF-8 -*-
import time, sys, math, threading
from WaitLock import WaitLock



class Status:
    def __init__(self):
        self.startTime_go = time.clock()
        # print 'start', self.startTime_go
        self.endTime_go = None

        self.endFlag_go = False
        self.endFlag_done = False
        self.pauseFlag = False


class Piece:
    def __init__(self):
        self.go_inc = 0
        # self.startTime = time.clock()
        self.lastTime_go = time.clock()

class Progress:

    def __init__(self, server_index, server, range, GlobalProg):

        self.server_index = server_index
        self.GlobalProg = GlobalProg
        # self.initialize(server, range)
        # if GlobalProg.save is True:
        #     self.BLOCK_SIZE = GlobalProg.DLMobj.BLOCK_SIZE

        self.buffer_piece = {}
        # self.save = save

        self.server = server
        self.thread = None

        self.begin = range[0]
        self.end = range[1]
        self.length = range[1] - range[0]


        # INCREMENT
        self.go_inc = 0
        self.done_inc = 0
        self.increment = 0

        self.status = Status()
        self.piece = Piece()


        self.retry_count = 0

        self.wait = WaitLock(timeout=2)
        self.lock = threading.Lock()


    def done(self, byte_length):
        """count the sizes that had wrote to file."""
        self.done_inc += byte_length

        if self.done_inc == self.length:
            # print self.length
            self.status.endFlag_done = True

            for i in self.GlobalProg.queue.values():
                if i.status.endFlag_done is False:
                    break
            else:
                self.GlobalProg.endFlag = True
                self.GlobalProg.endTime = time.clock()

            # self.wait.release()
            # if self.GlobalProg is not None:
            # self.GlobalProg.close()


        # if self.GlobalProg.save is True:
        if self.GlobalProg.pauseFlag is True:
            self.status.pauseFlag = True
        if self.done_inc > self.length:
            # print
            # if self.GlobalProg.save is :
            print self.GlobalProg.file.name
            raise Exception('ProgressCountError: (done_inc, length, id) = ', self.done_inc, self.length)
        # if self.done_inc == self.length:




    def merge_buffer_piece(self):

        if len(self.buffer_piece) is 0:
            return None
        else:
            ret_buf = ''
            _part_up = sorted(self.buffer_piece.items(), key=lambda x: x[0])
            for i in _part_up:
                ret_buf += i[1]
            return ret_buf

    def go(self, byte_length):
        """count the sizes that had downloaded to buffer.
        """

        self.piece.go_inc += byte_length

        self.go_inc += byte_length

        if self.go_inc > self.length:
            print '-----', self.go_inc, self.length

        if self.GlobalProg.save is True:
            pos = int((self.begin + self.go_inc - byte_length)* 1.0 / self.GlobalProg.BLOCK_SIZE)
            _fil_len = int(math.ceil(byte_length * 1.0 / self.GlobalProg.BLOCK_SIZE))
            for i in range(_fil_len):
                self.GlobalProg.map[pos + i] = self.server_index

        if self.go_inc == self.length:
            self.wait.release()
            self.status.endFlag_go = True
            self.status.endTime_go = time.clock()
            # print 'end', self.status.endTime_go
            # print '****', self.GlobalProg.file.size, self.end
            if self.GlobalProg.save is True:
                if self.GlobalProg.file.size == self.end:
                    self.GlobalProg.map[-1] = self.server_index


    def clip_range_req(self, take_range):
        with self.wait as res:
            if res is False:
                return [None, None]

            if self.status.endFlag_go is True or take_range[0] < self.begin or take_range[1] > self.end:
                return [None, None]

            while self.begin + self.go_inc >= take_range[0]:
                take_range[0] += self.GlobalProg.BLOCK_SIZE
            if take_range[0] >= take_range[1]:
                return [None, None]
            new_range = [self.begin, take_range[0]]

            self.GlobalProg.clip_range([self.begin, self.end], new_range)
            self.set_range(new_range)

            put_range = take_range
            return put_range




    def set_range(self, _range):

        self.begin = _range[0]
        self.end = _range[1]
        self.length = _range[1] - _range[0]

    def getLeft(self):
        return self.length - self.go_inc


    def getinsSpeed(self):

        if self.status.endFlag_go is True:

            ret = self.piece.go_inc / (self.status.endTime_go - self.status.startTime_go)
            # only the first can get the last instant speed. or it will get 0
            self.piece.go_inc = 0
        else:
            t = time.clock()
            ret = self.piece.go_inc / (t - self.piece.lastTime_go)
            self.piece.lastTime_go = t

        self.piece.go_inc = 0

        return ret

    def getavgSpeed(self):
        if self.status.endFlag_go is False:
            # print 2, self.go_inc, (time.clock() - self.status.startTime_go), time.clock(), self.status.startTime_go
            return self.go_inc / (time.clock() - self.status.startTime_go)
        else:
            # e = self.go_inc / (self.status.endTime_go - self.status.startTime_go) / 1024
            # print 2, self.go_inc, (self.status.endTime_go - self.status.startTime_go), self.status.endTime_go ,self.status.startTime_go, e
            return self.go_inc / (self.status.endTime_go - self.status.startTime_go)


    def isGoEnd(self):
        return self.status.endFlag_go and self.getLeft() == 0

    def isDoneEnd(self):
        return self.status.endFlag_done

    def isAlive(self):
        if self.thread is not None:
            return self.thread.isAlive()
        else:
            return False
    def re_init(self):
        self.go_inc = 0
        self.increment = 0
        self.done_inc = 0

        self.status = Status()
        self.piece = Piece()

        self.GlobalProg.endFlag = False
        if self.GlobalProg.save is True:

            pos = int(self.end * 1.0 / self.GlobalProg.BLOCK_SIZE)
            _fil_len = int((self.length) * 1.0 / self.GlobalProg.BLOCK_SIZE) - 1
            for i in range(_fil_len):
                self.GlobalProg.map[pos - i - 1] = None


    def copy(self):
        _dump_prog = Progress(self.server_index, self.server, [self.begin, self.end], self.GlobalProg)

        _dump_prog.GlobalProg = None
        _dump_prog.buffer_piece = self.buffer_piece
        _dump_prog.lock = None
        _dump_prog.server = None

        # INCREMENT
        _dump_prog.go_inc = self.go_inc
        _dump_prog.done_inc = self.done_inc
        _dump_prog.increment = self.increment

        _dump_prog.status = self.status
        _dump_prog.piece = self.piece

        _dump_prog.retry_count = self.retry_count

        return _dump_prog

    def activate(self):
        self.lock = threading.Lock()
        self.server = self.GlobalProg.DLMobj.servers[self.server_index]
        pos = int((self.begin) * 1.0 / self.GlobalProg.BLOCK_SIZE)
        _fil_len = int(math.ceil(self.go_inc * 1.0 / self.GlobalProg.BLOCK_SIZE))
        for i in range(_fil_len):
            self.GlobalProg.map[pos + i] = self.server_index




class GlobalProgress:

    def __init__(self, DLMobj, save=True):

        self.DLMobj = DLMobj
        self.save = save
        if self.save is True:
            self.BLOCK_SIZE = self.DLMobj.BLOCK_SIZE
            self.file = self.DLMobj.file
            self.map = self.__make_map(self.file.size)
            self.size = None
        else:
            self.file = None
            self.map = None
            self.BLOCK_SIZE = None
            self.size = 0

        self.startTime = time.clock()
        self.endTime = None
        self.lastLeft = None
        self.lastTime = None
        self.lastSpeed = None

        self.queue = {}

        self.endFlag = False    # END last
        self.pauseFlag = False  # PAUSE first
        self.monitor = None

    def __make_map(self, size):

        return [None for i in range(int(math.ceil(size*1.0 / self.BLOCK_SIZE)))]



    def launch_monitor(self):
        self.monitor = threading.Thread(target=self.__monitor_thread)
        self.monitor.start()

    def __monitor_thread(self):
        # _retry_count = 0
        while True:
            if self.pauseFlag is True or self.endFlag is True:
                break
            # if len(self.queue) == 0:
            #     _retry_count += 1
            #     time.sleep(2)
            #     if _retry_count > 5:
            #         break
            #     continue
            # else:
            #     _retry_count = 0
            for i in self.queue.values():
                if i.isGoEnd() is False:
                    if i.thread is None or i.thread.isAlive() is False:
                        self.DLMobj.launch(i)
                    # break
            # else:
            #     for i in self.queue.values():
            #         if i.isDoneEnd() is False:
            #             i.go_inc = i.done_inc
            #             i.status.endFlag_go = False
            #             i.status.endTime_go = None
            #             self.DLMobj.launch(i)
            #             break
            #     else:
            #         self.endFlag = True
            #         break
            time.sleep(1)


    def append_progress(self, server, _range):
        self.endFlag = False
        self.endTime = None
        _prog = Progress(self.DLMobj.servers.index(server), server, _range, self)
        self.queue['%d-%d' % (_range[0], _range[1])] = _prog
        if self.monitor is None or self.monitor.isAlive() is False:
            self.launch_monitor()
        return _prog

    def getinsSpeed(self):
        """global instant speed"""

        if self.lastLeft is None:
            # print self.queue.keys()
            if len(self.queue) > 0:
                self.lastLeft = self.getLeft()
                self.lastTime = time.clock()
            return 0
        else:
            now_left = self.getLeft()
            # print now_left, self.lastLeft
            if self.endFlag is False:
                ret = (self.lastLeft - now_left) / (time.clock() - self.lastTime)

            else:
                ret = (self.lastLeft - now_left) / (self.endTime - self.startTime)

            self.lastLeft = now_left
            self.lastTime = time.clock()

            if ret < 0:
                return self.getavgSpeed()

            return ret



    def getavgSpeed(self):
        """global average speed"""

        if self.endFlag is False:
            if self.lastSpeed is None:
                return (self.file.size - self.getLeft()) / (time.clock() - self.startTime)
            else:
                return (self.lastSpeed + (self.file.size - self.getLeft()) / (time.clock() - self.startTime)) / 2
        else:
            if self.lastSpeed is None:
                return (self.file.size - self.getLeft()) / (self.endTime - self.startTime)
            else:
                return (self.lastSpeed + (self.file.size - self.getLeft()) / (self.endTime - self.startTime)) / 2




    def getLeft(self):
        """get global left of the downloading."""
        sum = 0
        for i in self.queue.values():
            sum += i.getLeft()
        return sum




    def getCompl_perc(self):
        return 1.0 - self.getLeft() *1.0 / self.file.size

    def getOnlineQuantity(self):
        _count = 0
        for i in self.queue.values():
            if i.isAlive() is True:
                _count += 1

        return _count

    def isDone(self):
        return self.endFlag


    def getQueueServerMes(self):
        _dict = {}
        _server = None

        for i in self.queue.values():
            if _dict.has_key(i.server) is True:
                _dict[i.server]['COUNT'] += 1
                _dict[i.server]['SPEED'] += i.getavgSpeed()
            else:
                _dict[i.server] = {'SPEED': i.getavgSpeed(), 'COUNT': 1}

        return _dict

    def get_parent_prog(self, next_range):
        if len(self.queue) is 0:
            return None
        for i in self.queue.values():
            if next_range[0] >= i.begin and next_range[1] <= i.end:
                return i


        return None


    def clip_range(self, old_range, new_range):

        prog = self.queue['%d-%d' % (old_range[0], old_range[1])]
        # print prog
        del self.queue['%d-%d' % (old_range[0], old_range[1])]
        self.queue['%d-%d' % (new_range[0], new_range[1])] = prog

    def pause(self):

        self.pauseFlag = True
        while True:
            for i in self.queue.values():
                if i.status.pauseFlag is False and \
                        i.status.endFlag_done is False and \
                        i.thread is not None and \
                        i.thread.isAlive() is True:
                    break
            else:
                break
            time.sleep(0.2)


    def _continue(self):
        self.pauseFlag = False
        for i in self.queue.values():
            i.status.pauseFlag = False
            if i.isGoEnd() is False:
                self.DLMobj.launch(i)


    def dump(self):

        # print 'Global dump'
        _copy_queue = {}
        for i, j in self.queue.items():
            _copy_queue[i] = j.copy()
        if self.lastSpeed is None:
            self.lastSpeed = self.getavgSpeed()
        else:
            self.lastSpeed = (self.getavgSpeed() + self.lastSpeed) / 2

        _dump_dict = dict(
            queue=_copy_queue,
            endFlag=self.endFlag,
            pauseFlag=self.pauseFlag,
            startTime=self.startTime,
            endTime=self.endTime,
            lastLeft=self.lastLeft,
            lastSpeed=self.lastSpeed
        )

        return _dump_dict

    def activate(self):
        self.BLOCK_SIZE = self.DLMobj.BLOCK_SIZE
        self.file = self.DLMobj.file
        self.map = self.__make_map(self.file.size)
        self.lastTime = None
        self.startTime = time.clock()



    def load(self, _data):
        self.activate()

        for i, j in _data.items():
            setattr(self, i, j)

        for i in self.queue.values():
            i.GlobalProg = self
            i.activate()