# -*- coding: UTF-8 -*-
import time


class progress(object):
    class status(object):
        def __init__(self):
            self.count_inc = 0
            self.lastTime = time.clock()
            self.startTime = time.clock()
            self.endTime = None
            self.endFlag = False

    def __init__(self, id, range, GlobalProgress):
        self.id = id
        self.begin = range[0]
        self.end = range[1]
        self.length = range[1] - range[0]
        self.endFlag = False
        self.pauseFlag = False
        # INCREMENT
        self.go_inc = 0
        self.done_inc = 0
        self.GlobalProgress = GlobalProgress
        self.status = progress.status()

    def done(self, byte_length):
        """count the sizes that had wrote to file."""
        self.done_inc += byte_length
        if self.done_inc == self.length:
            self.endFlag = True
            self.GlobalProgress._GlobalProg__close_file()
        elif self.done_inc > self.length:
            raise Exception('ProgressCountError: (done_inc, length, id) = ', self.done_inc, self.length, self.id)

    def go(self, byte_length):
        """count the sizes that had downloaded to buffer."""
        self.status.count_inc += byte_length

        self.go_inc += byte_length
        if self.go_inc == self.length:
            self.status.endFlag = True
            self.status.endTime = time.clock()

    def getLeft(self):
        return self.length - self.go_inc

    def getinsSpeed(self):

        if self.status.endFlag:
            ret = self.status.count_inc / (self.status.endTime - self.status.startTime)
        else:
            t = time.clock()
            ret = self.status.count_inc / (t - self.status.lastTime)
            self.status.lastTime = t
        self.status.count_inc = 0
        return ret

    def getaverSpeed(self):
        return self.go_inc / (time.clock() - self.status.startTime)




class GlobalProg(object):
    def __init__(self, ranges, fileObj, DLManagerObj):
        self.ranges = ranges
        self.DLManagerObj = DLManagerObj
        self.__fileObj = fileObj
        # self.WriteQueue = []

        self.progress = [progress(threadId, self.ranges[threadId], self) for threadId in range(len(ranges))]
        self.endFlag = False    # END last
        self.pauseFlag = False  # PAUSE first

    def __close_file(self):


        _TMP_Flag_0 = True  # tmp to check All endFlag if they are True
        _TMP_Flag_1 = True  # tmp to check All pauseFlag if they are True
        for progress_index in self.progress:
            if not progress_index.endFlag:
                _TMP_Flag_0 = False
            if not progress_index.pauseFlag and not progress_index.endFlag:
                _TMP_Flag_1 = False

        self.endFlag = _TMP_Flag_0

        if _TMP_Flag_0 or _TMP_Flag_1:

            self.__fileObj.flush()
            self.__fileObj.close()
        if _TMP_Flag_0:

            self.DLManagerObj._DLManager__close()


