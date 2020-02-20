Nbdler
===============
[![Build Status](https://img.shields.io/badge/build-passing-green.svg)](https://github.com/ZSAIm/Nbdler)
[![Build Status](https://img.shields.io/badge/pypi-v2.0.0-blue.svg)](https://pypi.org/project/Nbdler/)

Nbdler 是使用Python编写的下载器。


# 特征

* 支持断点续传。
* 支持多线程分片下载。
* 支持多来源地址下载。
* 支持以子进程模式运行。
* 具有下载任务管理器。


# 安装

    $ pip install Nbdler

# 例子

## 简单下载任务(Downloader)
```python
from nbdler import dlopen, Request

request = Request('https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe', max_thread=32,
                  file_path='./微信安装包.exe')
dl = dlopen(request)
dl.start()
```

### 获取实时下载信息
```python
# :::::下载实时信息
# 实时下载速度
dl.realtime_speed()
# 平均下载速度
dl.average_speed()
# 剩余下载长度
dl.remaining_length()
# 剩余估计下载事件
dl.remaining_time()
# 已下载长度
dl.increment_go()
# 已写入文件长度
dl.increment_done()

# :::::下载实体信息（以字典形式返回）
# 文件路径长度等信息
dl.body.file
# 下载源信息
dl.body.url
# 下载配置信息
dl.body.config
# 返回所有实体信息
dl.body.all
# 下载块信息()
# 返回指定索引n的下载块
dl.body.block_mgr[n]
# 返回所有的下载块信息
dl.body.block_mgr.get_all()
```

### 下载任务操作/状态
```python
# :::::下载任务操作
# 开始（继续）下载任务
dl.start()
# 暂停下载任务
dl.pause()
# 关闭下载任务，任务成功完成后的关闭处理。
dl.close()
# 配置下载文件信息
dl.config()
# 速度限制为最大n字节每秒
dl.speed_limit(n)
# 阻塞至下载任务运行结束。
dl.join()
# 异常错误敏感的下载任务阻塞。下载异常错误会通过调用这个方法抛出。
dl.trap()

# :::::下载状态
# 下载任务是否运行中
dl.is_alive()
# 下载任务是否已完成
dl.is_finished()
```

## 下载管理器(Manager)
```python
from nbdler import Manager, Request

# 设置最大同时下载任务数量n
mgr = Manager(maxsize=n)
request1 = Request('https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe', max_thread=32,
                   file_path='./微信安装包1.exe')
request2 = Request('https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe', max_thread=32,
                   file_path='./微信安装包2.exe')

id1 = mgr.putrequest(request1)
id2 = mgr.putrequest(request2)
mgr.start()
```

### 获取当前运行中的下载任务实时信息
```python
# :::::下载实时信息
# 实时下载速度
mgr.realtime_speed()
# 平均下载速度
mgr.average_speed()
# 剩余下载长度
mgr.remaining_length()
# 剩余估计下载事件
mgr.remaining_time()
# 已下载长度
mgr.increment_go()
# 已写入文件长度
mgr.increment_done()
# 以字典形式获取以上所有实时信息
mgr.realtime_info()

# :::::下载实体信息（以字典形式返回）
# 文件路径长度等信息
mgr.body.file
# 下载源信息
mgr.body.url
# 下载配置信息
mgr.body.config
# 返回所有实体信息
mgr.body.all
# 以字典形式获取以上所有实体信息
mgr.body_info()
# 下载块信息()
# 返回指定索引n的下载块
mgr.body.block_mgr[n]
# 返回所有的下载块信息
mgr.body.block_mgr.get_all()

```

### 获取指定任务ID的信息
```python
# 返回任务ID为n的任务的实时速度。
mgr[n].realtime_speed()
# 返回任务ID为n和m的实时速度总和。
mgr[n, m].realtime_speed()
# 返回所有下载任务的实时速度
mgr[-2].realtime_speed()
```

### 下载管理器的运行队列信息
```python
# :::::运行队列
# 已入列待下载任务ID列表
mgr.queue.enqueued
# 运行中的任务ID列表
mgr.queue.running
# 已结束的任务ID列表
mgr.queue.dequeued
# 处于未确定队列的任务ID列表（正在dlopen打开过程中）
mgr.queue.unsettled

# :::::状态队列
# 已就绪的任务ID列表
mgr.queue.ready
# 已暂停的任务ID列表
mgr.queue.paused
# 正在dlopen打开下载任务的ID列表
mgr.queue.opening
# 已开始的下载任务ID列表
mgr.queue.started
# 发生错误并且已结束的任务ID列表
mgr.queue.error
# 已完成下载的任务ID列表
mgr.queue.finished
```


# 许可证
Apache-2.0

# 更新日志

### 2.0.0
- 重构

### 1.0.1
- 修复一些bug。

### 0.9.9
- 重构。
- 添加多进程下载支持。

### 0.0.1
- 上传代码。

 
