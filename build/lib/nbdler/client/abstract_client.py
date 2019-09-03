

from six import add_metaclass

from abc import ABCMeta, abstractmethod


@add_metaclass(ABCMeta)
class AbstractClient:

    @classmethod
    @abstractmethod
    def connect(cls):
        pass

    @classmethod
    @abstractmethod
    def retrieve(cls):
        pass

    @classmethod
    @abstractmethod
    def send_signal(cls, signal):
        pass

    @classmethod
    @abstractmethod
    def write_to_file(cls, fp):
        pass

    @classmethod
    @abstractmethod
    def install_callback(cls, callback):
        pass

    @classmethod
    @abstractmethod
    def clear_callback(cls):
        pass


@add_metaclass(ABCMeta)
class AbstractResponse:

    @classmethod
    @abstractmethod
    def read(cls):
        pass


