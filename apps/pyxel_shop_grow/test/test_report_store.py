import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from report_store import ReportStore  # pylint: disable=C0413,E0401


class TestReportStore(unittest.TestCase):
    @patch.object(ReportStore, "set_local_storage")
    def test_save(self, mock):
        """save() が保存データへ version を付与して set_local_storage() へ渡すこと"""
        mock.return_value = True
        report_store = ReportStore()
        self.assertEqual(True, report_store.save({"test": "value"}))
        mock.assert_called_once_with(
            f'{{"test": "value", "version": {ReportStore.VERSION}}}'
        )

    @patch.object(ReportStore, "set_local_storage")
    def test_save_exception(self, mock):
        """set_local_storage() の失敗がそのまま save() の戻り値になること"""
        mock.return_value = False
        report_store = ReportStore()
        self.assertEqual(False, report_store.save({"test": "value"}))

    @patch.object(ReportStore, "get_local_storage")
    def test_load(self, mock):
        """load() が正常・バージョン不一致・非 JSON・読み込み失敗を正しく扱うこと"""
        test_cases = [
            (
                "success",
                {"test": "value"},
                f'{{"test": "value", "version": {ReportStore.VERSION}}}',
            ),
            (
                "unmatch version",
                None,
                f'{{"test": "value", "version": {ReportStore.VERSION + 1}}}',
            ),
            ("no json format", None, "version: 1"),
            ("fail", None, None),
        ]
        for case_name, expected, load_str in test_cases:
            with self.subTest(case_name=case_name):
                mock.return_value = load_str
                report_store = ReportStore()
                self.assertEqual(expected, report_store.load())

    def test_crypt(self):
        """_crypt() → _decrypt() で復元でき、破損データでは None を返すこと"""
        test_cases = [
            ("case1", "test", "test", False),
            ("case2", "hello world 0123456789", "hello world 0123456789", False),
            ("error", None, "error test", True),
        ]
        for case_name, expected, target, is_broken in test_cases:
            with self.subTest(case_name=case_name):
                report_store = ReportStore()
                crypt_str = report_store._crypt(target)  # pylint: disable=W0212
                if is_broken:
                    crypt_str = target  # 破損データを模擬
                self.assertEqual(
                    expected, report_store._decrypt(crypt_str)  # pylint: disable=W0212
                )
