

from nbdler.console.multi_client import MultiClientConsole
from nbdler.console.single_client import SingleClientConsole
from nbdler.struct.dump import HandlerDumpedData, FileDumpedData
from nbdler.file import File, FileInfo
from nbdler.client import build_initial_opener
from nbdler.struct.progress import Progress
from nbdler.exception import URLPoolEmpty, URLConnectFailed, \
    URLMaxRetriesExceeded, HandlerBusy, FileAlreadyExisted
from nbdler.request import Request
from nbdler.url.pool import Url
from nbdler.saver import Saver
from nbdler.utils.process_interface import make_method, make_class
from nbdler.struct.signal import ID_TASK_STOP, ID_TASK_EXCEPTION

from six.moves.queue import Queue
import os


DEFAULT_MAX_THREAD = 5
DEFAULT_BUFFSIZE = 10 * 1024 * 1024     # 20MB


def dlopen(source=None, *, maxthread=DEFAULT_MAX_THREAD, buffsize=DEFAULT_BUFFSIZE, child_process=False):
    if child_process:
        open_handler = HandlerForChildProcess
    else:
        open_handler = Handler

    return open_handler(source, max_thread=maxthread, buffsize=buffsize)


class Handler:
    """
        Attribute:
            source: A Source to make a Download Handler, should be a Download Request
                    or Handler datafile.

            max_thread: Specify the upper limit of running client at the same time.

            buffsize: Specify the max download buffer size keeping in memory.
    """

    __idle = True
    __new_file = True

    def __init__(self, source=None, *, max_thread=DEFAULT_MAX_THREAD, buffsize=DEFAULT_BUFFSIZE):

        self.url = Url()
        self._console = None

        self._max_thread = max_thread
        self._buffsize = buffsize
        self._saver = None
        self._inner_exc_signal = Queue()

        if source:
            self.open(source)

    def puturl(self, url, headers=None, cookie=None, *,
               proxy=None, max_conn=None, rangef=None, name=None):
        self.url.put(url=url, headers=headers, cookie=cookie, proxy=proxy,
                     max_conn=max_conn, rangef=rangef, name=name)

    def geturlinfo(self, k, default=None):
        srcwrapper = self.url.get(k, default)
        return srcwrapper.source.getinfo()

    def geturlinfo_all(self):
        retinfos = []
        for i, v in enumerate(self.url.get_all()):
            if v:
                retinfos.append(self.geturlinfo(i))

        return retinfos

    def open(self, source):
        """ Make a decision to open Download Handler from a request or a datafile. """
        if not self.is_idle():
            raise HandlerBusy('handler has already opened.')
        if type(source) is Request:
            self._open_request(source)
        elif type(source) is str:
            self._open_file(source)
        else:
            raise AssertionError()
        # return self

    def _open_file(self, source):
        """ Open Download Handler from a Download Handler datafile. """
        self.__new_file = False
        self.__idle = False
        dumped_data = Saver.json_loads(source)
        console = self._load_console(dumped_data)
        self._console = console
        self._saver = Saver(os.path.join(console.file.getpath(), console.file.getname() + '.nb'),
                            self.save_handler)
        self._console.install_saver(self._saver)
        self.__idle = True

    def _urlopen_console(self, dlrequest):
        self.url.open_request(dlrequest)
        url_id = 0
        srcwrap = self.url.get(url_id)
        srcurl = srcwrap.get()
        if not srcwrap:
            raise URLPoolEmpty()

        lprog = Progress((0,))

        callback = Queue()
        max_retried = dlrequest.max_retries
        while True:
            try:
                init_res = build_initial_opener(srcurl, lprog, callback)
            except URLConnectFailed:
                if self.is_idle():
                    return None
                if max_retried is None:
                    continue

                max_retried -= 1
                if max_retried <= 0:
                    raise URLMaxRetriesExceeded()
            else:
                break

        specify_path, specify_name = os.path.split(dlrequest.filepath)
        if not specify_name:
            specify_name = init_res.filename
        file = File(specify_path, specify_name, init_res.filesize)
        if os.path.exists(os.path.join(specify_path, specify_name)):
            raise FileAlreadyExisted()

        srcwrap.use()

        if init_res.unspecified_size:
            console_handler = SingleClientConsole
            blocksize = float('inf')
        else:
            console_handler = MultiClientConsole
            blocksize = dlrequest.block_size

        srcwrap.source.response(init_res.client.geturl(),
                                init_res.response.getheaders(),
                                init_res.response.getcode(),
                                init_res.filesize)
        if dlrequest.max_thread:
            self._max_thread = dlrequest.max_thread
        console = console_handler(file, self.url, self._buffsize,
                                  blocksize, self._max_thread, self._inner_exc_signal)
        console.insert(init_res.client, lprog)
        return console

    def _open_request(self, dlrequest):
        """ Open Download Handler from a Download Request. """
        self.__new_file = True
        self.__idle = False
        if not dlrequest.resume:
            console = self._urlopen_console(dlrequest)
            if console:
                self._saver = Saver(os.path.join(console.file.getpath(), console.file.getname() + '.nb'),
                                    self.save_handler)
                console.install_saver(self._saver)
                self._console = console

            self.__idle = True
        else:
            self._open_file(dlrequest.filepath + '.nb')
            for i in dlrequest:
                self.url.put(i.url, i.headers, i.cookie, proxy=i.proxy, max_conn=i.max_thread,
                             rangef=i.rangef, name=i.name)

    def getavgspeed(self):
        """ Return download average speed. """
        return self._console.getavgspeed()

    def getinstspeed(self):
        """ Return download instant speed.

        It gets instant speed from a sampling thread which
        sampling at INST_SPEED_REFRESH_FREQUENCY Hz, default 2 Hz.
        """
        return self._console.getinstspeed()

    def get_go_inc(self):
        """ Return the size of download bytes already. """
        return self._console.get_go_inc()

    def get_time_left(self):
        """ Return the time remaining to finish the task. (base on average speed)"""
        return self._console.get_time_left()

    def get_byte_left(self):
        """ Return the remaining size of downloading file. """
        return self._console.get_byte_left()

    def save_handler(self):
        """ Save Download Handler Data to the file name with a suffix of '.nb'. """
        self._saver.json_dumps(tuple(self._dump_data()))

    def _dump_data(self):
        """ Return a raw Download Handler data to serialize. """
        return HandlerDumpedData(url=tuple(self.url.dump_data()), file=tuple(self._console.file.dump_data()),
                                 console=tuple(self._console.dump_data()), maxthread=self._max_thread,
                                 buffsize=self._buffsize, blocksize=self._console.get_block_size())

    def _load_console(self, dumped_data):
        """ Load Download Handler from a json serializing Handler data. """
        data = HandlerDumpedData(*dumped_data)
        file_data = FileDumpedData(*data.file)

        file = File(file_data.path, file_data.name, file_data.size)
        self.url.load(data.url)
        self._max_thread = data.maxthread
        self._buffsize = data.buffsize

        if file.getsize():
            console_handler = MultiClientConsole
        else:
            console_handler = SingleClientConsole
        console = console_handler(file, self.url, data.buffsize,
                                  data.blocksize, data.maxthread,
                                  self._inner_exc_signal)
        console.load(data.console)

        return console

    def getfileinfo(self):
        """ Return a static copy of the download file's information. """
        return FileInfo(name=self._console.file.getname(),
                        path=self._console.file.getpath(),
                        size=self._console.file.getsize(),
                        block_size=self._console.get_block_size())

    def get_online_cnt(self):
        return self._console.get_online_cnt()

    def start(self):
        """ Start the download task. """
        if not self.is_idle():
            raise RuntimeError('cannot start an busy handler.')

        if self.is_running():
            raise RuntimeError('cannot start a started handler.')

        if not self.is_opened():
            raise RuntimeError('cannot start a unopened handler.')

        self.__idle = False

        if self._console.file.getsize() and self.__new_file:
            self._console.file.makefile()
            self.__new_file = False
            self.save_handler()

        self._console.prepare()
        self._console.run()

    def pause(self, block=True):
        """ Stop the running/opening download task. """
        if self._console:
            self._console.pause(block)
        self.__idle = True

    stop = pause

    def is_finished(self):
        """ Return True if download task is finished. """
        return self._console.is_finished()

    def is_running(self):
        """ Return True if download task is started. """
        return self._console is not None and self._console.runflag

    def get_online_counter(self):
        """ Return the number of running client threads. """
        return self._console.get_online_cnt()

    def close(self):
        """ Remove the finished download task's datafile. """
        if self.is_finished():
            datafile = os.path.join(self._console.file.getpath(), self._console.file.getname() + '.nb')
            if os.path.exists(datafile):
                os.unlink(datafile)
        else:
            raise RuntimeError("cannot close an unfinished task.")

    def join(self, timeout=None):
        """ Blocks the calling thread until the end of download or getting a download stop. """
        self._console.join(timeout)

    def trap(self):
        """ A inner-exception sensitive join(). """
        if self.is_idle():
            raise RuntimeError('cannot trap a download handler when it is\'t started')
        while True:
            signal = self._inner_exc_signal.get()
            if signal.id == ID_TASK_EXCEPTION:
                raise signal.content
            elif signal.id == ID_TASK_STOP:
                break

    def install_external_callback_queue(self, callback_handle):
        """ Install a callback signal queue.
         when task is finished or stopped, there is a signal
         sent to callback_handle (should be a type of CallbackHandle).
         """
        self._console.install_external_callback_queue(callback_handle)  

    def is_opened(self):
        return self._console is not None

    def is_idle(self):
        if self._console:
            return not self._console.runflag
        else:
            return self.__idle


