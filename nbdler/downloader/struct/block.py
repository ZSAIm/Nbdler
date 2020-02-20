# -*- coding: UTF-8 -*-
""" 下载块

下载块Block结构:

+---------------------------------+
| Block                           |
|         +--------+----------+   |
|         | client | progress |   |
|         +--------+----------+   |
+---------------------------------+
| CellRange [0:25]                |
| >>>>>-------------------- 05/25 |
+---------------------------------+
|+|+|+|+|+|+|+|+|+|-|-|-|-|-|-|-|-|
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|  <--------- unit block
+---------------------------------+

其中: '>' 表示已下载块; '-' 表示未下载块

下载块管理器:

+-------------------------------------------------------------+
| BlockManager                                                |
|      +--------B1-------+ +---B3----+ +---------B2--------+  |
|      |-|-|-|-|-|-|-|-|-| |-|-|-|-|-| |-|-|-|-|-|-|-|-|-|-|  |
|      |-|-|-|-|-|-|-|-|-| |-|-|-|-|-| |-|-|-|-|-|-|-|-|-|-|  |
|      |-|-|-|-|-|-|-|-|-| |-|-|-|-|-| |-|-|-|-|-|-|-|-|-|-|  |
|      +-----------------+ +---------+ +-------------------+  |
+-------------------------------------------------------------+

文件下载块切片原理:

表述：
    搜索从剩余下载量最多的下载块中切片生成新的下载块。

1. 下载块B1 (总下载块=B1)
+--------------------------------------------------------------------------------------------------------------------+
|                                                B1 [0:100]                                                          |
|        >>>>>>>---------------------------------------------------------------------------------------------        |
+--------------------------------------------------------------------------------------------------------------------+

2. 从下载块B1中切片分出下载块B2 (总下载块=B1+B2)
+--------------------------------------------------------------+-----------------------------------------------------+
|                         B1 [0:54]                            |                   B2 [54:100]                       |
|    >>>>>>>>>>>>>>----------------------------------------    |    >>>-------------------------------------------   |
+--------------------------------------------------------------+-----------------------------------------------------+

3. 从下载块B2中切片分出下载块B3 (总下载块=B1+B2+B3)
+----------------------------------------------------------+-----------------------------+---------------------------+
|                         B1 [0:54]                        |         B2 [54:79]          |        B3 [79:100]        |
|  >>>>>>>>>>>>>>>>>>>>>---------------------------------  |  >>>>>>>>-----------------  |   >>>>-----------------   |
+----------------------------------------------------------+-----------------------------+---------------------------+

4. 从下载块B1中切片分出下载块B4 (总下载块=B1+B2+B3+B4)
+--------------------------------------+----------------------+----------------------------+-------------------------+
|               B1 [0:36]              |      B4 [36:54]      |         B2 [54:79]         |      B3 [79:100]        |
| >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>----- |  >-----------------  |  >>>>>>>>>>>>>>>>>-------- |  >>>>>>>>>>>>>>>>-----  |
+--------------------------------------+----------------------+-------------------------—--+-------------------------+

5. 从下载块B4中切片分出下载块B5 (总下载块=B1+B2+B3+B4+B5)
+--------------------------------------+------------+------------+---------------------------+-----------------------+
|               B1 [0:36]              | B4 [36:46] | B5 [46:54] |         B2 [54:79]        |      B3 [79:100]      |
| >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>-- | >>>>>----- |  >>------  | >>>>>>>>>>>>>>>>>>>>>>--- | >>>>>>>>>>>>>>>>>---- |
+--------------------------------------+------------+------------+---------------------------+-----------------------+

...


"""
from ..struct.misc import Timer, RealtimeSpeed
from ...utils.misc import BaseInfo, Component
from math import ceil
from threading import Lock


class CellRange(BaseInfo):
    __slots__ = 'sid', 'begin', 'end'

    def __init__(self, sid, begin, end):
        """
        :param
            sid     : 占用的ID号，若sid等于None，那说明当前单元是未被占用单元。
            begin   : 单元的开始索引
            end     : 单元的结束索引
        """
        self.sid = sid
        self.begin = begin
        self.end = end

    @property
    def __dict__(self):
        return {'sid': self.sid, 'begin': self.begin, 'end': self.end}

    def __repr__(self):
        return '<Cell (%s)[%s-%s]>' % (self.sid, self.begin, self.end)


