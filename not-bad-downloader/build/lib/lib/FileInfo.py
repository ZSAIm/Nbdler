# -*- coding: UTF-8 -*-

import time, os
from contentType import content_type

class FileInfo(object):
    def __init__(self):

        self.path = u''
        self.name = None
        self.size = None

        # self.object = None
        self.exist = False
        self.force = False
        self.closed = False

    def make_name(self, urlinfo, filename=None):
        """  """

        t = urlinfo.url.split('?')[0].split('/')[-1]

        if t == '':
            self.name = unicode(str(int(time.time())))
            # make name by time
        else:
            self.name = unicode(t)

        self.name += unicode(content_type(urlinfo.content_type))

        # abc. X     ab.c _/
        if filename is not None:
            if '.' not in filename or filename.split('.')[-1] == '':
                try:
                    self.name = unicode(filename + self.name[self.name.rindex('.'):])
                except ValueError:
                    self.name = unicode(filename)
            else:
                self.name = unicode(filename)
        if not self.force:
            self.validate_name()


    def make_file(self):

        if self.path is not u'' and not os.path.exists(unicode(self.path)):
            os.makedirs(unicode(self.path))

        with open(os.path.join(unicode(self.path), unicode(self.name + u'.download')), 'wb') as f:
            # print self.size
            f.seek(self.size - 1)
            f.write(b'\x00')

    def validate_name(self):
        _name = unicode(self.name)
        # _path_name = unicode(os.path.join(self.path, self.name))
        _path = unicode(self.path)

        _count = 0
        while True:
            if _count != 0:
                if u'.' in _name:
                    dot_index = _name.rindex(u'.')
                    if os.path.exists(os.path.join(_path, u'%s(%d)%s' % (_name[:dot_index], _count, _name[dot_index:]))):
                        _count += 1
                        continue
                    self.name = u'%s(%d)%s' % (_name[:dot_index], _count, _name[dot_index:])
                    break
                    # return u'%s(%d)%s' % (_name[:dot_index], _count, _name[dot_index:])

                else:
                    if os.path.exists(os.path.join(_path, u'%s(%d)' % (_name, _count))):
                        _count += 1
                        continue
                    self.name = u'%s(%d)' % (_name, _count)
                    # return u'%s(%d)' % (_name, _count)
                    break
            else:
                if not os.path.exists(os.path.join(_path, self.name)):
                    self.name = _name
                    # return _name
                    break
                else:
                    _count += 1

    # def dump(self):
    #     _dump_dict = dict(
    #         path=self.path,
    #         name=self.name,
    #         size=self.size,
    #         exist=self.exist,
    #         force=self.force,
    #     )
    #
    #     return _dump_dict
    #
    # def load(self, _data):
    #     _type = [list, int, str, tuple, int, bool, float, long, dict]
    #
    #     for i, j in _data.items():
    #         for k in _type:
    #             if isinstance(getattr(self, i), k) is True:
    #                 break
    #         else:
    #             if j is not None:
    #                 getattr(self, i).load(j)
    #                 continue
    #
    #         setattr(self, i, j)

    def close(self):
        self.closed = True