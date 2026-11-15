import base64
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from src.save_store import SaveStore


class TestSaveStore(unittest.TestCase):
    """SaveStore のテスト。入出力は一時ディレクトリのパスを引数で渡して差し替える。"""

    def setUp(self):
        self._tmp_name = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp_name)
        self.path = os.path.join(self._tmp_name, "data.txt")

    def make_store(self, enabled=True):
        """保存先と読込元を同じファイルにした SaveStore を作る。"""
        return SaveStore(load_path=self.path, save_path=self.path, enabled=enabled)

    def write_raw(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def encode_like_store(self, text):
        """SaveStore と同じ方式（SHA-256 の鍵で XOR、Base64）で text を暗号化する。"""
        key = hashlib.sha256(SaveStore.SECRET.encode("utf-8")).digest()
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(text.encode("utf-8")))
        return base64.b64encode(xored).decode("ascii")

    def test_round_trip(self):
        """BR1.1/BR1.2/BR1.6: save したものを load すると元の辞書に戻る（version は含まない）。"""
        store = self.make_store()
        data = {"field": [1, 2, 3], "score": 10}
        self.assertTrue(store.save(data))
        self.assertEqual(store.load(), data)

    def test_saved_text_is_ascii_and_not_plain_json(self):
        """BR1.2: 保存データは ASCII で、元の JSON をそのまま含まない。"""
        store = self.make_store()
        data = {"score": 12345}
        store.save(data)
        with open(self.path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.isascii())
        self.assertNotIn("score", text)
        self.assertNotIn("12345", text)

    def test_save_writes_current_version(self):
        """BR1.1: 書き出すデータにはバージョンが付く。"""
        store = self.make_store()
        store.save({"a": 1})
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read()
        key_decoded = json.loads(self.decode_like_store(raw))
        self.assertEqual(key_decoded, {"a": 1, "version": SaveStore.VERSION})

    def decode_like_store(self, text):
        """encode_like_store の逆。"""
        key = hashlib.sha256(SaveStore.SECRET.encode("utf-8")).digest()
        xored = base64.b64decode(text.encode("ascii"))
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode("utf-8")

    def test_version_mismatch_is_none(self):
        """BR1.3: バージョン違い（と version 無し）は「無し」。"""
        store = self.make_store()
        other = SaveStore.VERSION + 1
        self.write_raw(self.encode_like_store(json.dumps({"a": 1, "version": other})))
        self.assertIsNone(store.load())
        self.write_raw(self.encode_like_store(json.dumps({"a": 1})))
        self.assertIsNone(store.load())

    def test_broken_data_is_none(self):
        """BR1.4: 復号できない・JSON でない・辞書でないデータは「無し」。"""
        store = self.make_store()
        broken = [
            "!!!not base64!!!",
            self.encode_like_store("not json"),
            self.encode_like_store(json.dumps([1, 2, 3])),
            base64.b64encode(b"\xff\xfe\xfd").decode("ascii"),
        ]
        for text in broken:
            with self.subTest(text=text):
                self.write_raw(text)
                self.assertIsNone(store.load())

    def test_missing_file_is_none(self):
        """BR1.5: ファイルが無いときは「無し」。"""
        self.assertIsNone(self.make_store().load())

    def test_disabled_does_not_write_and_loads_none(self):
        """BR1.7: 無効のとき save は何も書かず False、load は「無し」。"""
        store = self.make_store(enabled=False)
        self.assertFalse(store.save({"a": 1}))
        self.assertFalse(os.path.exists(self.path))
        self.write_raw(
            self.encode_like_store(json.dumps({"version": SaveStore.VERSION}))
        )
        self.assertIsNone(store.load())

    def test_write_failure_returns_false(self):
        """BR1.8: 書き込みに失敗しても例外を出さず False を返す。"""
        bad_path = os.path.join(self._tmp_name, "no_such_dir", "data.txt")
        store = SaveStore(load_path=bad_path, save_path=bad_path, enabled=True)
        self.assertFalse(store.save({"a": 1}))

    def test_paths_are_injectable(self):
        """BR1.9/BR1.6: 保存先と読込元を別々に差し替えられる。"""
        save_path = os.path.join(self._tmp_name, "save.txt")
        load_path = os.path.join(self._tmp_name, "load.txt")
        store = SaveStore(load_path=load_path, save_path=save_path, enabled=True)
        data = {"a": 1}
        store.save(data)
        self.assertTrue(os.path.exists(save_path))
        self.assertIsNone(store.load())  # 読込元はまだ無い
        os.replace(save_path, load_path)
        self.assertEqual(store.load(), data)

    def test_default_paths_and_auto_enabled(self):
        """BR1.6/BR1.7: 既定の入出力先と、enabled=None はブラウザ版のときだけ有効。"""
        store = SaveStore()
        self.assertEqual(store.save_path, "/save_data.txt")
        self.assertEqual(store.load_path, "/load_data.txt")
        self.assertFalse(store.is_enabled())  # テストはネイティブ実行


if __name__ == "__main__":
    unittest.main()
