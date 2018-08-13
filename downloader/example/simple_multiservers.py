from downloader import downloader
import time


dl = downloader()
dl.config(file_name='0_wechat_0', thread_count=5, complete_validate=False, force=True, block_size=1024*10)
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