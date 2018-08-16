from downloader import downloader
import time

def download_test():

    start = time.clock()
    dl = downloader()
    dl.config(max_thread=5, verify=False)
    # dl.add_url('http://xiazai.xiazaiba.com/Soft/W/WeChatSetup_2.6.4.1000_XiaZaiBa.zip')
    # dl.add_url('http://dblt.xiazaiba.com/Soft/W/WeChatSetup_2.6.4.1000_XiaZaiBa.zip')
    dl.add_url('http://xiazai.xiazaiba.com/Soft/M/MarvelousDesigner7_Personal_4_1_100_XiaZaiBa.zip')
    dl.add_url('http://dblt.xiazaiba.com/Soft/M/MarvelousDesigner7_Personal_4_1_100_XiaZaiBa.zip')
    # dl.add_url('https://download.virtualbox.org/virtualbox/5.2.18/VirtualBox-5.2.18-124319-Win.exe')
    opener = dl.open()
    # dl.file.validate_name()
    # opener = dl.load('', dl.file.name)

    # if opener.server_validate() is True:
    opener.start()

    while True:

        print 'online:%d, %d/%d [%f kb/s]' % (opener.GlobalProg.getOnlineQuantity(), opener.file.size - opener.getLeft(), opener.file.size, opener.getinsSpeed() / 1024)
        time.sleep(1)
        if opener.isDone():
            print '-----------------------------'
            print 'Total time: %f s, average speed: %f kb/s' % (time.clock() - start, opener.getavgSpeed() / 1024)
            print 'done!'
            break

# , sort="cumulative"
# cProfile.run('download_test()')
download_test()