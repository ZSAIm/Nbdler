from downloader import downloader
import time


dl = downloader()
# dl.config(thread_count=10)
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

# or use ___progressbar
#
# from ___progressbar import progressBar
# bar = progressBar(0, opener.file.size)
# while True:
#     bar.update(opener.file.size - opener.getLeft(), str(int(opener.getinsSpeed() / 1024)) + ' kb/s')
#     if opener.isDone():
#         print 'done!'
#         break
#     time.sleep(1)
