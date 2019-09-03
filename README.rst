Nbdler
======

|Build Status| |Build Status|

Nbdler is a HTTP/HTTPS downloader programming by Python.

a short example：


    The usage is similar to ``urllib``'s.

.. code:: python

    >>> import nbdler
    >>> import time
    >>> req = nbdler.Request(url='https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe')
    >>> dl = nbdler.dlopen(req)
    >>> fileinfo = dl.getfileinfo()
    >>> fileinfo
    FileInfo(name='WeChatSetup.exe', path='', size=44758872, block_size=524288)
    >>> dl.start()
    >>> while not dl.is_finish():
    ...     print("instspeed: %f KB/S, remain_time: %f s, %d/%d" % (dl.getinstspeed()/1024, dl.get_remain_time(), dl.getincbyte(), fileinfo.size))
    ...     time.sleep(1)
    ... else:
    ...     print('download finished.')
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

Features
========

*  Resume breakpoint supported.
*  Multi-thread download supported.
*  Multi-url-source download supported.
*  Running in child process mode supported.
*  Download manager pool supported.

Installation
============

::

    $ pip install Nbdler

More example
============

About ``handler``\ 。
---------------------

``nbdler.Request``\ ：

*  Using ``child_process=True`` to make download running in child
   process mode. (``False`` default)

*  Using ``filepath`` to specify the filepath file saved. (filename
   would be determined by the first download url if missing)
*  Using ``max_thread`` to limit the max number of download thread.
   (``5`` default)
*  Using ``max_retries`` to limit the max number of retries to open url.
   (``None`` default, meaning no limit)
*  Using ``block_size`` to specify the unit byte size of the slice.
   (``512*1024`` default)

.. code:: python

    >>> req = nbdler.Request(filepath='c:/nbdler_saved_path/centos-7-aarch64.iso', max_retries=3, max_thread=32)

Using ``req.put()``\ to put more download source.

.. code:: python

    >>> req.put(url='http://mirrors.huaweicloud.com/centos-altarch/7.6.1810/isos/aarch64/CentOS-7-aarch64-NetInstall-1810.iso')
    >>> req.put(url='http://mirror.xtom.com.hk/centos-altarch/7.6.1810/isos/aarch64/CentOS-7-aarch64-Minimal-1810.iso')

Using ``child_process=True`` to make download running in child process
mode.(the priority level of ``dlopen``'s argument is higher than
``Request``'s)

.. code:: python

    >>> dl = nbdler.dlopen(req, child_process=True)
    >>> dl.start()

Using ``dl.pause()`` or ``dl.stop()`` to stop downloading, and using
``dl.start()`` to resume downloading.

.. code:: python

    >>> dl.pause()
    >>> dl.start()

About ``manager``\ 。
---------------------

``nbdler.manager`` ：

*  Using ``max_task`` to set the max number of the download tasks.

*  Using ``child_process=True`` to make download running in child
   process mode. (``False`` default)

.. code:: python

    >>> mgr = nbdler.manager(2)

Using ``putrequest()`` to put more download download request and
returning ``task id`` after then.

.. code:: python

    >>> mgr.putrequest(req)
    0
    >>> mgr.putrequest(req1)
    1
    >>> mgr.putrequest(req2)
    2

Using ``mgr.start_queue()`` to run the download pool.

.. code:: python

    >>> mgr.start_queue()

License
=======

Apache-2.0

