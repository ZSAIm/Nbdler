# -*- coding: UTF-8 -*-
""" 下载块

下载块Chunk结构:

+---------------------------------+
| Chunk                           |
|         +--------+----------+   |
|         | client | progress |   |
|         +--------+----------+   |
+---------------------------------+
| Block [0:25]                    |
| >>>>>-------------------- 05/25 |
+---------------------------------+
|+|+|+|+|+|+|+|+|+|-|-|-|-|-|-|-|-|
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|  <--------- block
+---------------------------------+

其中: '>' 表示已下载块; '-' 表示未下载块

下载块管理器:

+-------------------------------------------------------------+
| ChunkManager                                                |
|      +--------C1-------+ +---C3----+ +---------C2--------+  |
|      |-|-|-|-|-|-|-|-|-| |-|-|-|-|-| |-|-|-|-|-|-|-|-|-|-|  |
|      |-|-|-|-|-|-|-|-|-| |-|-|-|-|-| |-|-|-|-|-|-|-|-|-|-|  |
|      |-|-|-|-|-|-|-|-|-| |-|-|-|-|-| |-|-|-|-|-|-|-|-|-|-|  |
|      +-----------------+ +---------+ +-------------------+  |
+-------------------------------------------------------------+

文件下载块切片原理:

表述：
    搜索从剩余下载量最多的下载块中切片生成新的下载块。

1. 下载块C1 (总下载块=C1)
+--------------------------------------------------------------------------------------------------------------------+
|                                                C1 [0:100]                                                          |
|        >>>>>>>---------------------------------------------------------------------------------------------        |
+--------------------------------------------------------------------------------------------------------------------+

2. 从下载块B1中切片分出下载块C2 (总下载块=C1+C2)
+--------------------------------------------------------------+-----------------------------------------------------+
|                         C1 [0:54]                            |                   C2 [54:100]                       |
|    >>>>>>>>>>>>>>----------------------------------------    |    >>>-------------------------------------------   |
+--------------------------------------------------------------+-----------------------------------------------------+

3. 从下载块C2中切片分出下载块B3 (总下载块=C1+C2+C3)
+----------------------------------------------------------+-----------------------------+---------------------------+
|                         C1 [0:54]                        |         C2 [54:79]          |        C3 [79:100]        |
|  >>>>>>>>>>>>>>>>>>>>>---------------------------------  |  >>>>>>>>-----------------  |   >>>>-----------------   |
+----------------------------------------------------------+-----------------------------+---------------------------+

4. 从下载块C1中切片分出下载块C4 (总下载块=C1+C2+C3+C4)
+--------------------------------------+----------------------+----------------------------+-------------------------+
|               C1 [0:36]              |      C4 [36:54]      |         C2 [54:79]         |      C3 [79:100]        |
| >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>----- |  >-----------------  |  >>>>>>>>>>>>>>>>>-------- |  >>>>>>>>>>>>>>>>-----  |
+--------------------------------------+----------------------+-------------------------—--+-------------------------+

5. 从下载块C4中切片分出下载块B5 (总下载块=C1+C2+C3+C4+C5)
+--------------------------------------+------------+------------+---------------------------+-----------------------+
|               C1 [0:36]              | C4 [36:46] | C5 [46:54] |         C2 [54:79]        |      C3 [79:100]      |
| >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>-- | >>>>>----- |  >>------  | >>>>>>>>>>>>>>>>>>>>>>--- | >>>>>>>>>>>>>>>>>---- |
+--------------------------------------+------------+------------+---------------------------+-----------------------+

...


"""
from .utils import UsageInfo
from math import ceil
from threading import RLock
from time import time
from .progress import Progress
import bisect


class Chunk:
    __slots__ = 'uri_id', 'begin', 'end'

    def __init__(self, uri_id, begin, end):
        """
        :param
            uri_id     : 源URI的ID
            begin   : 单元的开始索引
            end     : 单元的结束索引
        """
        self.uri_id = uri_id
        self.begin = begin
        self.end = end

    @property
    def length(self):
        return self.end - self.begin

    def __repr__(self):
        return f'<Cell ({self.uri_id})[{self.begin}-{self.end}]>'

    def __iter__(self):
        return iter([self.uri_id, self.begin, self.end])