class Block(Component):
    """ 下载块是对某一刻下载进度的快照，是一个状态量。不具备实时性。
    既然不作为实时数据，那么不需要对其进行强制与实时数据对应。
    那么对于未确定大小的进度对象Progress，即大小为inf时，不必关注其大小，关注的是其下载的量的块记录。
    """
    __slots__ = 'client', 'progress', '_unit_size', '__range', '__cells', '__refresh_lock'

    def __init__(self, client, progress, unit_size, relative_cells=None):
        self.client = client
        self.progress = progress
        self._unit_size = unit_size

        begin = progress.begin // unit_size

        # 当不提前知道块大小的情况下以一块为起点。
        # progress.end == None是进度大小未指定的情况。
        end = 1
        if progress.end != float('inf'):
            end = int(ceil(progress.end / unit_size))

        self.__range = [begin, end]

        # 下载块的占用单元情况
        if not relative_cells:
            relative_cells = [CellRange(None, 0, end-begin)]
        else:
            # relative_cells 中的cell需要以字典的形式存储。
            relative_cells = [CellRange(**c) for c in relative_cells]
        self.__cells = relative_cells

        self.__refresh_lock = Lock()
        self.refresh()

    @property
    def begin(self):
        return self.__range[0]

    @property
    def end(self):
        return self.__range[1]

    @property
    def length(self):
        try:
            return self.__range[1] - self.__range[0]
        except TypeError:
            return float('inf')

    @property
    def cells(self):
        self.refresh()
        return self.__cells

    @property
    def margin(self):
        if self.progress.end is None:
            return float('inf') if not self.progress.finish_go_flag else 0

        # 未被占用的单元只能排在最后面，这里使用属性cells，刷新后再搜索
        mar_cell = self.cells[-1]
        try:
            if mar_cell.sid is None:
                h = mar_cell.end - mar_cell.begin
            else:
                h = 0
        except TypeError:
            h = float('inf')
        return h

    def __getitem__(self, index):
        assert type(index) is int
        for c in self.cells:
            if c.begin <= index < c.end:
                return c

        assert False

    def refresh(self):
        """ 刷新下载块进度信息。

        由于下载块只是作为快照的形式监控，并不直接由下载客户端接管，所以得到的信息并不是实时的，
        这就需要在获取信息的时候进行刷新信息。
        对外的接口都已进行了刷新数据来保证数据的实时性。
        """
        with self.__refresh_lock:
            client = self.client
            if not client:
                # 如果没有客户端对象说明下载块已经完成了，再删除引用前以经过了刷新，之后没有刷新的必要。
                return
            # 对于不提前知道下载块大小的情况下，需要根据进度对象更新下载块长度。
            # 并且以下载量incr_go作为下载块的大小进行计算
            progress_incr_go = self.progress.increment_go
            progress_begin = self.progress.begin
            abs_end = self.progress.end
            if abs_end == float('inf'):
                # 未确定块大小的情况下，使用下载步进来作为当前的结束点。
                abs_end = progress_incr_go + progress_begin
            self.__range[1] = int(ceil(abs_end / self._unit_size))

            sid = client.source.id
            mar_cell = self.__cells[-1]

            # 已下载进度步进的单元块索引
            incr_end = int(ceil(progress_incr_go / self._unit_size))

            # 若单元数大于两个并且最后一个是未占用单元说明同时具有已占用单元和未占用单元，
            # 那么可以是上一个占用的单元继续侵占未占用的单元，或者新的占用者进行侵占。
            if mar_cell.sid is None:
                if len(self.__cells) > 1:
                    prv_cell = self.__cells[-2]

                    # 更新上一个占用单元。
                    prv_cell.end = incr_end

                    # 如果现在的单元与上一个单元的占用者ID（下载源ID）一致就刷新上一个单元继续侵占未占用单元，
                    # 否则将新建新的占用者来侵占未占用单元。
                    # 至于界限的准确度会通过在切换占用者的时候进行更新，也就是将交由在切换处进行更新。
                    if sid == prv_cell.sid:
                        # 如果已经全部被占用就移除最后的sid为None的单元。
                        if incr_end and incr_end == self.length:
                            self.__cells.pop()
                    else:
                        # 由于需要控制台来实现在切换占用者的时候进行刷新的，所以这里面就要把
                        # 距离上一次刷新完成的全部划分给上一个占用者单元，并插入新的占用者的单元。
                        self.__cells.insert(-1, CellRange(sid, incr_end, incr_end))

                else:
                    # 这种情况说明只有未占用单元。这种情况必须要新建新的占用单元。
                    self.__cells.insert(-1, CellRange(sid, incr_end, incr_end))

                # 无论如何都需要更新未占用单元。
                mar_cell.begin = incr_end
                mar_cell.end = self.length

            else:
                # 若最后一个单元不是未占用单元，那么说明下载块已经被占用完了。
                # 刷新最后一块。
                pass

    def __snapshot__(self):
        progress = self.progress.__snapshot__()
        cells = [c.dict() for c in self.cells]
        return {
            'cells': cells,
            'progress': progress
        }

    def __repr__(self):
        return '<Block [{}-{}]> {:.2%}'.format(self.begin, self.end, self.progress.percent / 100)


