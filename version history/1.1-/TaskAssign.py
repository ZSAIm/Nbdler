

class TaskAssign:
    def __init__(self, server_set, GlobalProg, DLMobj):


        self.DLMobj = DLMobj
        self.file_size = self.DLMobj.file.size
        self.GlobalProg = GlobalProg
        self.BLOCK_SIZE = self.DLMobj.BLOCK_SIZE
        self.server_set = server_set

        self.thread_count = self.DLMobj.thread_count



    def free_block(self):
        """GlobalProgress.map"""

        free_list = []
        _begin = None
        for index, value in enumerate(self.GlobalProg.map):
            if value is None:
                if _begin is None:
                    _begin = index
            else:
                if _begin is not None:
                    free_list.append((_begin, index))
                    _begin = None
        else:
            if _begin is not None and _begin != len(self.GlobalProg.map) - 1:

                free_list.append((_begin, len(self.GlobalProg.map) - 1))

        return free_list

    def block_to_range(self, block_range):
        """find the widest space to be the new thread download range"""

        if block_range == []:
            return [[None, None]]
        li = sorted(block_range, key=lambda x: (x[1] - x[0]), reverse=True)
        # max_range = li[-1]
        # print li
        _blocks = []
        for i in li:
            if i[0] == 0:
                _begin_pos = 0
            else:
                _begin_pos = (i[1] + i[0]) * self.BLOCK_SIZE / 2.0
                _begin_pos = int(_begin_pos - _begin_pos % self.BLOCK_SIZE)
                if _begin_pos == i[0] * self.BLOCK_SIZE:
                    _begin_pos += self.BLOCK_SIZE

            if i[1] == len(self.GlobalProg.map) - 1:
                _end_pos = self.DLMobj.file.size
            else:
                _end_pos = i[1] * self.BLOCK_SIZE
            _range = [_begin_pos, _end_pos]

            if _range[0] == _range[1]:
                _range = [None, None]
            _blocks.append(_range)

        return _blocks




    def assign(self):

        _ranges_ = self.block_to_range(self.free_block())


        _max_range = _ranges_[0]
        _range = _max_range

        # fetch appropriate server, which is the highest speed per thread.
        _dict = self.GlobalProg.getQueueServerMes()
        # print _dict.values()
        _server = None
        if len(_dict) >= len(self.server_set):
            _speed_up = sorted(list(_dict.items()), key=lambda x: x[1]['SPEED'] / x[1]['COUNT'])
            _server = _speed_up[-1][0]
        else:
            for i in self.server_set:
                if i not in _dict.keys():
                    _server = i
                    break

        if len(self.GlobalProg.queue) != 0 and None not in _range:

            _parent_progress = self.GlobalProg.get_parent_prog(_range)
            _range = _parent_progress.clip_range_req(_range)


        if _server is None:
            _server = self.server_set[0]
        if None not in _range:
            self.GlobalProg.map[int(_range[0] / self.BLOCK_SIZE)] = self.server_set.index(_server)

        return _server, _range
