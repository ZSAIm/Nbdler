
from __future__ import division
import gc
from math import ceil
from time import sleep

from six.moves.queue import Queue
from nbdler.struct.block import Block, GridCell
from nbdler.misc.thread import ThreadCollector, Lock
from nbdler.struct.progress import Progress
from nbdler.client import build_client
from nbdler.console.abstract_console import AbstractConsole
from nbdler.misc.signal import SIGNAL_TASK_STOP, SIGNAL_TASK_SLICE, ID_TASK_BUFF, \
    ID_TASK_SLICE, ID_TASK_STOP, SIGNAL_TASK_FINISH, ID_THREAD_END, ID_TASK_FINISH, ID_TASK_PAUSE, SIGNAL_TASK_PAUSE, \
    ID_GAIERROR, ID_CRASH, ID_TIMEOUT, ID_UNKNOWN, ID_URL_STATUS, ID_NORMAL, SIGNAL_EXCEPTION, \
    SIGNAL_SWITCH, SIGNAL_WAIT, Signal, ID_CALLBACK_END, SIGNAL_CALLBACK_END

from nbdler.exception import URLUnknownError, URLTimeout, URLCrash, \
    NetworkDisconnected
from nbdler.struct.dump import BlockDumpedData, ProgressDumpedData, ConsoleDumpedData
from nbdler.struct.time_speed import AccumulatedTime, InstSpeedMaker

GROUP_CLIENT = 'Console.client'
GROUP_CONTROLLER = 'Console.controller'
GROUP_RELEASE = 'Console.release'
GROUP_SLICER = 'Console.slice'
GROUP_INSTSPEED = 'Console.inst_capture'

INST_SPEED_REFRESH_FREQUENCY = 3    # 3 Hz


