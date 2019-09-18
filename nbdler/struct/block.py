
from math import ceil
from collections import namedtuple
from nbdler.utils.thread import RLock
from nbdler.struct.dump import BlockDumpedData

try:
    xrange
except NameError:
    xrange = range

GridCell = namedtuple('GridCell', 'id begin end')


class Block:
    def __init__(self, content, progress, blocksize, abs_grid=None, rel_grid=None):
        self._content = content
        self._prog = progress
        self._blocksize = blocksize

        self._range = (int(progress.range[0] / blocksize),
                       int(ceil(progress.range[1] / blocksize)) if progress.range[1] else 1)
        if abs_grid:
            rel_grid = list([GridCell(id=i.id, begin=i.begin - self.begin, end=i.end - self.begin)
                             for i in abs_grid])
        if not rel_grid:
            rel_grid = [GridCell(id=None, begin=0, end=self.length)]

        self._rel_grid = rel_grid
        self._correct_lock = RLock()
        self.calibration()

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
    def grid(self):
        """ Grid's cells with relative position. """
        self.calibration()
        return self._rel_grid

    @property
    def abs_grid(self):
        """ Grid's cells with absolute position. """
        return [GridCell(id=c.id, begin=self.begin+c.begin, end=self.end+c.begin) for c in self.grid]

    @property
    def handler(self):
        return self._content.run

    @property
    def margin(self):
        margin_cell = self.grid[-1]
        try:
            if margin_cell.id is None:
                h = margin_cell.end - margin_cell.begin
            else:
                h = 0
        except TypeError:
            h = float('inf')
        return h

    def calibration(self):
        if self._blocksize != float('inf'):
            with self._correct_lock:
                self._correct_range()
                self._correct_grid()

    def __contains__(self, item):
        return item == self._content

    def _correct_grid(self):
        prog = self._content.getprogress()
        source = self._content.getsource()
        x_end = int(ceil(prog.go_inc / self._blocksize))
        margin_cell = self._rel_grid[-1]
        new_margin = GridCell(id=None, begin=x_end, end=self.length)
        if len(self._rel_grid) > 1:
            prv_cell = self._rel_grid[-2]
            if prv_cell.id == source.id:
                self._rel_grid[-2] = GridCell(id=source.id, begin=prv_cell.begin, end=x_end)
                if x_end == margin_cell.end:
                    self._rel_grid.pop(-1)
                else:
                    self._rel_grid[-1] = new_margin
            else:
                self._rel_grid.insert(-2, GridCell(id=source.id, begin=margin_cell.begin, end=x_end))
                self._rel_grid[-1] = new_margin
        else:
            self._rel_grid.insert(-2, GridCell(id=source.id, begin=0, end=x_end))
            self._rel_grid[-1] = new_margin

    def _correct_range(self):
        self._range = (self._range[0],
                       int(ceil(self._prog.end / self._blocksize)))

    def send_signal(self, signal):
        self._content.send_signal(signal)

    def release_buffer(self, fp):
        self._content.write_to_file(fp)

    clear_signal = property(lambda self: self._content.clear_signal, lambda self, v: None, None, '')

    getavgspeed = property(lambda self: self._prog.getavgspeed, lambda self, v: None, None, '')

    getinstspeed = property(lambda self: self._prog.getinstspeed, lambda self, v: None, None, '')

    getsource = property(lambda self: self._content.getsource, lambda self, v: None, None, '')

    clear = property(lambda self: self._prog.clear, lambda self, v: None, None, '')

    is_go_finished = lambda self: self._prog.go_finishflag

    is_finished = lambda self: self._prog.finishflag

    get_byte_left = lambda self: self._prog.go_remain

    get_go_inc = lambda self: self._prog.go_inc

    def __repr__(self):
        self.calibration()
        return "<%d>[%d-%d](%d-%d) - %s/%s" % (self.getsource().id, self.begin, self.end,
                                               self._prog.begin, self._prog.end, self.is_go_finished(),
                                               self.is_finished())

    def dump_data(self):
        return BlockDumpedData(rel_grid=tuple([tuple(i) for i in self.grid]), url_id=self.getsource().id,
                               progress=tuple(self._prog.dump_data()))


