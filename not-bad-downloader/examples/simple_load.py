from downloader import downloader
import time


# pause
dl = downloader()
dl.config(max_thread=10)
dl.add_url('http://dldir1.qq.com/weixin/Windows/WeChatSetup.exe')
opener = dl.open()
opener.start()
time.sleep(3)
print 'before pause: ', opener.getLeft()
opener.pause()
print 'after pause: ', opener.getLeft()

time.sleep(2)
new_dl = downloader()
new_opener = new_dl.load('', opener.file.name)
print 'before continue: ', new_opener.getLeft()
new_opener.start()

while True:
    print 'online:%d, %d/%d [%f kb/s]' % (new_opener.GlobalProg.getOnlineQuantity(), new_opener.file.size - new_opener.getLeft(), new_opener.file.size, new_opener.getinsSpeed() / 1024)
    time.sleep(1)
    if new_opener.isDone():
        print 'done!'
        break
