
import asyncio


class AbstractClient:
    """ 抽象客户端

    Class Variable:
        NAME: 客户端名称，作为客户端的唯一标识
        PROTOCOL_SUPPORT: 客户端支持处理的协议, protocol/scheme
        ASYNC_EXECUTE: 指定客户端的是否为异步实现
        TIMEOUT: 客户端默认的连接connect,读取read超时参数
    """

    TIMEOUT = 10

    def __init__(self, session,
                 source_uri,
                 progress,
                 resume_capability,
                 **kwargs):
        """
        Args:
            session: 客户端会话
            source_uri: 下载源SourceUri对象
            progress: 请求进度对象Progress
            resume_capability: 是否支持断点续传，若为None则代表不确定，连接后将根据实际情况赋值
        """
        self.source_uri = source_uri
        self.progress = progress
        self.resume_capability = resume_capability
        self.kwargs = kwargs

        self._closed = False
        self.session = session
        self.resp = None

    async def connect(self):
        """ (可定义非异步方法)客户端连接

        Returns:
            UriResponse对象，该对象指定了资源的基本信息。
        """
        raise NotImplementedError

    async def fetch(self):
        """ (可定义非异步方法)客户端循环获取数据 """
        raise NotImplementedError

    async def pause(self):
        """ 客户端暂停 """
        self._closed = True
        raise NotImplementedError

    async def close(self):
        raise NotImplementedError

    async def run(self):
        raise NotImplementedError

    async def __aenter__(self):
        """ 异步with enter.

        进入客户端，准备开始客户端。
        该方法不应该执行非异步的长耗时任务。

        Returns:
            返回自身对象self
        """
        self._closed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """ 异步with exit.

        退出客户端，做必要的链接关闭操作，设置实例变量_closed=True。
        """
        coro_or_result = self.close()
        # 兼容异步关闭链接方法
        if asyncio.iscoroutine(coro_or_result):
            await coro_or_result
        self.session = None
        self._closed = True

    def __enter__(self):
        """ 同步with enter.

        进入客户端，准备开始客户端。
        该方法不应该执行非异步的长耗时任务。

        Returns:
            返回自身对象self
        """
        self._closed = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        self.session = None
        self._closed = True

    @classmethod
    def dlopen(cls, source, progress, **kwargs):
        raise NotImplementedError

    def __repr__(self):
        status = 'running'
        if self._closed:
            status = 'closed'
        name = self.run.__globals__['NAME']
        support = self.run.__globals__['PROTOCOL_SUPPORT']
        is_async = self.run.__globals__['ASYNC_EXECUTE']
        return f'<Client {status} name="{name}" ' \
               f'support={support} ' \
               f'async={is_async}>'


def noop():
    """ ignore function. """
    return None


NAME = 'abstract'
PROTOCOL_SUPPORT = ('http', 'https')
ASYNC_EXECUTE = True

ClientSession = noop
ClientHandler = AbstractClient
