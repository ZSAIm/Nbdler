import threading

class DownloadThread(threading.Thread):

    def __init__(self, foo, threadId, range):
        threading.Thread.__init__(self)
        self.threadId = threadId
        self.range = range

        self.foo = foo

    def run(self):

        self.foo(self.range[0], self.range[1], self.threadId)


class WriteThread(threading.Thread):
    def __init__(self, fileObj, buff, startPos, lock, progress):
        threading.Thread.__init__(self)
        self.buff = buff
        self.startPos = startPos
        self.fileObj = fileObj
        self.lock = lock
        self.progress = progress


    def run(self):

        self.lock.acquire()
        self.fileObj.seek(self.startPos)
        self.fileObj.write(self.buff)
        self.progress.done(len(self.buff))

        if self.progress.GlobalProgress.pauseFlag:

            self.progress.pauseFlag = True
            self.progress.GlobalProgress._GlobalProg__close_file()

        self.lock.release()

