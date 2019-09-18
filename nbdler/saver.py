
import gzip
import io
import json


class Saver:
    def __init__(self, saved_path, save_handle):
        self._saved_path = saved_path
        self._save_handle = save_handle

    def json_dumps(self, obj):
        with io.open(self._saved_path, 'wb') as fp:
            fp.write(gzip.compress(json.dumps(obj).encode('utf-8')))
            fp.flush()

    def dump(self):
        self._save_handle()

    @staticmethod
    def json_loads(file):
        with io.open(file, 'rb') as f:
            json_byte = gzip.decompress(f.read())

        return json.loads(json_byte, encoding='utf-8')