class MultiClientConsole(AbstractConsole):
    def __init__(self, file, url, buffsize, block_size, maxthread, exception_callback):
        self._blocks = []
        self._block_size = block_size

        self._mxthread = maxthread
        self._buffsize = buffsize

        self.__total = int(ceil(file.getsize() / self._block_size))

        self.file = file
        self._url = url

        self._tpm = ThreadCollector()

        self._client_callback_queue = Queue()
        self.__exception_signal = exception_callback

        self.__buff_counter = 0

        self._buff_lock = Lock()
        self.runflag = False

        self._acum_time = AccumulatedTime(0)
        self._inst_maker = InstSpeedMaker()
        self._saver = None

        self._external_callback_queue = None

    def insert(self, content, progress, abs_grid=None, rel_grid=None):
        block = Block(content, progress, self._block_size, abs_grid=abs_grid, rel_grid=rel_grid)

        for i, v in enumerate(self._blocks):
            if v.begin > block.begin:
                self._blocks.insert(i, block)
                break
        else:
            self._blocks.append(block)

        return block

    def locate(self, block_index):
        c = 0
        for i in self._blocks:
            c += i.length
            if block_index < c:
                return i

    def getfullmap(self):
        for b in self._blocks:
            for i in b.abs_grid:
                yield i

    def __iter__(self):
        return self.getfullmap()

    def __getitem__(self, item):
        if type(item) is not int:
            raise ValueError()

        if item >= self.__total:
            raise IndexError()

        c = 0
        for i in self._blocks:
            c += i.length
            if item < c:
                return i.grid[item - c + i.length]

        raise IndexError()

    def prepare(self):

        self.file.open()

    def run(self):
        """ Run download task. """
        if not self._blocks:
            raise RuntimeError('cannot find any download block in the console.')
        self.runflag = True
        self._acum_time.start()
        self._inst_maker.start(self.getincbyte())
        for block in self._blocks:
            block.clear_signal()
            self._tpm.put(block.handler, GROUP_CLIENT, args=(self._client_callback_queue,),
                          owner=block)
        self._tpm.start_group(GROUP_CLIENT)

        self._tpm.put(self._client_callback_handle_thread, GROUP_CONTROLLER).start()
        self._tpm.put(self._inst_speed_capture_thread, GROUP_INSTSPEED).start()

        if self._mxthread > self.get_running_counter():
            self._make_slice_request()

    def getblocksize(self):
        """ Return console's unit block size. """
        return self._block_size

    def getincbyte(self):
        """ Return byte size downloaded. """
        inc = 0
        for v in self._blocks:
            inc += v.getincbyte()
        return inc

    def pause(self, block=True, timeout=None):
        """ Pause downloading. block until finish pausing only when block == True. """
        self.runflag = False
        self._client_callback_queue.put_nowait(SIGNAL_TASK_PAUSE())
        if block:
            self._tpm.wait(GROUP_CONTROLLER, timeout=timeout)

    stop = pause

    def getavgspeed(self):
        """ Return average download speed. """
        return self.getincbyte() / (self._acum_time.getinctime() or float('inf'))

    def getinstspeed(self):
        """ Return instant download speed. """
        return self._inst_maker.getspeed()

    def _inst_speed_capture_thread(self):
        while self.runflag:
            self._inst_maker.capture(self.getincbyte())
            freq = INST_SPEED_REFRESH_FREQUENCY
            if freq > 0:
                sleep(1 / freq)
            else:
                break

    def get_remain_time(self):
        """ Return remaining time to finish the download task. """
        speed = self.getavgspeed()
        return self.get_remain_byte() / speed if speed else float('inf')

    def get_remain_byte(self):
        """ Return remaining byte to finish the download task. """
        acum_byte = 0
        for v in self._blocks:
            acum_byte += v.get_remain_byte()

        return acum_byte

    def get_online_counter(self):
        """ Return the number of running client-threads. """
        return len(self._tpm.get_group(GROUP_CLIENT))

    def get_running_counter(self):
        """ Return the number of running clients. """
        acum = 0
        for v in self._blocks:
            if not v.is_finish_go():
                acum += 1
        return acum

    def is_finish_go(self):
        """ Return True if download finished (finish writing to file is not necessary). """
        for v in self._blocks:
            if not v.is_finish_go():
                return False
        return self._check_complete()

    def is_finish(self):
        """ Return True if download task finished. """
        for v in self._blocks:
            if not v.is_finish():
                return False
        return self._check_complete()

    def _client_callback_handle_thread(self):
        """ A thread handler about callback signal. """
        while True:
            signal = self._client_callback_queue.get()
            if signal.id == ID_TASK_BUFF:
                self.__buffer_signal_handler(signal.content)
            elif signal.id == ID_TASK_SLICE:
                self.__slice_feedback_handler(signal.content)
            elif signal.id == ID_THREAD_END:
                self.__client_thread_end_handler(signal.content)
            elif signal.id == ID_URL_STATUS:
                self.__url_status_handler(signal.content)
            elif signal.id == ID_TASK_PAUSE:
                self.__pause_handler()
            elif signal.id == ID_TASK_FINISH:
                self.__finish_handler()
            elif signal.id == ID_TASK_STOP:
                self.__stop_handler()
            elif signal.id == ID_CALLBACK_END:
                break

            self._client_callback_queue.task_done()

        self._client_callback_queue.task_done()

    def _buffer_release_thread(self):
        """ A thread handling writing buffer to file. """
        with self._buff_lock:
            for v in self._blocks:
                v.release_buffer(self.file)
            if self._saver:
                self._saver.dump()
        gc.collect()

    def _find_block_from_client(self, client, defalut=None):
        """ Find the block"""
        for v in self._blocks:
            if client in v:
                return v
        return defalut

    def _make_slice_request(self):
        """ Make a slice request. """
        maxblock = sorted(self._blocks, key=lambda i: i.margin, reverse=True)[0]
        margin_len = maxblock.margin
        put_begin = maxblock.begin + (maxblock.length - margin_len) + int(ceil(margin_len / 2))
        put_end = maxblock.end
        signal = SIGNAL_TASK_SLICE((put_begin * self._block_size, put_end * self._block_size))
        maxblock.send_signal(signal)

    def _check_complete(self):
        """ Return True if total blocks length completely match. """
        acum_len = 0
        for v in self._blocks:
            v.calibration()
            acum_len += v.length
        return self.__total == acum_len

    def __client_thread_end_handler(self, client):
        """ Callback handler when signal.id == ID_THREAD_END:
                <CLIENT THREAD END OF LIFE>
        """
        block = self._find_block_from_client(client)
        if self.runflag:
            if block.is_finish_go():
                if self._mxthread > self.get_running_counter():
                    self._make_slice_request()
                srcwrapper = self._url.getwrapper(block.getsource())
                srcwrapper.disuse()

            else:
                self._tpm.put(client.run, GROUP_CLIENT, args=(self._client_callback_queue,),
                              owner=block).start()

        if self.is_finish_go():
            self._buffer_release_thread()
            self._finish_task()

    def _finish_task(self):
        self._client_callback_queue.put_nowait(SIGNAL_TASK_FINISH())

        if self._external_callback_queue:
            self._external_callback_queue.queue.put_nowait(
                SIGNAL_TASK_FINISH(
                    Signal(id=self._external_callback_queue.id)
                )
            )

    def _failed_task(self, exception):
        self.__exception_signal.put_nowait(SIGNAL_EXCEPTION(exception))

        if self._external_callback_queue:
            self._external_callback_queue.queue.put_nowait(
                SIGNAL_EXCEPTION(
                    Signal(id=self._external_callback_queue.id,
                           content=exception)
                )
            )

    def __stop_handler(self):
        self.file.close()
        self._acum_time.stop()
        self._inst_maker.stop()
        self.runflag = False
        self._client_callback_queue.put_nowait(SIGNAL_CALLBACK_END())
        self.__exception_signal.put_nowait(SIGNAL_TASK_STOP())
        if self._external_callback_queue:
            self._external_callback_queue.queue.put_nowait(
                SIGNAL_TASK_STOP(Signal(id=self._external_callback_queue.id))
            )

    def __finish_handler(self):
        self._client_callback_queue.put_nowait(SIGNAL_TASK_STOP())

    def __slice_feedback_handler(self, slice):
        """ Callback handler when signal.id == ID_SLICE:
                <SLICE FEEDBACK>
        """
        if slice.range:
            srcwrapper = self._url.get_min_avl_used()
            prog = Progress(slice.range)
            client = slice.client(srcwrapper.get(), prog)
            block = self.insert(client, prog)
            srcwrapper.use()
            if self.runflag:
                self._tpm.put(block.handler, GROUP_CLIENT,
                              args=(self._client_callback_queue,),
                              owner=block).start()

        if self._mxthread > self.get_running_counter():
            self._make_slice_request()

    def __buffer_signal_handler(self, byte):
        """ Callback handler when signal.id == ID_BUFF:
                <BUFFER COUNTER>
        """
        self._url.clear_counter()
        self.__buff_counter += byte
        if self.__buff_counter >= self._buffsize:
            self.__buff_counter = 0
            self._tpm.put(self._buffer_release_thread, GROUP_RELEASE).start()

    def __url_status_handler(self, url_status):
        """ Callback handler when signal.id == ID_URL_STATUS:
                <URL SIGNAL>
        """
        client = url_status.content.client
        exception = url_status.content.exception
        source = client.getsource()
        srcwrapper = self._url.getwrapper(source)
        block = self._find_block_from_client(client)
        try:
            if url_status.id == ID_NORMAL:
                srcwrapper.clear_counter()
            elif url_status.id == ID_TIMEOUT:
                srcwrapper.timeout()
            elif url_status.id == ID_CRASH:
                srcwrapper.crash()
            elif url_status.id == ID_UNKNOWN:
                srcwrapper.unknown()
            elif url_status.id == ID_GAIERROR:
                srcwrapper.network_down()
        except (URLCrash, URLTimeout, URLUnknownError, NetworkDisconnected) as e:
            try:
                nextwrapper = self._url.get_min_avl_used()
            except ValueError:
                if self._url.is_all_crashed():
                    self._failed_task(e)
                else:
                    block.send_signal(SIGNAL_WAIT(1))
            else:
                block.send_signal(SIGNAL_SWITCH(nextwrapper.get()))
                nextwrapper.use()

    def __pause_handler(self):
        """ Callback handler when signal.id == ID_PAUSE:
                <PAUSE SIGNAL>
        """
        for thread in self._tpm.get_group(GROUP_CLIENT):
            thread.owner.send_signal(SIGNAL_TASK_PAUSE())

        self._tpm.wait(GROUP_SLICER)
        self._tpm.wait(GROUP_CLIENT)
        self._tpm.wait(GROUP_RELEASE)

        self._buffer_release_thread()
        self._client_callback_queue.put_nowait(SIGNAL_TASK_STOP())

        if self._external_callback_queue:
            self._external_callback_queue.queue.put_nowait(
                SIGNAL_TASK_PAUSE(
                    Signal(id=self._external_callback_queue.id)
                )
            )

    def dump_data(self):
        return ConsoleDumpedData(block_data=list([tuple(b.dump_data()) for b in self._blocks]),
                                 acum_time=self._acum_time.getinctime())

    def load(self, dumped_data):
        data = ConsoleDumpedData(*dumped_data)
        self._acum_time = AccumulatedTime(data.acum_time)

        for i in data.block_data:
            b = BlockDumpedData(*i)
            p = ProgressDumpedData(*b.progress)
            prog = Progress(p.range, p.go_inc, p.done_inc)
            srcwrapper = self._url.get(b.url_id)
            source = srcwrapper.get()
            client = build_client(source, prog)
            srcwrapper.use()
            self.insert(client, prog,
                        rel_grid=list([GridCell(*i) for i in b.rel_grid]))

    def install_saver(self, saver):
        self._saver = saver

    def install_external_callback_queue(self, signal_queue):
        self._external_callback_queue = signal_queue

    def join(self, timeout=None):
        self._tpm.join(timeout)

