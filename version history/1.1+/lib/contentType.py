
def content_type(type):
    dict = {
        'application/octet-stream': '',
        'image/tiff': '.tif',
        'text/asp': '.asp',
        'text/html': '.html',
        'image/x-icon': '.ico',
        'application/x-ico': '.ico',
        'application/x-msdownload': '.exe',
        'video/mpeg4': '.mp4',
        'audio/mp3': '.mp3',
        'video/mpg': '.mpg',
        'application/pdf': '.pdf',
        'application/vnd.android.package-archive': '.apk',
        'application/vnd.rn-realmedia-vbr': '.rmvb',
        'application/vnd.rn-realmedia': '.rm',
        'application/vnd.ms-powerpoint': '.ppt',
        'application/x-png': '.png',
        'image/jpeg': '.jpg',
        'application/x-jpg': '.jpg',
        'application/x-bmp': '.bmp',
        'application/msword': '.doc',
        '': '',
    }
    if type in dict.keys():
        return dict[type]
    return ''