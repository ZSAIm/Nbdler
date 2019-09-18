Nbdler
===============
[![Build Status](https://img.shields.io/badge/build-passing-green.svg)](https://github.com/ZSAIm/Nbdler)
[![Build Status](https://img.shields.io/badge/pypi-v1.0.0-blue.svg)](https://pypi.org/project/Nbdler/)

[Click here](https://github.com/ZSAIm/Nbdler/blob/master/README_EN.md) for the English version. 

Nbdler 是使用Python编写的 的HTTP/HTTPS下载器。

一个简短的例子：
*****

> 在用法上模仿了``urllib``的使用习惯。

```python
>>> import nbdler
>>> import time
>>> req = nbdler.Request(url='https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe')
>>> dl = nbdler.dlopen(req)
>>> fileinfo = dl.getfileinfo()
>>> fileinfo
FileInfo(name='WeChatSetup.exe', path='', size=44758872, block_size=524288)
>>> dl.start()
>>> while not dl.is_finish():
... 	print("instspeed: %f KB/S, remain_time: %f s, %d/%d" % (dl.getinstspeed()/1024, dl.get_remain_time(), dl.getincbyte(), fileinfo.size))
... 	time.sleep(1)
... else:
... 	print('download finished.')
instspeed: 21234.240212 KB/S, remain_time: 1.543446 s, 49152/44758872
instspeed: 2819.759705 KB/S, remain_time: 7.684911 s, 5160960/44758872
instspeed: 2770.697604 KB/S, remain_time: 9.182783 s, 8011776/44758872
instspeed: 2916.052060 KB/S, remain_time: 9.444060 s, 10797056/44758872
instspeed: 3010.630393 KB/S, remain_time: 9.092954 s, 13680640/44758872
instspeed: 2723.848368 KB/S, remain_time: 8.515533 s, 16564224/44758872
instspeed: 2891.365600 KB/S, remain_time: 7.860457 s, 19382272/44758872
instspeed: 2872.925135 KB/S, remain_time: 7.059829 s, 22290432/44758872
instspeed: 2676.442852 KB/S, remain_time: 6.241065 s, 25149440/44758872
instspeed: 2628.328905 KB/S, remain_time: 5.397935 s, 27983872/44758872
instspeed: 2915.214162 KB/S, remain_time: 4.533532 s, 30801920/44758872
instspeed: 2628.635096 KB/S, remain_time: 3.625203 s, 33669120/44758872
instspeed: 2727.497028 KB/S, remain_time: 2.702176 s, 36536320/44758872
instspeed: 2679.336099 KB/S, remain_time: 1.780210 s, 39370752/44758872
instspeed: 2720.844082 KB/S, remain_time: 0.831110 s, 42252120/44758872
download finished.
>>> dl.close()

```


# 特征

* 支持断点续传。
* 支持多线程分片下载。
* 支持多来源地址下载。
* 支持以子进程模式运行。
* 具有管理任务下载池。


# 安装

    $ pip install Nbdler

# 更多例子

## 关于``handler``。

对于``nbdler.Request``：

- 使用参数``child_process=True``使得下载任务运行在子进程模式下（默认为False）。

- 使用参数``filepath``来指定下载文件路径（如果文件名省却则由第一条下载地址决定）。
- 使用参数``max_thread``来限制最大的分片下载线程数（默认5）。
- 使用参数``max_retries``来限制下载链接的最大重试打开次数。（默认None，即无限制）
- 使用参数``block_size``来指定对分片的最小切割单元字节大小。（默认512*1024）

```python
>>> req = nbdler.Request(filepath='c:/nbdler_saved_path/centos-7-aarch64.iso', max_retries=3, max_thread=32)
```

为了实现多来源地址下载，你可以使用方法``put()``，来进行添加更多的地址来源。

```python
>>> req.put(url='http://mirrors.huaweicloud.com/centos-altarch/7.6.1810/isos/aarch64/CentOS-7-aarch64-NetInstall-1810.iso')
>>> req.put(url='http://mirror.xtom.com.hk/centos-altarch/7.6.1810/isos/aarch64/CentOS-7-aarch64-Minimal-1810.iso')
```

如果你希望下载运行在子进程模式下，可以使用参数``child_process=True``（``dlopen``下的参数优先于``Request``）。

```python
>>> dl = nbdler.dlopen(req, child_process=True)
>>> dl.start()
```

如果你希望暂停下载，可以使用``dl.pause()``或者``dl.stop()``，之后可以使用``dl.start()``继续下载。

```python
>>> dl.pause()
>>> dl.start()
```

## 关于``manager``。

如果你需要用到下载池，可以使用``nbdler.manager``：

- 使用参数``max_task``设置同时最大下载任务。

- 使用参数``child_process=True``使得下载池工作在子进程模式下（默认False）。

```python
>>> mgr = nbdler.manager(2)
```

之后你可以使用``putrequest``往下载池里面进行添加下载请求，添加完成后将返回任务``id号``。

```python
>>> mgr.putrequest(req)
0
>>> mgr.putrequest(req1)
1
>>> mgr.putrequest(req2)
2
```

使用``mgr.start_queue()``就能运行下载池。

```python
>>> mgr.start_queue()
```


# 许可证
Apache-2.0

# 更新日志

### 1.0.0
- 修复一些bug。

### 0.9.9
- 新的重构。
- 添加多进程下载支持。

### 0.0.1
- 上传代码。

 