class BlockManager(Component):
    """ 下载块管理器。 """
    __slots__ = '_all', 'unit_size', 'total', 'map_size', '_timer', 'realtime_speed_capture', '__lock'

    def __init__(self, unit_size, map_size, increment_time=0):
        self._all = []
        self.unit_size = unit_size
        try:
            self.total = int(ceil(map_size / unit_size))
        except (TypeError, OverflowError):
            self.total = 1
        self.map_size = map_size

        self._timer = Timer(increment_time)

        self._realtime_speed_capture = RealtimeSpeed()
        self.__lock = Lock()

    def get_all(self):
        """ 返回所有的下载块对象。 """
        return self._all

    @property
    def realtime_speed(self):
        """ 实时下载速度。 """
        return self._realtime_speed_capture.get_speed()

    @property
    def average_speed(self):
        """ 平均下载速度。 """
        return self.incr_go / (self._timer.get_time() or float('inf'))

    @property
    def incr_go(self):
        """ 已下载字节数。 """
        return sum((v.progress.increment_go for v in self._all))

    @property
    def incr_done(self):
        """ 已缓存的字节数。"""
        return sum((v.progress.increment_done for v in self._all))

    @property
    def remaining_length(self):
        """ 还剩余字节数。 """
        return self.map_size - self.incr_go

    @property
    def remaining_time(self):
        """ 估计剩余时间。 """
        realtime_speed = self.realtime_speed
        if not realtime_speed:
            return float('inf')
        return self.remaining_length / self.realtime_speed

    @property
    def finish_go_flag(self):
        for b in self._all:
            if not b.progress.finish_go_flag:
                return False
        return not self.integrity_check()

    @property
    def finish_flag(self):
        for b in self._all:
            if not b.progress.finish_done_flag:
                return False
        return not self.integrity_check()

    def refresh_realtime_speed(self):
        """ 实时速度快照。 """
        self._realtime_speed_capture.refresh(self.incr_go)

    def insert(self, client, progress, relative_cells=None):
        """ 插入下载块。 """
        with self.__lock:
            block = Block(client, progress, self.unit_size, relative_cells=relative_cells)

            # 将下载块按位置顺序排序
            for i, v in enumerate(self._all):
                if v.begin > block.begin:
                    self._all.insert(i, block)
                    break
            else:
                self._all.append(block)

        return block

    def find_room_for_new_block(self):
        """ 搜索剩余下载量最大的下载块。 """
        block = sorted(self._all, key=lambda i: i.margin, reverse=True)[0]
        margin_len = block.margin
        put_begin = block.begin + (block.length - margin_len) + int(ceil(margin_len / 2))
        put_end = block.end

        return block, (put_begin * self.unit_size, put_end * self.unit_size)

    def activate(self):
        """ 激活下载块映射图。 """
        self._timer.start()
        self._realtime_speed_capture.start(self.incr_go)

    def deactivate(self):
        """ 关闭下载块映射图。 """
        self._timer.stop()
        self._realtime_speed_capture.stop()

    def integrity_check(self):
        """ 下载块映射图完整性检测。
        如果下载块缺失返回缺失的块，否则返回[]。
        """
        missing = []
        with self.__lock:
            prv_end = self._all[0].end

            for v in self._all[1:]:
                v.refresh()
                if v.begin - prv_end > 0:
                    # 如果下一个下载块的起点索引比上一个下载块的结束索引要大，说明了这其中缺少了一块。
                    missing.append((prv_end, v.begin))
                elif v.begin - prv_end < 0:
                    # 如果下一个下载块的起点索引比上一个下载块的结束索引要小，说明这出现了下载块范围交叉。
                    # 理论上这是不会出现的问题。
                    raise ValueError(v.begin, prv_end)
                # else:
                    # 如果是刚好相同说明了这是衔接的，期望情况。
                    # pass

                prv_end = v.end

        return missing

    def find_client(self, client):
        """ 通过客户端找到对应的下载块对象。"""
        for blo in self._all:
            if client is blo.client:
                return blo

        return None

    def locate(self, index):
        """ 通过下载单元索引到对应的下载块的单元CellRange。 """
        assert type(index) is int

        if index >= self.total:
            raise IndexError('索引 %d 超出下载块映射图的范围。' % index)

        for b in self._all:
            if b.begin <= index < b.end:
                return b[index - b.begin]

        raise IndexError()

    def __getitem__(self, index):
        """ 索引下载块。 """
        assert type(index) is int
        return self._all[index]

    def __iter__(self):
        """ 迭代返回下载块对象。"""
        return iter(self._all)

    def __snapshot__(self):
        with self.__lock:
            ret = {
                'all': [b.__snapshot__() for b in self._all],
                'increment_time': self._timer.get_time()
            }
        return ret