class Block:
    """ 下载块是对某一刻下载进度的快照，是一个状态量。不具备实时性。
    既然不作为实时数据，那么不需要对其进行强制与实时数据对应。
    那么对于未确定大小的进度对象Progress，即大小为inf时，不必关注其大小，关注的是其下载的量的块记录。
    """
    __slots__ = 'client', 'progress', '_chunk_size', '_range', '_chunks', '_lock'

    def __init__(self, progress, chunk_size, init_chunks=None):
        self.client = None
        self.progress = progress
        self._chunk_size = chunk_size

        begin = progress.begin // chunk_size

        end = 1
        if progress.end not in (float('inf'), None):
            end = int(ceil(progress.end / chunk_size))

        self._range = [begin, end]
        self._chunks = []

        if init_chunks is not None:
            self._chunks = [Chunk(*chunk) for chunk in init_chunks]

        self._lock = RLock()
        self.refresh()

    @property
    def begin(self):
        return self._range[0]

    @property
    def end(self):
        return self._range[1]

    @property
    def length(self):
        try:
            return self._range[1] - self._range[0]
        except TypeError:
            return float('inf')

    @property
    def chunks(self):
        self.refresh()
        return self._chunks

    def current_uri(self):
        return self.client and self.client.source_uri

    def slice(self, request_range):
        resp_range = self.progress.slice(request_range)
        self.refresh()
        return resp_range

    def unused_length(self):
        """ 返回下载块中未处理的块chunk长度。"""
        if self.progress.end in (None, float('inf')):
            return float('inf') if not self.progress.is_walk_finished() else 0
        self.refresh()

        return (not self._chunks and self.length) or self.length - self._chunks[-1].end

    def __getitem__(self, index):
        assert type(index) is int
        for c in self.chunks:
            if c.begin <= index < c.end:
                return c

        assert False

    def refresh(self):
        """ 刷新下载块进度信息。

        由于下载块只是作为快照的形式监控，并不直接由下载客户端接管，所以得到的信息并不是实时的，
        这就需要在获取信息的时候进行刷新信息。
        对外的接口都已进行了刷新数据来保证数据的实时性。
        """
        with self._lock:
            progress = self.progress

            block_begin = self.begin

            cur_uri = self.current_uri()

            cur_walk = progress.walk_length / self._chunk_size
            if not progress.walk_left:
                cur_walk = int(ceil(cur_walk))
            else:
                cur_walk = int(cur_walk)

            cur_done = progress.done_length / self._chunk_size
            if not progress.done_left:
                cur_done = int(ceil(cur_done))
            else:
                cur_done = int(cur_done)

            # 更新块范围
            block_end = progress.end
            if block_end is None:
                block_end = cur_walk + block_begin
            block_end = int(ceil(block_end / self._chunk_size))

            self._range[1] = block_end

            last_chunk = (self._chunks and self._chunks[-1]) or None
            if last_chunk is None:
                if cur_uri is not None:
                    self._chunks.append(Chunk(cur_uri.id, 0, cur_walk))
                else:
                    pass
            else:
                if cur_uri is not None:
                    if last_chunk.uri_id != cur_uri.id:
                        self._chunks.append(Chunk(cur_uri.id, cur_walk, cur_walk))
                    else:
                        last_chunk.end = cur_walk

    def half_unused(self):
        unused_len = self.unused_length()
        put_begin = self.begin + (self.length - unused_len) + int(ceil(unused_len / 2))
        put_end = self.end
        if put_begin == put_end:
            return None
        return put_begin * self._chunk_size, put_end * self._chunk_size

    def request(self, client):
        self.client = client
        return self

    async def __aenter__(self):
        from nbdler.handler import block_context

        assert self.client
        block_context.set(self)
        return await self.client.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        from nbdler.handler import block_context

        self.refresh()
        client = self.client
        await client.__aexit__(exc_type, exc_val, exc_tb)
        self.client = None
        block_context.set(None)

    def dumps(self):
        return {
            'progress': list(self.progress),
            'range': [self.begin, self.end],
            'chunks': [list(c) for c in self._chunks]
        }

    def __repr__(self):
        return f'<Chunk [{self.begin}-{self.end}] {self.progress.percent_complete / 100:.2%} client={self.client}>'

    def __iter__(self):
        return iter([list(self.progress), self._chunk_size, [list(block) for block in self._chunks]])

    def __lt__(self, other):
        return self.begin < other.begin


