

from setuptools import setup, find_packages
import io

version = '0.9.9'
author = 'ZSAIm'
author_email = 'zzsaim@163.com'

with io.open('README.rst', 'r', encoding='utf-8') as freadme:
    long_description = freadme.read()

setup(
    name='Nbdler',
    version=version,
    description='HTTP/HTTPS downloader',
    long_description=long_description,
    author=author,
    author_email=author_email,
    url='https://github.com/ZSAIm/Nbdler',
    license='Apache-2.0 License',
    classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: Apache Software License',
            'Programming Language :: Python',
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
        ],
    packages=find_packages(),

)