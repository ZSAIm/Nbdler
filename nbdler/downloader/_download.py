# -*- coding: UTF-8 -*-
"""
事件流程:

+----------------------------------------------------------------------------------+
|                                                                                  |
|                                   Console                                        |
|                                                                                  |
+- raise_exception ----------------- pause ----------------------------------------+
|            ^                              |                                      |
|            | EVT_TASK_ERROR               | EVT_TASK_PAUSING                     |
|            |                              |                                      |
|            |    v-------------------------<                                      |
|            |    |                                                                |
|    +------------|-----+                                  +------------------+    |
|    |            v     |                                  |                  |    |
|    |  EVT_TASK_PAUSED |                                  |                  |    |
|    |            |     |                                  |                  |    |
|    |            v     |  <----- EVT_BLOCK_RETRY -------  |                  |    |
|    | EVT_TASK_SHUTDOWN|  ------- submit_block -------->  |                  |    |
|    |     ^            |                                  |                  |    |
|    |     |     v---------<----- EVT_BLOCK_FINISH ------  |                  |    |
|    |     |     ?>-------->----- EVT_TASK_SLICE ------->  |                  |    |
|    |     |     v      |                                  |                  |    |
|    |  EVT_TASK_FINISH |                                  |                  |    |
|    |                  |                                  |                  |    |
|    |                  |  ------ EVT_TASK_SLICE ------->  |                  |    |
|    |                  |  <----- EVT_TASK_SLICE --------  |                  |    |
|    |   <con_worker>   |                                  |  <cli_workers>   |    |
|    |                  |  <----- EVT_URL_STATUS --------  |                  |    |
|    |                  |  --?>-- EVT_CLIENT_SWITCH ---->  |                  |    |
|    |                  |     >-- EVT_CLIENT_WAIT ------>  |                  |    |
|    |                  |                                  |                  |    |
|    |                  |  <---- EVT_BUFFER_COUNT -------  |                  |    |
|    +------------------+                                  +------------------+    |
|             |  EVT_BUFFER_RELEASE                                                 |
|             v                                                                    |
|    +------------------------------------------------------------------------+    |
|    |                             <buff_worker>                              |    |
|    +------------------------------------------------------------------------+    |
+----------------------------------------------------------------------------------+
"""
from ..utils.eventdriven import MappingBlueprint, session as sess, EVT_DRI_TIMING
from nbdler.event import (EVT_BUFFER_COUNT, EVT_BUFFER_RELEASE, EVT_BLOCK_RETRY, EVT_BLOCK_FINISH, EVT_TASK_PAUSING,
                          EVT_TASK_ERROR, EVT_TASK_FINISH, EVT_TASK_SHUTDOWN, EVT_TASK_PAUSED, EVT_TASK_SLICE,
                          EVT_URL_STATUS, EVT_URL_UNAVAILABLE, EVT_URL_GAIERROR,
                          EVT_URL_NORMAL, EVT_URL_TIMEOUT, EVT_URL_UNKNOWN)
from ..error import (URLUnknownError, URLTimeoutError, URLCriticalError, NetworkBrokenError, MissingBlockError)
from .struct.progress import Progress
from .client import get_client
import gc


buffer_model = MappingBlueprint()
console_model = MappingBlueprint()
client_model = MappingBlueprint()

# ====================================================
# <buff_worker> 缓存控制器事件处理函数。
#
# public:
#     sess['self']          :   控制器自身
#     sess['storage']       :   缓存信息BufferInfo对象
#     sess['cfg']           :   控制台配置
#     sess['con']           :   控制台
#     sess['file']          :   File对象
#
# ====================================================


@buffer_model.register(EVT_BUFFER_RELEASE)
def __release__():
    """ 释放缓存到文件。
    :private
        sess['val']   :   None

    :from
        EVT_BUFFER_COUNT : 缓存容器溢出时
        EVT_TASK_FINISH  : 任务下载完成时
        EVT_TASK_PAUSED  : 任务下载暂停后
    """
    # 释放下载缓冲。
    sess['storage'].release(sess['file'])
    # 保存下载配置信息。
    sess['con'].dump()
    # 手动执行垃圾回收。
    gc.collect()


