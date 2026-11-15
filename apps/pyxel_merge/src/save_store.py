"""保存データの読み書き（暗号化・バージョン・ネイティブ実行での無効化）。"""

import base64
import binascii
import hashlib
import json
import sys
from typing import Optional


class SaveStore:
    """保存データの入出力を担う。

    入出力先は引数で差し替えられる。enabled が None のときは、
    ブラウザ版（emscripten）の実行のときだけ有効になる。
    """

    VERSION = 1
    SECRET = "pyxel merge game secret"

    def __init__(
        self,
        load_path: str = "/load_data.txt",
        save_path: str = "/save_data.txt",
        enabled: Optional[bool] = None,
    ):
        self.load_path = load_path
        self.save_path = save_path
        self.enabled = enabled
        self._key = hashlib.sha256(self.SECRET.encode("utf-8")).digest()

    def is_enabled(self) -> bool:
        """保存が有効か。enabled が None のときはブラウザ版のときだけ有効。"""
        if self.enabled is None:
            return sys.platform == "emscripten"
        return self.enabled

    def save(self, data: dict) -> bool:
        """data にバージョンを付けて暗号化し保存する。成功なら True。

        無効のとき、または書き込みに失敗したときは、何も例外を出さず False。
        """
        if not self.is_enabled():
            return False
        try:
            text = self._encrypt(json.dumps({**data, "version": self.VERSION}))
            with open(self.save_path, "w", encoding="ascii") as f:
                f.write(text)
        except (OSError, TypeError, ValueError):
            return False
        return True

    def load(self) -> Optional[dict]:
        """保存データを読み込む。「無し」（無効・無い・壊れている・版違い）は None。"""
        if not self.is_enabled():
            return None
        try:
            with open(self.load_path, "r", encoding="ascii") as f:
                dump = json.loads(self._decrypt(f.read()))
        except (OSError, ValueError, binascii.Error):
            return None
        if not isinstance(dump, dict) or dump.get("version") != self.VERSION:
            return None
        del dump["version"]
        return dump

    def _xor(self, data: bytes) -> bytes:
        return bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(data))

    def _encrypt(self, text: str) -> str:
        return base64.b64encode(self._xor(text.encode("utf-8"))).decode("ascii")

    def _decrypt(self, text: str) -> str:
        return self._xor(base64.b64decode(text.encode("ascii"))).decode("utf-8")
