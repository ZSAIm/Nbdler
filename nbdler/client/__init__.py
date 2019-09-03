# ---------------------------------------------------------------------------
# Name:        nbdler/client/__init__.py
# Author:      ZSAIm
#
# Created:     01-Sept-2019
# License:     Apache-2.0
# ---------------------------------------------------------------------------

from nbdler.client import http

__all__ = ('build_initial_opener', 'build_client')


def build_initial_opener(source, progress, callback):
    if source.scheme in ('http', 'https'):
        handler = http.build_initial_opener
    else:
        raise ValueError('Unsupported protocol (%s).' % source.scheme)

    return handler(source, progress, callback)


def build_client(source, progress):
    if source.scheme in ('http', 'https'):
        handler = http.HTTPClient
    else:
        raise ValueError('Unsupported protocol (%s).' % source.scheme)

    return handler(source, progress)