# ==============================================
# 控制台控制器事件处理函数。
#
# public:
#     sess['self']       : 控制器自己
#     sess['con']        : 控制台
#     sess['cfg']        : 控制台配置信息
#     sess['url']        : Url对象
#     sess['file']       : File对象
#     sess['buff_worker']: 下载缓存控制器
#     sess['storage']    : 下载缓冲存储器
#     sess['block_mgr']  : 下载块管理器
#     sess['cli_workers']: 下载池
#     sess['working']    : 正在下载的下载块。
#     sess.leftover      : 未完成的下载块队列
#
# private:
#     from console:
#         pass
#
#     from client:
#         sess.blo   : 发起客户端
#
#     from cli_workers:
#         pass
#
# ==============================================

@console_model.register(EVT_BUFFER_COUNT)
def __count__():
    """ 一级缓存计数。
    私有上下文：
        sess['val']    :   下载缓存数据
        sess.blo       :   请求缓存的progress对象

    来源:
        下载块客户端缓存溢出后，由客户端发起缓存计数存储
    """
    sess['storage'].store(sess.blo.progress, sess['val'])
    # 检查下载缓冲存储器是否溢出，如果溢出了就进行释放。
    if sess['storage'].check(sess['cfg'].max_buff):
        # 如果缓存控制器处于空闲状态才让其进行释放，避免缓存满后不断的发送释放信号。
        if sess['buff_worker'].is_idle():
            sess['buff_worker'].dispatch(EVT_BUFFER_RELEASE)


@console_model.register(EVT_BLOCK_FINISH)
def __block_finish__():
    """ （客户端控制器发起）客户端退出事件响应。
    :private
        sess.blo : 发起的客户端的下载块

    :from
        下载块完成事件后，由客户端发起下载块完成事件
    """
    # 移除已经完成的在工作队列的下载块客户端。
    sess['working'].remove(sess.blo)
    sess['url'].get(sess.blo.client.source.id).disuse()
    # 释放客户端的引用，以减少内存的占用，并且在之前进行最后的下载块信息刷新。
    sess.blo.refresh()
    sess.blo.client = None
    # 分片下载完成后，检查下载任务是否完成。
    if sess['block_mgr'].finish_go_flag:
        # 再次检查下载块映射图是否完整。
        missing = sess['block_mgr'].integrity_check()
        if not missing:
            # 所有下载块下载完成，通知控制台。
            if not sess['working']:
                sess['self'].dispatch(EVT_TASK_FINISH)
            return
        else:
            # 如果没有正在进行的下载块，但是存在下载空隙，那么出现了下载块缺失异常错误。
            if not sess['working']:
                sess['self'].dispatch(EVT_TASK_ERROR, MissingBlockError(missing))

    if sess['cfg'].partial:
        # 下载未完成，提交新的分片下载任务到下载客户端池。
        if sess.leftover:
            # 优先下载未完成的下载块。
            next_blo = sess.leftover.pop(0)
            sess['working'].append(next_blo)
            sess['url'].get(next_blo.client.source.id).use()
            next_blo.client.clean()
            submit_block(next_blo)
        else:
            # 搜索最大的剩余下载块，并请求其分割块。
            block, put_range = sess['block_mgr'].find_room_for_new_block()
            # 如果客户端已经删除了引用，说明已经完成了工作，那么就没必要继续切片
            if block.client:
                # 发送请求切片信号给客户端。
                block.client.slice_from(put_range)
    else:
        # 这里面理论上不会执行，但是这里会根据下载配置进行暂停或重试。
        sess['self'].dispatch(EVT_TASK_ERROR, AssertionError('Unknown Error'))
        assert False


@console_model.register(EVT_BLOCK_RETRY)
def __block_retry__():
    """ （客户端发起）客户端退出事件响应。
    :private
        sess.blo : 发起的客户端的下载块

    :from
        下载块客户端未完成结束后，由客户端发起请求重试
    """
    if not sess['con'].is_paused():
        if not sess['cfg'].partial:
            # 非partial请求需要重置下载进度。
            sess['storage'].clear()
            sess.blo.progress.reset()
        submit_block(sess.blo)

    else:
        # 由于暂停的原因不需要重试，所以可以把下载客户端从工作队列移除。
        sess['working'].remove(sess.blo)
        sess['url'].get(sess.blo.client.source.id).disuse()


