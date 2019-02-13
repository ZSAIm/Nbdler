from downloader import downloader
import time

start = time.clock()
dl = downloader()
dl.config(file_name='wechat1', thread_count=16, complete_validate=False, force=True)
# dl.add_server('http://xiazai.xiazaiba.com/Soft/W/WeChatSetup_2.6.4.1000_XiaZaiBa.zip')
# dl.add_server('http://dblt.xiazaiba.com/Soft/W/WeChatSetup_2.6.4.1000_XiaZaiBa.zip')
dl.add_server('http://xiazai.xiazaiba.com/Soft/M/MarvelousDesigner7_Personal_4_1_100_XiaZaiBa.zip')
dl.add_server('http://dblt.xiazaiba.com/Soft/M/MarvelousDesigner7_Personal_4_1_100_XiaZaiBa.zip')
opener = dl.open()

if opener.server_validate() is True:
    opener.start()

    while True:

        print 'online:%d, %d/%d [%f kb/s]' % (opener.GlobalProg.getOnlineQuantity(), opener.file.size - opener.getLeft(), opener.file.size, opener.getinsSpeed() / 1024)
        time.sleep(1)
        if opener.isDone():
            print '-----------------------------'
            print 'Total time: %f s, average speed: %f kb/s' % (time.clock() - start, opener.getavgSpeed() / 1024)
            print 'done!'
            break