@make_class(Handler)
class HandlerForChildProcess:

    @make_method
    def start(self):
        pass

    @make_method
    def pause(self, block=False):
        pass

    @make_method
    def open(self, source):
        pass

    @make_method
    def join(self, timeout=None):
        pass

    @make_method
    def trap(self):
        pass

    @make_method
    def install_external_callback_queue(self, callback_handle):
        pass

    @make_method
    def is_opened(self):
        pass

    @make_method
    def is_idle(self):
        pass

    @make_method
    def close(self):
        pass

    @make_method
    def get_online_counter(self):
        pass

    @make_method
    def is_running(self):
        pass

    @make_method
    def is_finished(self):
        pass

    @make_method
    def getfileinfo(self):
        pass

    @make_method
    def getavgspeed(self):
        pass

    @make_method
    def getinstspeed(self):
        pass

    @make_method
    def get_go_inc(self):
        pass

    @make_method
    def get_time_left(self):
        pass

    @make_method
    def get_byte_left(self):
        pass

    @make_method
    def save_handler(self):
        pass

    @make_method
    def puturl(self, url, headers=None, cookie=None, *,
               proxy=None, mxthread=None, rangef=None, name=None):
        pass

    @make_method
    def geturlinfo(self, k, default=None):
        pass

    @make_method
    def geturlinfo_all(self):
        pass

    @make_method
    def get_online_cnt(self):
        pass

    # @make_method
    # def rmurl(self):


