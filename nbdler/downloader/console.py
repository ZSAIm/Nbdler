# -*- coding: UTF-8 -*-

from ..utils.eventdriven import Timer, Semaphore, Controller, ControllerPool
from ..utils import saver
from ..event import EVT_TASK_PAUSING, EVT_BUFFER_RELEASE
from ..utils.misc import Component
from .struct.progress import Progress
from .struct.storage import BufferStorage
from ._download import buffer_model, console_model, client_model
from .client import get_client
from threading import Lock
from queue import Queue


class ConsoleConfig(Component):
    """ 控制台配置信息。 """
    DEFAULT_HEARTBEAT_INTERVAL = 0.5

    def __init__(self, partial, max_thread, unit_size, max_buff, timeout,
                 max_speed=None, daemon=False, heartbeat_interval=DEFAULT_HEARTBEAT_INTERVAL, **options):
        self.partial = partial
        self.max_thread = max_thread
        self.unit_size = unit_size
        self.max_buff = max_buff
        self.timeout = timeout
        self.heartbeat_interval = heartbeat_interval
        self.max_speed = max_speed
        self.daemon = daemon
        # 对于允许部分下载的任务会忽略改设置
        self.nbcfg = options.pop('nbcfg', None)
        self.options = options

    @staticmethod
    def is_permitted(item):
        return item not in ('partial', 'unit_size', 'overwrite', 'max_thread')

    def __snapshot__(self):
        snapshot = dict(self.options)
        snapshot.update({
            'partial': self.partial,
            'max_thread': self.max_thread,
            'unit_size': self.unit_size,
            'max_buff': self.max_buff,
            'timeout': self.timeout,
            'heartbeat_interval': self.heartbeat_interval,
            'max_speed': self.max_speed,
            'daemon': self.daemon,
            'nbcfg': self.nbcfg
        })
        return snapshot


