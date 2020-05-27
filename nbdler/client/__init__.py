

from . import aiohttp, requests
from .abstract import AbstractClient
from collections import defaultdict

__all__ = ['get_policy', 'ClientPolicy']

_solutions = defaultdict(list)
_name_solution = {}


class ClientPolicy:
    def __init__(self, **specified_mapping):
        self._specified = {k.lower(): v.lower() for k, v in specified_mapping.items()}

    def get_solution(self, protocol):
        """ 返回根据策略决定的客户端处理模块。
        Args:
            protocol: 要处理的协议

        Returns:
            返回客户端处理方案
        """
        sol_name = self._specified.get(protocol, None)
        if sol_name is None:
            # 使用该协议最新注册的客户端处理器作为默认的处理策略
            sol_name = _solutions.get(protocol, [None])[-1]
        if sol_name is None:
            raise NotImplementedError(f'没有找到协议{protocol}的处理策略。')
        solution = _name_solution.get(sol_name, None)
        if solution is None:
            raise NotImplementedError(f'没有找到名称为{sol_name}的客户端处理器。')
        return solution

    def __iter__(self):
        return iter(self._specified.items())


class ProtocolSolution:
    def __init__(self, module):
        self._module = module

    @property
    def name(self):
        return self._module.NAME

    @property
    def supported_protocols(self):
        return self._module.PROTOCOL_SUPPORT

    def is_async(self):
        return self._module.ASYNC_EXECUTE

    @property
    def dlopen(self):
        return self._module.ClientHandler.dlopen

    @property
    def adlopen(self):
        return self._module.ClientHandler.adlopen

    def get_client(self, *args, **kwargs):
        return self._module.ClientHandler(*args, **kwargs)

    def get_session(self, *args, **kwargs):
        return self._module.ClientSession(*args, **kwargs)


def get_policy(**kwargs):
    return ClientPolicy(**kwargs)


def register(module):
    """ 注册下载客户端处理模块。

    客户端模块规范：
    1. 客户端处理程序要求继承abstract_base.py中的AbstractClient类
    2. 使用类变量NAME作为客户端的唯一标识名称，尽量避免与其他客户端重名，
        重名的处理策略是后注册覆盖前注册。
    3. 使用ClientHandler作为客户端的类名，或通过赋值该模块变量名实现
    4. 使用ClientSession作为客户端会话，必须存在该变量，若不需要会话则赋值noop函数，
        客户端会话创建不提供参数，若需要提供使用functions.partial传递定义

    Args:
        module: 协议处理解决方案

    """
    global _solutions, _name_solution
    solution = ProtocolSolution(module)
    for protocol in solution.supported_protocols:
        _solutions[protocol].append(solution.name)
        _name_solution[solution.name] = solution


def main():
    # 多线程HTTP/HTTPS，使用requests库
    register(requests)
    # 异步HTTP/HTTPS，使用aiohttp库
    register(aiohttp)


# 注册下载客户端
main()



