

import gc
from time import sleep

from nbdler.utils.thread import ThreadCollector, Lock
from nbdler.struct.block import Block
from six.moves.queue import Queue
from nbdler.struct.dump import BlockDumpedData, ConsoleDumpedData
from nbdler.struct.time_speed import AccumulatedTime, InstSpeedMaker
from nbdler.struct.progress import Progress
from nbdler.client import build_client
from nbdler.console.abstract_console import AbstractConsole
from nbdler.struct.signal import Signal, SIGNAL_TASK_STOP, ID_TASK_BUFF, SIGNAL_CALLBACK_END, \
    ID_TASK_STOP, SIGNAL_TASK_FINISH, ID_THREAD_END, ID_TASK_FINISH, ID_TASK_PAUSE, SIGNAL_TASK_PAUSE, \
    ID_GAIERROR, ID_CRASH, ID_TIMEOUT, ID_UNKNOWN, ID_URL_STATUS, ID_NORMAL, SIGNAL_EXCEPTION

from nbdler.exception import URLUnknownError, URLTimeout, URLCrash, NetworkDisconnected


GROUP_CONTROLLER = 'Console.controller'
GROUP_CLIENT = 'Console.client'
GROUP_RELEASE = 'Console.release'
GROUP_SLICER = 'Console.slice'
GROUP_INSTSPEED = 'Console.inst_capture'


INST_SPEED_REFRESH_FREQUENCY = 2    # 2 Hz


