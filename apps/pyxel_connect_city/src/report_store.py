import base64
import binascii
import hashlib
import json


class ReportStore:
    LOAD_FILENAME = "/load_data.txt"
    SAVE_FILENAME = "/save_data.txt"
    SECRET = "pyxel connect city game secret"
    VERSION = 9

    def __init__(self):
        self.secret_hash = hashlib.sha256(self.SECRET.encode("utf-8")).digest()

    def set_local_storage(self, value):
        with open(self.SAVE_FILENAME, "w", encoding="utf-8") as f:
            save_data = self._crypt(value)
            f.write(save_data)
        return True

    def _xor_bytes(self, data: bytes, key: bytes) -> bytes:
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def _crypt(self, target):
        data = target.encode("utf-8")
        xored = self._xor_bytes(data, self.secret_hash)
        enc = base64.b64encode(xored).decode("ascii")
        return enc

    def get_local_storage(self):
        try:
            with open(self.LOAD_FILENAME, "r", encoding="utf-8") as f:
                return self._decrypt(f.read())
        except FileNotFoundError:
            return None

    def _decrypt(self, target):
        try:
            xored = base64.b64decode(target.encode("ascii"))
        except binascii.Error:
            return None
        data = self._xor_bytes(xored, self.secret_hash)
        return data.decode("utf-8")

    def save(self, data):
        return self.set_local_storage(json.dumps({**data, "version": self.VERSION}))

    def load(self):
        storage_str = self.get_local_storage()
        if storage_str is None:
            return None
        try:
            dump = json.loads(storage_str)
        except (json.JSONDecodeError, TypeError):
            return None
        if dump.get("version", None) != self.VERSION:
            return None
        del dump["version"]
        return dump
