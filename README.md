Nbdler
===============
[![Build Status](https://img.shields.io/badge/build-passing-green.svg)](https://github.com/ZSAIM/Nbdler)
[![Build Status](https://img.shields.io/badge/pypi-v3.0.2-blue.svg)](https://pypi.org/project/Nbdler/)

Nbdler 是由Python3 编写的异步多客户端、多来源下载工具。


# 支持协议

- HTTP
- HTTPS

# 支持客户端

- [**aiohttp**](https://github.com/aio-libs/aiohttp): Async http client/server framework.
- [**requests**](https://github.com/psf/requests): A simple, yet elegant HTTP library.

# 特征

- 支持断点续传
- 支持多来源多客户端下载
- 支持速度限速
- 支持下载缓冲设置
- 支持代理（取决于客户端）

# 入门使用

### 简单下载示例
```python
import asyncio
import nbdler

async def main():
    request = nbdler.Request('http://a/file', file_path='file')
    async with nbdler.dlopen(request) as dl:
        dl.start()
        while not dl.is_finished():
            print((f'filename={dl.file.name}, '
                   f'transfer rate={round(dl.transfer_rate() / 1024)} kb/s, '
                   f'{round(dl.percent_complete(), 2)} % percent complete'))    
            await asyncio.sleep(1)
        await dl.ajoin()
            
asyncio.run(main())
```
### 多客户端，多来源，指定处理客户端，指定最大并发数
```python
import asyncio
import nbdler

async def main():
    request = nbdler.Request('http://a/file', 
                client_policy=nbdler.get_policy(http='aiohttp', https='requests'), 
                max_concurrent=16, file_path='file')
    request.put('https://b/file')
    async with nbdler.dlopen(request) as dl:
        await dl.astart()
        await dl.ajoin()
            
asyncio.run(main())
```

### 关于方法


# Installation

    $ pip install Nbdler

# Requirements

- Python >= 3.5.3
- aiohttp
- requests


# 许可证

Apache-2.0

# TODO

- [ ] 完善使用文档。
- [ ] 实现Handler处理器(SampleValidate 保证多来源下载时的资源匹配)。
- [ ] 实现DownloadSession(以便实现下载器的进程隔离，同时实现RPC进程通信)。
- [ ] 支持FTP协议。
