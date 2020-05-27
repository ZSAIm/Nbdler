import os


class File:
    __slots__ = 'name', 'path', 'size'

    def __init__(self, path, name, size):
        """
        :param
            path    : 文件路径（不包括文件名）
            name    : 文件名称
            size    : 文件大小
        """
        self.name = name
        self.path = path
        self.size = size

    @property
    def extension(self):
        return os.path.splitext(self.name)[-1]

    @property
    def pathname(self):
        return os.path.join(self.path, self.name)

    def number_name(self, number):
        just_name, ext = os.path.splitext(self.name)
        return f'{just_name}({number}){ext}'

    def __repr__(self):
        return f'<File {self.pathname}>'

    def dumps(self):
        return {
            'path': self.path,
            'name': self.name,
            'size': self.size,
        }
