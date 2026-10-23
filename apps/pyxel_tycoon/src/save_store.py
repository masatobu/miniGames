import base64
import binascii
import hashlib
import json
import sys


class SaveStore:
    LOAD_FILENAME = "/load_data.txt"
    SAVE_FILENAME = "/save_data.txt"
    SECRET = "pyxel tycoon game secret"
    # 保存データの形式（キー・値の意味）を変えたら繰り上げる。
    # 繰り上げると、古い形式の保存データは読み込まれず、新しいゲームとして始まる
    VERSION = 2

    def __init__(self):
        self.secret_hash = hashlib.sha256(self.SECRET.encode("utf-8")).digest()

    @staticmethod
    def _is_browser():
        """保存・読み込みはブラウザ実行（Pyodide）のときだけ行う。ネイティブ実行では無効"""
        return sys.platform == "emscripten"

    def set_local_storage(self, value):
        if not self._is_browser():
            return False
        with open(self.SAVE_FILENAME, "w", encoding="utf-8") as f:
            f.write(self._crypt(value))
        return True

    def _xor_bytes(self, data: bytes, key: bytes) -> bytes:
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def _crypt(self, target):
        data = target.encode("utf-8")
        xored = self._xor_bytes(data, self.secret_hash)
        return base64.b64encode(xored).decode("ascii")

    def get_local_storage(self):
        if not self._is_browser():
            return None
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
