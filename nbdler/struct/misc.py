from collections import namedtuple

Slice = namedtuple('_Slice', 'client range')
InitialResult = namedtuple('_InitialResult', 'client filename filesize unspecified_size response')
ClientException = namedtuple('_ClientException', 'client exception')
SignalQueue = namedtuple('SignalQueue', 'id queue')
ProcessInfo = namedtuple('ProcessInfo', 'name pid ident')


class RangeFormat:
    def __init__(self, rangef):
        self._full_formats = rangef

        self._queryf = {}
        self._headerf = {}

        for i, j in self._full_formats.items():
            if i[0] != '&':
                self._headerf[i] = j
            else:
                self._queryf[i] = j

    def _format(self, range, dict):
        retitem = dict.copy()
        for i, j in dict.items():
            begin = range[0]
            end = range[1] or ''
            end_with = range[1] - 1 if range[1] is not None and range[1] > 0 else ''
            length = (range[1] or 0) - range[0]
            retitem[i] = j.format(begin=begin, end=end, end_with=end_with, length=length)
        return retitem

    getheader = lambda self, range: RangeFormat._format(self, range, self._headerf)

    getquery = lambda self, range: RangeFormat._format(self, range, self._queryf)

    def __iter__(self):
        return iter(self._full_formats.items())