@console_model.register(EVT_TASK_FINISH)
def __finish__():
    """ （控制台发起）下载任务完成事件响应。
    :private
        null

    :from
        EVT_BLOCK_FINISH : 所有下载块完成时
    """
    # 停止下载池客户端。
    sess['cli_workers'].shutdown()
    # 释放缓存，发送控制台关闭信号。
    sess['buff_worker'].dispatch(EVT_BUFFER_RELEASE)
    # 关闭下载器。
    _shutdown_downloader()
    sess['self'].dispatch(EVT_TASK_SHUTDOWN, True)


def _shutdown_downloader():
    """ (Con_worker Only)当暂停后和下载完成后关闭下载器。"""
    # 关闭下载块映射图。
    sess['block_mgr'].deactivate()
    # 关闭缓存控制器和控制台控制器。
    sess['buff_worker'].shutdown()
    sess['buff_worker'].wait()
    # 关闭文件对象。
    sess['file'].close()
    # 通知trap()的异常消息队列，控制台已关闭。
    sess['con'].raise_exception(None)


@console_model.register(EVT_TASK_SHUTDOWN)
def __shutdown__():
    """ （控制台发起）控制台准备关闭事件响应。
    :private
        null

    :from
        EVT_TASK_FINISH : 下载任务完成时
        EVT_TASK_PAUSED : 下载任务暂停后
    """
    # 关闭控制台控制器。
    sess['self'].shutdown()


@console_model.register(EVT_TASK_PAUSING)
def __pausing__():
    """ （控制台发起）下载任务开始暂停事件响应。
        :private
            null

        :from
            用户使用暂停方法pause/stop时，由控制台发起下载暂停事件
        """
    # 关闭限流器。
    sess['self'].adapters['semaphore'].close()
    # 停止所有的客户端。
    for blo in sess['working']:
        blo.client.pause()
    # 关闭下载池。
    sess['cli_workers'].shutdown()
    # 为了保证下载块的完整性，必须要处理完控制器的待处理事件队列，
    # 所以先确保停掉所有的下载客户端后避免继续产生新的事件。
    sess['cli_workers'].wait()
    # 由事件EVT_TASK_PAUSED来善后。
    sess['self'].dispatch(EVT_TASK_PAUSED)


@console_model.register(EVT_TASK_PAUSED)
def __paused__():
    """ 下载任务已暂停事件。"""
    # 释放下载磁盘缓存
    sess['buff_worker'].dispatch(EVT_BUFFER_RELEASE)
    # 关闭下载器。
    _shutdown_downloader()
    # 之后可以进行发送关闭下载器信号了。
    sess['self'].dispatch(EVT_TASK_SHUTDOWN, False)


@console_model.register(EVT_URL_STATUS)
def __url_status__():
    """ （客户端发起）客户端连接反馈事件响应。
    :private
        sess['val']  : 客户端连接状态
        sess.info    : 若连接成功，则返回响应，否则返回异常信息。
        sess.blo     : 客户端对象

    :from
        下载块客户端连接下载源时，由客户端发起的下载源连接状态事件
    """
    def success():
        # 在切换下载源如果客户端连接成功会得到反馈信息，
        # 为了保证下载块单位数据的准确性，这里需要刷新下载块状态。
        block.refresh()
        srcwrap.success()
        if not srcwrap.response:
            srcwrap.setresponse(*info)

    info = sess.info
    block = sess.blo
    source = block.client.source
    srcwrap = sess['url'].get(source.id)
    try:
        {
            EVT_URL_TIMEOUT: srcwrap.timeout,
            EVT_URL_UNAVAILABLE: srcwrap.unavailable,
            EVT_URL_UNKNOWN: srcwrap.unknown,
            EVT_URL_GAIERROR: srcwrap.network_broken,
            EVT_URL_NORMAL: success
        }[sess['val']]()
    except (URLCriticalError, URLTimeoutError, URLUnknownError, NetworkBrokenError) as e:
        if sess['cfg'].partial:
            # 当前下载源出现异常，切换下载源。
            srcwrap.disuse()
            next_warp = sess['url'].find_min_avl_used()

            if next_warp:
                next_warp.use()
            else:
                # 如果目前没找到合适可用的下载源，那么会强制切换下一个下载源。
                next_warp = sess['url'].get_next(srcwrap.id)
                if sess['url'].is_all_critical():
                    sess['self'].dispatch(EVT_TASK_ERROR, type(e)(info))
                else:
                    block.client.wait(1)
                next_warp.use_anyway()

            block.client.switch_to(next_warp.get())
        else:
            # 对于不允许部分下载的情况，这里会根据下载配置进行暂停或重试。
            sess['self'].dispatch(EVT_TASK_ERROR, type(e)(info))