class SingleClientConsole(AbstractConsole):
    def __init__(self, file, url, buffsize, block_size, maxthread, exception_callback):
        self._block_size = block_size

        self._buffsize = buffsize
        self._block = None
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

        self.__callback_queue = None

    def insert(self, client, progress):
        if self._block:
            raise RuntimeError('cannot insert more than one block into single client console.')
        self._block = Block(client, progress, self._block_size)

    def prepare(self):
        self.file.open()

    def run(self):
        self.runflag = True
        self._block.clear()
        self._acum_time.start()
        self._inst_maker.start(self.get_go_inc())
        self._tpm.put(self._block.handler, GROUP_CLIENT,
                      args=(self._client_callback_queue,), owner=self._block).start()
        self._tpm.put(self._client_callback_handle_thread, GROUP_CONTROLLER).start()
        self._tpm.put(self._inst_speed_capture_thread, GROUP_INSTSPEED).start()

    def __stop_handler(self):
        self.file.close()
        self._acum_time.stop()
        self._inst_maker.stop()
        self.runflag = False
        self._client_callback_queue.put_nowait(SIGNAL_CALLBACK_END())
        self.__exception_signal.put_nowait(SIGNAL_TASK_STOP())
        if self.__callback_queue:
            self.__callback_queue.queue.put_nowait(
                SIGNAL_TASK_STOP(Signal(id=self.__callback_queue.id))
            )

    def pause(self, block=True, timeout=None):
        self.runflag = False
        self._client_callback_queue.put_nowait(SIGNAL_TASK_PAUSE())
        if block:
            self._tpm.wait(GROUP_CONTROLLER, timeout=timeout)

    def is_finish_go(self):
        return self._block.is_go_finished()

    def get_byte_left(self):
        if self.is_finish_go():
            return 0
        else:
            return float('inf')

    def get_time_left(self):
        if self.is_finish_go():
            return 0
        else:
            return float('inf')

    def getavgspeed(self):
        return self.get_go_inc() / (self._acum_time.getinctime() or float('inf'))

    def get_go_inc(self):
        return self._block.get_go_inc()

    def getinstspeed(self):
        return self._inst_maker.getspeed()

    def _inst_speed_capture_thread(self):
        while self.runflag:
            self._inst_maker.capture(self.get_go_inc())
            freq = INST_SPEED_REFRESH_FREQUENCY
            if freq > 0:
                sleep(1 / freq)
            else:
                break

    def _client_callback_handle_thread(self):
        while True:
            signal = self._client_callback_queue.get()
            if signal.id == ID_TASK_BUFF:
                self.__buffer_signal_handler(signal.content)
            elif signal.id == ID_THREAD_END:
                self.__client_thread_end_handler(signal.content)
            elif signal.id == ID_URL_STATUS:
                self.__url_status_handler(signal.content)
            elif signal.id == ID_TASK_PAUSE:
                self.__pause_handler()
            elif signal.id == ID_TASK_FINISH:
                self.__stop_handler()
            elif signal.id == ID_TASK_STOP:
                break

            self._client_callback_queue.task_done()

        self._client_callback_queue.task_done()

    def is_finished(self):
        return self._block.is_finished()

    def _finish_task(self):
        self._client_callback_queue.put_nowait(SIGNAL_TASK_FINISH())

        if self.__callback_queue:
            self.__callback_queue.queue.put_nowait(
                SIGNAL_TASK_FINISH(
                    Signal(id=self.__callback_queue.id)
                )
            )

    def __pause_handler(self):
        """ Callback handler when signal.id == ID_PAUSE:
                <PAUSE SIGNAL>
        """
        for thread in self._tpm.get_group(GROUP_CLIENT):
            thread.owner.send_signal(SIGNAL_TASK_PAUSE())

        self._tpm.wait(GROUP_CLIENT)
        self._tpm.wait(GROUP_RELEASE)

        self._buffer_release_thread()
        self._client_callback_queue.put_nowait(SIGNAL_TASK_STOP())

        if self.__callback_queue:
            self.__callback_queue.queue.put_nowait(
                SIGNAL_TASK_PAUSE(
                    Signal(id=self.__callback_queue.id)
                )
            )

    def __url_status_handler(self, url_status):
        """ Callback handler when signal.id == ID_URL_STATUS:
                <URL SIGNAL>
        """
        client = url_status.content.client
        exception = url_status.content.exception
        source = client.getsource()
        srcwrapper = self._url.getwrapper(source)
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
            self.__exception_signal.put_nowait(SIGNAL_EXCEPTION(e))

    def _buffer_release_thread(self):
        """ A thread handler about releasing buffer. """
        with self._buff_lock:
            self._block.release_buffer(self.file)
            if self._saver:
                self._saver.dump()
        gc.collect()

    def __buffer_signal_handler(self, byte):
        """ Callback handler when signal.id == ID_BUFF:
                <BUFFER COUNTER>
        """
        self._url.clear_counter()
        self.__buff_counter += byte
        if self.__buff_counter >= self._buffsize:
            self.__buff_counter = 0
            self._tpm.put(self._buffer_release_thread, GROUP_RELEASE).start()

    def __client_thread_end_handler(self, client):
        """ Callback handler when signal.id == ID_THREAD_END:
                <CLIENT THREAD END OF LIFE>
        """
        if self.runflag:
            if self._block.is_go_finished():
                srcwrapper = self._url.getwrapper(self._block.getsource())
                srcwrapper.disuse()
            else:
                self._block.clear()
                self._tpm.put(client.run, GROUP_CLIENT, args=(self._client_callback_queue,),
                              owner=self._block).start()

        if self.is_finish_go():
            self._buffer_release_thread()
            self._finish_task()

    def install_saver(self, saver):
        self._saver = saver

    def dump_data(self):
        return ConsoleDumpedData(block_data=tuple(self._block.dump_data()),
                                 acum_time=self._acum_time.getinctime())

    def load(self, dumped_data):
        data = ConsoleDumpedData(*dumped_data)
        self._acum_time = AccumulatedTime(data.acum_time)

        for i in data.block_data:
            b = BlockDumpedData(*i)
            prog = Progress((0,))
            srcwrapper = self._url.get(b.url_id)
            source = srcwrapper.get()
            client = build_client(source, prog)
            srcwrapper.use()
            self.insert(client, prog)

    def get_block_size(self):
        return self._block_size

    def join(self, timeout=None):
        self._tpm.join(timeout)

    def install_external_callback_queue(self, handle):
        self.__callback_queue = handle

    def getBuffCnter(self):
        return self.__buff_counter