class BlockGroup:
    """ 下载块管理器。 """
    def __init__(self, chunk_size, total_size, duration=0):
        self._blocks = []
        self.chunk_size = chunk_size
        try:
            self.total_chunk = int(ceil(total_size / chunk_size))
        except (TypeError, OverflowError):
            self.total_chunk = 1

        if total_size is None:
            total_size = float('inf')
        self.total_size = total_size

        self.usage_info = UsageInfo(self.walk_length)

        self._start_time = None
        self._duration = duration

    def transfer_rate(self):
        """ 实时数据传输速率。 """
        return self.usage_info.rate

    def average_speed(self):
        """ 平均数据传输速率。 """
        total_time = self._duration + time() - (self._start_time or time())
        return self.walk_length() / (total_time or float('inf'))

    def walk_length(self):
        """ 已下载字节数。 """
        return sum((v.progress.walk_length for v in self._blocks))

    def done_length(self):
        """ 已缓冲的字节数。"""
        return sum((v.progress.done_length for v in self._blocks))

    def remaining_length(self):
        """ 还剩余字节数。 """
        return self.total_size - self.walk_length()

    def remaining_time(self):
        """ 估计剩余时间。 """
        realtime_rate = self.transfer_rate()
        if not realtime_rate:
            return float('inf')
        return self.remaining_length() / realtime_rate

    def percent_complete(self):
        return self.walk_length() * 100 / self.total_size

    def is_walk_finished(self):
        for b in self._blocks:
            if not b.progress.is_walk_finished():
                return False
        return not self.integrity_check()

    def is_done_finished(self):
        for b in self._blocks:
            if not b.progress.is_done_finished():
                return False
        return not self.integrity_check()

    is_finished = is_done_finished

    def insert(self, put_range):
        """ 插入下载块。
        Args:
            put_range: 插入的快进度范围range
        """
        block = Block(Progress(put_range), self.chunk_size)
        bisect.insort(self._blocks, block)

        return block

    def unfinished_blocks(self):
        return [b for b in self._blocks if not b.progress.is_walk_finished()]

    def activate(self):
        """ 激活下载块映射图。 """
        self._start_time = time()

    def deactivate(self):
        """ 关闭下载块映射图。 """
        self._duration += time() - (self._start_time or time())
        self._start_time = None
        self.usage_info.reset()
        if self.is_walk_finished():
            if self.total_size in (None, float('inf')):
                self.total_size = self.walk_length()

    def integrity_check(self):
        """ 下载块映射图完整性检测。
        如果下载块缺失返回缺失的块，否则返回[]。
        """
        if not self._blocks:
            return [(0, self.total_chunk)]
        missing = []
        prv_end = self._blocks[0].end
        prv_b = None
        for v in self._blocks[1:]:
            v.refresh()
            if v.begin - prv_end > 0:
                # 如果下一个下载块的起点索引比上一个下载块的结束索引要大，说明了这其中缺少了一块。
                missing.append((prv_end, v.begin))
            elif v.begin - prv_end < 0:
                # 如果下一个下载块的起点索引比上一个下载块的结束索引要小，说明这出现了下载块范围交叉。
                raise ValueError(f'完整性校验不通过。冲突：{prv_b} <-> {v}')

            prv_end = v.end
            prv_b = v

        return missing

    def dumps(self):
        return {
            'chunk_size': self.chunk_size,
            'total_size': self.total_size,
            'duration': self._duration,
            'blocks': [b.dumps() for b in self._blocks],
        }

    @classmethod
    def loads(cls, dumpy):
        chunk_size = dumpy['chunk_size']
        block_grp = cls(chunk_size, dumpy['total_size'], dumpy['duration'])
        for block in dumpy['blocks']:
            progress = Progress(*block['progress'])
            block = Block(progress, chunk_size, block['chunks'])
            bisect.insort(block_grp._blocks, block)
        return block_grp

    def __iter__(self):
        """ 迭代返回下载块对象。"""
        return iter([self.chunk_size, self.total_size, [list(block) for block in self._blocks]])

    def __repr__(self):
        return f'<BlockGroup transfer_rate={round(self.transfer_rate() / 1024)} kb/s ' \
               f'percent={round(self.percent_complete(), 2)}%>'
