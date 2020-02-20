

from setuptools import setup, find_packages
import io

version = '2.0.0'
author = 'ZSAIm'
author_email = 'zzsaim@163.com'

with io.open('README.rst', 'r', encoding='utf-8') as readme:
    long_description = readme.read()

setup(
    name='Nbdler',
    version=version,
    description='downloader',
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
            'Programming Language :: Python :: 3',
        ],
    packages=find_packages(),
    install_requires=['EventDriven'],
)