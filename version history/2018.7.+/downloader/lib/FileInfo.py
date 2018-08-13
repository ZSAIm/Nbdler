# -*- coding: UTF-8 -*-

import time, os
from contentType import content_type

class FileInfo(object):
    def __init__(self):

        self.path = ''
        self.name = None
        self.size = None

        self.object = None
    def make_name(self, urlinfo, filename=None):
        """  """

        t = urlinfo.url.split('?')[0].split('/')[-1]

        if t == '':
            self.name = str(int(time.time()))

            self.name += content_type(urlinfo.content_type)

            # make name by time
        else:
            self.name = t
            try:
                self.name += content_type(urlinfo.content_type)
            except KeyError:
                pass


        # abc. X     ab.c _/
        if not filename:
            return
        if '.' not in filename or filename.split('.')[-1] == '':
            try:
                self.name = filename + self.name[self.name.rindex('.'):]
            except ValueError:
                self.name = filename
        else:
            self.name = filename

    def make_file(self):

        if self.path and not os.path.exists(self.path.decode('UTF-8')):
            os.makedirs(self.path)
        self.path = self.path.replace(r'\\', '/')
        try:
            if self.path[-1] != '/':
               self.path = self.path + '/'
        except:
            pass
        # print self.path + self.name

        with open((self.path + self.name + '.download').decode('UTF-8'), 'wb') as f:
            f.seek(self.size - 1)
            f.write(b'\x00')
