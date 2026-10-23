import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from src.save_store import SaveStore


class TestSaveStore(unittest.TestCase):
    @patch.object(SaveStore, "set_local_storage")
    def test_save(self, mock):
        """save() が保存データへ version を付与して set_local_storage() へ渡すこと"""
        mock.return_value = True
        store = SaveStore()
        self.assertEqual(True, store.save({"test": "value"}))
        mock.assert_called_once_with(
            f'{{"test": "value", "version": {SaveStore.VERSION}}}'
        )

    @patch.object(SaveStore, "set_local_storage")
    def test_save_exception(self, mock):
        """set_local_storage() の失敗がそのまま save() の戻り値になること"""
        mock.return_value = False
        store = SaveStore()
        self.assertEqual(False, store.save({"test": "value"}))

    @patch.object(SaveStore, "get_local_storage")
    def test_load(self, mock):
        """load() が正常・バージョン不一致・非 JSON・読み込み失敗を正しく扱うこと"""
        test_cases = [
            (
                "success",
                {"test": "value"},
                f'{{"test": "value", "version": {SaveStore.VERSION}}}',
            ),
            (
                "unmatch version",
                None,
                f'{{"test": "value", "version": {SaveStore.VERSION + 1}}}',
            ),
            # ID-033 の形式（ユニットの状態を含まない）の保存データは読み込まない
            ("previous format version 1", None, '{"test": "value", "version": 1}'),
            ("no json format", None, "version: 1"),
            ("fail", None, None),
        ]
        for case_name, expected, load_str in test_cases:
            with self.subTest(case_name=case_name):
                mock.return_value = load_str
                store = SaveStore()
                self.assertEqual(expected, store.load())

    def test_crypt(self):
        """_crypt() → _decrypt() で復元でき、破損データでは None を返すこと"""
        test_cases = [
            ("case1", "test", "test", False),
            ("case2", "hello world 0123456789", "hello world 0123456789", False),
            ("error", None, "error test", True),
        ]
        for case_name, expected, target, is_broken in test_cases:
            with self.subTest(case_name=case_name):
                store = SaveStore()
                crypt_str = store._crypt(target)  # pylint: disable=W0212
                if is_broken:
                    crypt_str = target  # 破損データを模擬
                self.assertEqual(
                    expected, store._decrypt(crypt_str)  # pylint: disable=W0212
                )


class TestSaveStorePlatform(unittest.TestCase):
    """保存・読み込みはブラウザ実行（emscripten）のときだけ行う（ネイティブ実行では無効）"""

    def setUp(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        self.save_path = os.path.join(tmp_dir, "save_data.txt")
        self.load_path = os.path.join(tmp_dir, "load_data.txt")
        for name, path in (
            ("SAVE_FILENAME", self.save_path),
            ("LOAD_FILENAME", self.load_path),
        ):
            patcher = patch.object(SaveStore, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_native_save_does_nothing(self):
        """ネイティブ実行では save() がファイルを書かず、失敗（False）を返すこと"""
        with patch.object(sys, "platform", "linux"):
            self.assertEqual(False, SaveStore().save({"test": "value"}))
        self.assertFalse(os.path.exists(self.save_path))

    def test_native_load_returns_none(self):
        """ネイティブ実行では読み込み用のファイルがあっても load() が None を返すこと"""
        store = SaveStore()
        with open(self.load_path, "w", encoding="utf-8") as f:
            f.write(
                store._crypt(  # pylint: disable=W0212
                    f'{{"test": "value", "version": {SaveStore.VERSION}}}'
                )
            )
        with patch.object(sys, "platform", "linux"):
            self.assertIsNone(store.load())

    def test_browser_save_and_load(self):
        """ブラウザ実行では save() の書き出した内容を、読み込み用のファイル経由で load() が復元すること"""
        with patch.object(sys, "platform", "emscripten"):
            store = SaveStore()
            self.assertEqual(True, store.save({"test": "value"}))
            os.replace(self.save_path, self.load_path)  # フック HTML の受け渡しを模擬
            self.assertEqual({"test": "value"}, store.load())

    def test_browser_load_without_file(self):
        """ブラウザ実行で読み込み用のファイルが無いとき load() が None を返すこと"""
        with patch.object(sys, "platform", "emscripten"):
            self.assertIsNone(SaveStore().load())


if __name__ == "__main__":
    unittest.main()
