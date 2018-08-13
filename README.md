# not-bad-downloader
multi-server, auto-range, completeness-validate...


# 不错的下载器
	* 【支持多服务器下载】
	* 【自动分片控制管理】
	* 【自动连接超时重试】
	* 【文件损坏尝试修复】

### 基本功能： 
	断点续传 、 分片下载 、 等各种基本功能。

### 内置模块
	time , os , math, threading, random, socket, ssl

### 安装模块
	无

## 基本结构
                                                /--> Progress 
                               /----> progress ----> GlobalProgress           TaskAssign <-- WaitLock -> Progress 
	downloader -> DLManager --|          									   
	                           \----> TaskAssign --> TaskAssign   

### 各部分作用	
	downloader	: 负责文件名，下载地址等处理完交给DLManager。
	DLManager	: 管理下载任务的全局操作。
	GlobalProg	: 全局的进度管理，对各下载分片进行监听。
	Progress	: 下载分片的信息。
	TaskAssign	: 管理控制下载分片的分配，如服务器、分片范围等
	WaitLock	: 解决分片范围重新设定时和正在下载进度的冲突而出现的问题。
	
### 最简单的使用例子
```ruby
from downloader import downloader
import time

dl = downloader()
dl.config(thread_count=10)
dl.add_server('http://dldir1.qq.com/weixin/Windows/WeChatSetup.exe')
opener = dl.open()
opener.start()

# progress viewer
while True:
    print 'online:%d, %d/%d [%f kb/s]' % (opener.GlobalProg.getOnlineQuantity(), opener.file.size - opener.getLeft(), opener.file.size, opener.getinsSpeed() / 1024)
    time.sleep(1)
    if opener.isDone():
        print 'done!'
        break
```
### 来一个多服务器的栗子
```ruby
from downloader import downloader
import time


dl = downloader()
dl.config(file_name='wechat', thread_count=5, complete_validate=False, force=True, block_size=1024*10)
dl.add_server('http://xiazai.xiazaiba.com/Soft/W/WeChatSetup_2.6.4.1000_XiaZaiBa.zip')
dl.add_server('http://dblt.xiazaiba.com/Soft/W/WeChatSetup_2.6.4.1000_XiaZaiBa.zip')

opener = dl.open()

if opener.server_validate() is True:
    opener.start()

    while True:
        print 'online:%d, %d/%d [%f kb/s]' % (opener.GlobalProg.getOnlineQuantity(), opener.file.size - opener.getLeft(), opener.file.size, opener.getinsSpeed() / 1024)
        time.sleep(1)
        if opener.isDone():
            print 'done!'
            break

```

项目文件夹 ./not-bad-downloader/example/ 下还有'很多'实现相关功能栗子，可以取参考下。

***
如果对这个项目感兴趣，可以提意见或者参与改进哦！
	如果有什么疑问可以直接pull，或者联系邮箱：405935987@163.com
	

本项目地址：https://github.com/ZSAIm/not-bad-downloader

