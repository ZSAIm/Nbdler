# -*- coding: UTF-8 -*-

from .struct.body import Body
import os


class Downloader:
    def __init__(self, console, new_file):
        self._console = console
        self.__body = Body(console)

        self.__new_file__ = new_file

    @property
    def body(self):
        return self.__body

    info = body

    @property
    def console(self):
        """ 返回下载控制台对象。"""
        return self._console

    @property
    def file(self):
        """ 返回下载文件对象。"""
        return self._console.file

    @property
    def url(self):
        """ 返回下载源对象。"""
        return self._console.url

    @property
    def block_mgr(self):
        return self._console.block_mgr
    
    def is_alive(self):
        """ 下载器是否在运行中。 """
        return self._console.is_alive()

    def is_finished(self):
        """ 下载是否完成。 """
        return self._console.block_mgr.finish_flag

    def config(self, **options):
        """ 配置下载器。 """
        self._console.config(**options)

    def start(self):
        """ 开始下载。 """
        if self.__new_file__:
            # 构建下载文件
            self._console.file.makefile()
            self.__new_file__ = False

        self._console.prepare()
        self._console.run()

    def pause(self, block=True, timeout=None):
        """ 暂停下载。 """
        self._console.pause(block, timeout)

    stop = pause

    def close(self):
        """ 关闭下载器，并且删除下载配置文件 *.nbcfg。 """
        if not self.is_finished():
            raise PermissionError('下载未完成，不允许关闭下载器.')
        if self._console.file.safe_ext:
            self._console.file.remove_downloading_extension()
        os.unlink(self._console.cfg.nbcfg)

    def wait(self, timeout=None):
        """ 等待下载完成结束。

        该等待方法不会将内部的错误抛出，而是会等待至下载器停止。
        """
        self._console.wait(timeout)

    join = wait

    def trap(self, timeout=None):
        """ 具有响应异常错误的等待wait()方法。

        如果下载器在下载过程中发生了客户端或者服务器错误，这个方法可以将内部的错误抛出到当前线程。
        但要注意的是下载器并不会因此而自动暂停，而是默认不断重试，直到用户手动暂停或下载完成。
        当你需要知道下载是否正常的时候可以通过该方法进行等待下载器的下载结束。
        """
        self._console.trap(timeout)

    def speed_limit(self, max_speed):
        """ 设置速度限制，None为关闭速度限制。"""
        self._console.speed_limit(max_speed)

    def remaining_length(self):
        """ 剩余下载字节数。 """
        return self._console.block_mgr.remaining_length

    def remaining_time(self):
        """ 估计剩余下载时间。 """
        return self._console.block_mgr.remaining_time

    def realtime_speed(self):
        """ 实时速度。 """
        return self._console.block_mgr.realtime_speed

    def average_speed(self):
        """ 平均速度。 """
        return self._console.block_mgr.average_speed

    def increment_go(self):
        """ 返回已下载的字节长度。"""
        return self._console.block_mgr.incr_go

    def increment_done(self):
        """ 返回已写出文件的字节长度。"""
        return self._console.block_mgr.incr_done

    def dump(self, filepath=None):
        """ 转储下载配置文件。 保存路径由file指定。
        若不指定filepath则会保存到设置的nbcfg或者默认的文件保存路径加上 .nbcfg.
        """
        self._console.dump(filepath)

    def export(self):
        """ 以字典类型返回下载配置信息。"""
        return self.console.export()

    def listened_by(self, queue, allow, name=None):
        """ 监听下载器控制台的事件。"""
        self._console.listened_by(queue, allow, name)

    def __repr__(self):
        return '<Downloader %s - %s> ' % (self._console.file.name, self._console.file.size)