@console_model.register(EVT_TASK_SLICE)
def __slice__():
    """ （客户端发起）客户端切片反馈事件响应。
    :private
        sess['val'] : 切片请求响应的范围元组 tuple.
        sess.blo    : 进行了切片的下载块

    :from
        控制台请求下载块切片时，由下载块客户端发起的生成新的下载分片事件
    """
    if sess['val']:
        # 取最合适的并且有效的下载源
        source_wrap = sess['url'].find_min_avl_used()
        if not source_wrap:
            # 如果没有最合适的那么无视限制选取连接数最少的下载源
            source_wrap = sess['url'].find_min_used()
        # 构建下载块
        progress = Progress(sess['val'])
        source = source_wrap.get()
        # 传递工作台额外的参数给客户端。
        options = {'timeout': sess['cfg'].timeout}
        options.update(sess['cfg'].options)
        cli = get_client(source.protocol)(source, progress, True, **options)
        block = sess['block_mgr'].insert(cli, progress)
        source_wrap.use()
        # 提交下载客户端给下载池。
        sess['working'].append(block)
        submit_block(block)


@console_model.register(EVT_DRI_TIMING)
def __timing__():
    """ （控制器发起）定时事件响应。用于实时速度的捕获和限速的信号量限制释放。
    :private
        sess['val'] : 定时器信号发生周期。

    :from
        控制台控制器定时插件发起的事件
    """
    if not sess['con'].is_paused():
        # 刷新实时速度。
        sess['block_mgr'].refresh_realtime_speed()
        # 控制限速器线流。
        if sess['cfg'].max_speed:
            # TODO ：实现更通用,更灵活的根据下载客户端的下载粒度进行限速。
            #        这里实现的是默认的HTTP/S客户端的下载粒度是8196（8KB）
            sess['self'].release(sess['cfg'].max_speed / (8196 / sess['val']))


@console_model.register(EVT_TASK_ERROR)
def __exception__():
    """ （控制台发起）任务下载发生异常。
    注意对于允许部分下载的任务，这个事件仅仅是用于通知作用，并不会停止下载器。
    :private
        sess['val'] : 异常消息。

    :from
        EVT_BLOCK_FINISH : 下载块下载完成出现的未知错误
        EVT_URL_STATUS   : 下载块客户端连接发生无法处理错误时
    """
    sess['con'].raise_exception(sess['val'])
    if not sess['cfg'].options.get('auto_retry', True):
        # 如果控制台配置成非自动重试，即auto_retry==False，那么将自动暂停下载。
        sess['con'].pause(block=False)


def submit_block(block):
    """ 提交下载块到下载工作池进行处理。 """
    sess['cli_workers'].submit(block.client.run, args=(sess['self'],), context={'blo': block})


# ====================================================
# 缓存控制器事件处理函数。
#
# public:
#     sess['con_worker']  : 控制台控制器
# ====================================================


@client_model.hook_after()
def __client_exit__():
    """ 客户端连接关闭退出。
    将交由控制台来控制接下来的操作。
    :private
        sess.blo     : 下载快对象

    :from
        下载块客户端处理任务退出时，控制器的处理后事件
    """
    if sess.blo.progress.finish_go_flag:
        sess['con_worker'].dispatch(EVT_BLOCK_FINISH, context={'blo': sess.blo})
    else:
        sess['con_worker'].dispatch(EVT_BLOCK_RETRY, context={'blo': sess.blo})
