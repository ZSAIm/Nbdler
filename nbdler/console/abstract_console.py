
from six import add_metaclass
from abc import abstractmethod, ABCMeta


@add_metaclass(ABCMeta)
class AbstractConsole:

    @abstractmethod
    def prepare(self):
        pass

    @abstractmethod
    def run(self):
        """ Run download task. """

    @abstractmethod
    def pause(self, *args, **kwargs):
        """ Pause downloading. """

    @abstractmethod
    def insert(self, *args, **kwargs):
        """ Insert a block described by Client and Progress into the console. """

    @abstractmethod
    def get_go_inc(self):
        """ Return byte size downloaded. """

    @abstractmethod
    def getinstspeed(self):
        """ Return instant download speed. """

    @abstractmethod
    def getavgspeed(self):
        """ Return average download speed. """

    @abstractmethod
    def get_byte_left(self):
        """ Return remaining byte to finish the download task. """

    @abstractmethod
    def get_time_left(self):
        """ Return remaining time to finish the download task. """

    @abstractmethod
    def is_finished(self):
        """ Return True if download task finished. """

    @abstractmethod
    def _buffer_release_thread(self):
        """ A thread handler about writing buffer to file. """

    @abstractmethod
    def _client_callback_handle_thread(self):
        """ A thread handler about callback signal. """

    @abstractmethod
    def get_block_size(self):
        """ Return console's unit block size. """

    @abstractmethod
    def getBuffCnter(self):
        """ Return current buffer counter. """