class Console(Component):
    def __init__(self, file, url, block_mgr, partial, **configure):
        self.file = file
        self.url = url
        self.block_mgr = block_mgr
        # 缓冲存储器。
        self.storage = BufferStorage()
        # 正在工作的客户端列表
        self.working = []

        # 为了让控制台的事件处理映射更灵活，支持传递自定义或修改后的事件处理映射蓝图。
        buf_m = configure.pop('buffer_model', buffer_model)
        con_m = configure.pop('console_model', console_model)
        cli_m = configure.pop('client_model', client_model)

        # 初始化控制台配置。
        self.cfg = ConsoleConfig(partial, **configure)

        # 缓冲控制器
        self.buff_worker = Controller(buf_m, static={
            'con': self, 'cfg': self.cfg, 'file': file, 'storage': self.storage
        }, name='%s-buff_worker' % file.name, daemon=self.cfg.daemon)
        # 控制台控制器
        self.con_worker = Controller(con_m, static={
            'con': self, 'url': url, 'file': file, 'buff_worker': self.buff_worker, 'storage': self.storage,
            'block_mgr': self.block_mgr, 'cfg': self.cfg, 'working': self.working
        }, name='%s-con_worker' % file.name, daemon=self.cfg.daemon)
        # 客户端工作控制器
        self.cli_workers = ControllerPool(self.cfg.max_thread, mapping=cli_m, static={
            'con_worker': self.con_worker
        }, name='%s-cli_workers' % file.name, daemon=self.cfg.daemon)

        # 方便控制台控制器引用客户端工作控制器，静态上下文添加客户端对象。
        self.con_worker.__static__.update({'cli_workers': self.cli_workers})
        # 控制台控制器安装插件定时器和限速信号量控制
        self.con_worker.Adapter(Timer(self.cfg.heartbeat_interval), Semaphore())

        self.__trap_lock = Lock()
        self.__paused = False
        self.__raise = Queue()

    @property
    def adapters(self):
        return self.con_worker.adapters

    def config(self, **options):
        """ 配置控制台。

        注意：并不是所有的配置都是允许修改的。
        """
        for k, v in options.items():
            if self.cfg.is_permitted(k):
                setattr(self.cfg, k, v)
            else:
                # 将额外的配置放入选项中。
                if k not in self.cfg.__dict__:
                    self.cfg.options[k] = v

    def is_paused(self):
        return self.__paused

    def is_alive(self):
        return self.con_worker.is_alive()

    def _fast_slice(self):
        """ 快速切片。
        注意： 该操作不能在下载运行过程中进行。
        """
        assert not self.is_alive() and self.cfg.partial

        # 搜索剩余量最大的下载块，并对其进行切片操作。
        block, put_range = self.block_mgr.find_room_for_new_block()
        fb_range = block.progress.slice(put_range)

        # 如果无法切分出更多的块，就结束快速切片操作。
        if not fb_range:
            return None

        # 完成切片，添加下载块，并将任务加入待下载队列。
        source_wrap = self.url.find_min_avl_used()
        if not source_wrap:
            source_wrap = self.url.find_min_used()
        # 为了能够进行有效的分配下载源，所以需要在这里进行使用。
        # 需要注意的是，在分配完后需要进行重置下载源的使用次数。
        source_wrap.use()
        # 构建下载进度，客户端和下载块。
        progress = Progress(fb_range)
        source = source_wrap.get()
        options = dict(self.cfg.options)
        options['timeout'] = self.cfg.timeout
        client = get_client(source.protocol)(source, progress, True, **options)
        block = self.block_mgr.insert(client, progress)
        return block

    def prepare(self):
        """ 控制台开始的准备工作。"""
        assert not self.con_worker.is_alive()
        assert not self.block_mgr.finish_flag
        # 清除残留事件
        self.con_worker.clean()
        self.buff_worker.clean()
        self.cli_workers.clean()
        # 打开文件。
        self.file.open()
        # 清除异常队列的消息。
        self.__raise = Queue()
        # 根据配置开启关闭限制器。
        self.speed_limit(self.cfg.max_speed)

    def run(self):
        """ 开始下载任务。 """
        assert not self.con_worker.is_alive()
        assert not self.block_mgr.finish_flag

        self.__paused = False
        # 清空下载工作池的任务队列。
        self.cli_workers.clean()
        # 搜索未完成的下载分片。
        leftover = []
        for b in self.block_mgr.get_all():
            if not b.progress.finish_flag:
                leftover.append(b)

        if self.cfg.partial:
            # 如果未完成的分片不足以提供给下载池，那么将对下载请求进行快速切片。
            if len(leftover) < self.cfg.max_thread:
                left_len = self.cfg.max_thread - len(leftover)
                for i in range(left_len):
                    block = self._fast_slice()
                    if not block:
                        break
                    leftover.append(block)

        # 由方法_fast_slice()的说明，这里需要进行重置下载源。
        for u in self.url.get_all():
            u.reset()

        if leftover:
            # 开启控制台控制器，客户端控制器池，缓存控制器。
            self.con_worker.run(context={'leftover': leftover})
            self.cli_workers.run()
            self.buff_worker.run()

            # 分派下载任务。
            for blo in leftover[:]:
                self.url.get(blo.client.source.id).use()
                # 清理下载块客户端的消息队列。
                blo.client.clean()
                self.cli_workers.submit(blo.client.run, args=(self.con_worker,), context={
                    'blo': blo
                })
                leftover.remove(blo)
                self.working.append(blo)

            # 激活下载块管理器。
            self.block_mgr.activate()
        else:
            # 没有可下载的下载块，那就关闭文件。
            self.file.close()

    def speed_limit(self, max_speed):
        """ 设置下载速度限制。 """
        self.cfg.max_speed = max_speed
        # 限制器以插件的性质安装到控制台控制器。
        if max_speed is None:
            self.adapters['semaphore'].close()
        else:
            self.adapters['semaphore'].open()

    def release_buffer(self):
        """ 强制释放缓冲。 """
        if self.buff_worker.is_idle():
            self.buff_worker.dispatch(EVT_BUFFER_RELEASE)
            return True
        return False

    def pause(self, block=True, timeout=None):
        """ 暂停下载控制台。 """
        self.__paused = True
        self.con_worker.dispatch(EVT_TASK_PAUSING)
        if block:
            self.con_worker.wait(timeout=timeout)

    def raise_exception(self, error):
        """ 如果抛出的错误是error = None，那么说明是由于控制台关闭所抛出的消息。"""
        if error is None:
            # 如果进入了trap方法的锁才进行推送None以通知释放锁。
            if not self.__trap_lock.locked():
                return
        self.__raise.put(error)

    def wait(self, timeout=None):
        """ 等待控制台至停止。 """
        if not self.con_worker.is_alive():
            return
        self.con_worker.wait(timeout)

    def trap(self, timeout=None):
        """ 具有响应异常错误的等待wait()方法。

        如果下载器在下载过程中发生了客户端或者服务器错误，这个方法可以将内部的错误抛出到当前线程。
        但要注意的是下载器并不会因此而自动暂停，而是默认不断重试，直到用户手动暂停或下载完成。
        当你需要知道下载是否正常的时候可以通过该方法进行等待下载器的下载结束。
        """
        with self.__trap_lock:
            if not self.con_worker.is_alive():
                return
            while True:
                exception = self.__raise.get(timeout=timeout)
                # 如果异常信息是None说明是控制台停止所抛出的消息。
                if exception is None:
                    break
                raise exception

    def listened_by(self, queue, allow, name):
        """ 时间监听"""
        self.con_worker.listened_by(queue, allow, name)

    def dump(self, filepath=None, method=('json', 'gzip')):
        """ 转存下载配置文件。"""
        if not filepath:
            filepath = self.cfg.nbcfg or self.file.fullpath + '.nbcfg'
        saver.dump(filepath, self.__snapshot__(), method)

    def export(self):
        """ 以字典类型返回下载配置信息。"""
        return self.__snapshot__()

    def __snapshot__(self):
        """ 对象快照。为了下次快速构建对象而创建的字典信息。
        用于保存下载进度配置文件所需信息。
        """
        block_map = self.block_mgr.__snapshot__()
        url = self.url.__snapshot__()
        file = self.file.__snapshot__()
        configure = self.cfg.__snapshot__()
        return {
            'block_mgr': block_map,
            'cfg': configure,
            'url': url,
            'file': file
        }

    @staticmethod
    def load(snapshot):
        """ 从快照字典加载对象。"""
        from .file import File
        from .url.manager import UrlManager
        from .struct.block import BlockManager
        from .struct.progress import Progress
        # 初始化文件对象
        f = snapshot['file']
        file = File(f['path'], f['name'], f['size'], f['overwrite'], f['downloading_extension'])

        # 初始化下载源对象
        url = UrlManager.load(snapshot['url'])
        cfg = snapshot['cfg']
        partial = cfg.pop('partial')

        # 构建下载块映射图
        bm = snapshot['block_mgr']
        block_map = BlockManager(cfg['unit_size'], file.size, bm['increment_time'])
        for b in bm['all']:
            # 创建下载进度
            p = b['progress']
            progress = Progress(p['range'], p['increment_go'], p['increment_done'], p['increment_time'])
            # 创建客户端
            src = url.find_min_avl_used()
            source = src.get()
            options = {'timeout': cfg['timeout']}
            options.update(cfg['options'])
            cli = get_client(source.protocol)(source, progress, partial, **options)
            # 插入下载块
            block_map.insert(cli, progress, b['cells'])

        return Console(file, url, block_map, partial, **cfg)


