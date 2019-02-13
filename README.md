<<<<<<< HEAD
=======
******
*******
# 花了一个多星期重构了程序，过几天后将上传代码。
# 敬请期待！！
*******
******

# not-bad-downloader ( NB dwonloader )
multi-server, auto-range, completeness-validate...
>>>>>>> 78ce3fe93a59ee60a6aa9c5e59445a14224e8bc9

# nbdler (not-bad-downloader)

## 更新说明
**2019/02/13** - 基于not-bad-downloader 进行代码重构。


## 特征
1) 断点续传。
2) 多来源地址下载。
3) 多线程分片下载。
4) 自动分片控制管理。

## nbdler.open()可控参数
### 全局参数：

 参数  |  默认  |  说明
 ---- | -----  |  -----
filename  |  from url  |  文件名称。
filepath  |  ""  |  文件路径。(默认当前目录, "")
block_size  |  1MB  |  下载块大小。(数值越小，块数量越多，可分片数量越多，占用资源越多）
buffer_size  |  20MB  |  下载缓冲空间大小。(理论上缓冲空间越大，占用内存资源越多，下载速度越快， 适当调大可以降低对硬盘读写损耗)
max_conn  |  无限制  |  最大连接数。(默认-1， 即无限制)
max_speed  |  无限制  |  最大下载速度。(尚未实现，先占位)

### 链接局部参数

 参数  |  默认  |  说明
----  |  -----  |  -----
urls  |    |  [url1, url2, ...]
cookies  |  ""  |  指定对应链接的cookie: [cookie1, cookie2, ...]
hosts  |  from url  |  指定对应链接的host: [host1, host2, ...]
ports  |  from url  |  指定对应链接的port: [port1, port2, ...]
paths  |  from url  |  指定对应链接的port: [path1, path2, ...]
headers  |  chrome  |  指定对应链接的port: [header1, header2, ...]
max_threads  |  无限制  |  限制对应链接的最大线程数: 默认无限制[max_thread1, max_thread2, ...]

#### 注意：各参数列表的一个索引对应生成一个链接来源地址节点。
#### 若len(urls) > 1时，cookies/hosts/ports/paths/headers 可以使用单个元素来设置全局链接的参数。 如 headers = [header]


## 使用方法
### 打开下载例程
```python
# 若要下载文件A, 并且文件A可以通过在以下两个地址来源进行获取:
# 1)	https://host1:port1/path1/A		, 限制最大线程数： -1（无限制)
# 2)	https://host2:port2/path2/A		, 限制最大线程数： 10
# 限制下载最大链接数： 32


# 方法一: (一步到位)

import nbdler
urls = ['https://host1:port1/path1/A', 'https://host2:port2/path2/A']
dl = nbdler.open(max_conn=32, urls=urls, max_threads=[-1, 10])
dl.run()


# 方法二: (逐步添加)

import nbdler
dl = nbdler.open()

dl.config(max_conn=32)
dl.addNode(url='https://host1:port1/path1/A', max_thread=-1)
dl.addNode(url='https://host2:port2/path2/A', max_thread=10)

dl.run()
```

### 获取下载信息
```python
# 省略以上任务建立代码

# 获取下载文件大小
dl.getFileSize()

# 获取下载文件名
dl.getFileName()

# 获取瞬时下载速度
dl.getInsSpeed()

# 获取平均下载速度
dl.getAvgSpeed()

# 获取剩余下载字节
dl.getLeft()

# 获取当前在线的分片(返回正在链接获取数据的分片)
dl.getOnlines()

# 获取任务是否完成
dl.isEnd()

# 获取当前链接分片(返回所有的未完成分片)
dl.getConnections()

# 获取所有下载来源地址数据
dl.getUrls()

```

### 任务管理
```python 
# 省略任务建立的代码

# 任务暂停
dl.pause()	# 该方法将等待任务完全暂停后返回。

# 任务完成结束
dl.close()	# 该方法将删除下载任务信息的本地文件 '*.nbdler'

# 新添加下载来源地址节点(允许在下载过程中进行添加)
dl.add(id=-1, url, cookie, headers, host, port, path, protocal, proxy, max_thread)

# 删除下载来源地址节点(不允许下载过程中删除)
dl.delete([url, ], [id, ])

# 文件校验(实则是对各个分片最后指定大小的数据的校验)
segs = dl.fileVerify()	# 返回所有校验不匹配的分片索引

# 对分片索引所对应的分片进行重新下载
dl.fix(segs)

```

### 若非完整下载文件，而只是文件其中片段。

```python

import nbdler
urls = ['https://host1:port1/path1/A', 'https://host2:port2/path2/A']
dl = nbdler.open(max_conn=32, urls=urls, max_threads=[-1, 10])

# 若下载该文件的 0-512 和 1024-4096 段的数据，分别使用1和3个线程进行下载。。
dl.insert(0, 512, 1)
dl.insert(1024, 4096, 3)

# 对其进行下载
dl.manualRun()	# 当使用该方法运行的时候将自动进入片段下载模式而非文件下载模式

# 使用同样的方法进行获取下载过程信息
...
...

# 获取下载片段数据可以使用
dl.getSegsValue()	# 返回以范围为索引的数据数据流组成的字典，如{'0-512': ..., '1024-4096': ...} 

# 获取下载片段当前数据大小
dl.getSegsSize()	# 返回已下载并且完成缓冲的片段数据大小

# 片段的更多操作可以引用
dl.file.fp

```


# 





