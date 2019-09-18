import nbdler
import time

req = nbdler.Request('http://mirrors.neusoft.edu.cn/centos/7.7.1908/isos/x86_64/CentOS-7-x86_64-Minimal-1908.iso',
                     max_thread=200, block_size=1024)
req.put('http://mirrors.zju.edu.cn/centos/7.7.1908/isos/x86_64/CentOS-7-x86_64-Minimal-1908.iso')
req.put('http://ftp.sjtu.edu.cn/centos/7.7.1908/isos/x86_64/CentOS-7-x86_64-Minimal-1908.iso')
dl = nbdler.dlopen(req)
dl.start()


dl.pause()
dl.start()
dl.pause()
del dl

dl = nbdler.dlopen('CentOS-7-x86_64-Minimal-1908.iso.nb')
dl.start()
while not dl.is_finished():
    print('inst: %f KB/S, remain_time: %f s, remain_byte: %d, online: %d' % (
        dl.getinstspeed() / 1024, dl.get_time_left(), dl.get_byte_left(), dl.get_online_cnt()))
    time.sleep(0.5)

dl.close()


import gc
del dl
gc.collect()
print('done')

# memory
while True:
    time.sleep(1)