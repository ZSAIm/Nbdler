
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
    def getincbyte(self):
        """ Return byte size downloaded. """

    @abstractmethod
    def getinstspeed(self):
        """ Return instant download speed. """

    @abstractmethod
    def getavgspeed(self):
        """ Return average download speed. """

    @abstractmethod
    def get_remain_byte(self):
        """ Return remaining byte to finish the download task. """

    @abstractmethod
    def get_remain_time(self):
        """ Return remaining time to finish the download task. """

    @abstractmethod
    def is_finish(self):
        """ Return True if download task finished. """

    @abstractmethod
    def _buffer_release_thread(self):
        """ A thread handler about writing buffer to file. """

    @abstractmethod
    def _client_callback_handle_thread(self):
        """ A thread handler about callback signal. """

    @abstractmethod
    def getblocksize(self):
        """ Return console's unit block size. """

