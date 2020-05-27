

from setuptools import setup, find_packages
import io
import os

here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, 'nbdler', 'version.py'), 'r', encoding='utf-8') as f:
    exec(f.read(), about)

with io.open('README.rst', 'r', encoding='utf-8') as readme:
    long_description = readme.read()

install_requires = [
    'aiohttp',
    'requests'
]


setup(
    name=about['TITLE'],
    version=about['VERSION'],
    description=about['DESCRIPTION'],
    long_description=long_description,
    author=about['AUTHOR'],
    author_email=about['AUTHOR_EMAIL'],
    url=about['URL'],
    license=about['LICENSE'],
    classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: Apache Software License',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
        ],
    packages=find_packages(),
    install_requires=install_requires,
)