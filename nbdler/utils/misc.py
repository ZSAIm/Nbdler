# -*- coding: UTF-8 -*-


class BaseInfo:
    """ 基本信息对象。 """

    def __iter__(self):
        return iter(self.dict().items())

    def dict(self, dictify_all=False):
        """ dictify_all : 当为True的时候字典化所有的BaseInfo对象。 """

        d = dict(self.__dict__)
        if dictify_all:
            d = _dictify(d)
        return d


def _dictify(obj):
    """ 递归字典化所有的BaseInfo对象。 """
    if isinstance(obj, BaseInfo):
        v = obj.dict(True)
    elif isinstance(obj, dict):
        # 由于BaseInfo的dict取自于__dict__，所以字典的键只能是字符串。
        v = {i: _dictify(j) if not isinstance(j, BaseInfo) else _dictify(j) for i, j in obj.items()}
    elif type(obj) in (list, tuple):
        v = [_dictify(i) if not isinstance(i, BaseInfo) else _dictify(i) for i in obj]
    else:
        v = obj
    return v


class Component(object):
    """ 下载器的基本组件。 """
    def __snapshot__(self):
        """ 组件数据快照。 """

