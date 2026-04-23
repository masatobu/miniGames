import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from report_store import ReportStore  # pylint: disable=C0413


class TestReportStore(unittest.TestCase):
    @patch.object(ReportStore, "set_local_storage")
    def test_save(self, mock):
        mock.return_value = True
        report_store = ReportStore()
        report_store.version = 1
        self.assertEqual(True, report_store.save({"test": "value"}))
        mock.assert_called_once_with('{"test": "value", "version": 1}')

    @patch.object(ReportStore, "set_local_storage")
    def test_save_exception(self, mock):
        mock.return_value = False
        report_store = ReportStore()
        report_store.version = 1
        self.assertEqual(False, report_store.save({"test": "value"}))
        mock.assert_called_once_with('{"test": "value", "version": 1}')

    @patch.object(ReportStore, "get_local_storage")
    def test_load(self, mock):
        test_cases = [
            ("success", {"test": "value"}, '{"test": "value", "version": 1}'),
            ("unmatch version", None, '{"test": "value", "version": 2}'),
            ("no json format", None, "version: 1"),
            ("fail", None, None),
        ]
        for case_name, expected, load_str in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, load_str=load_str
            ):
                mock.return_value = load_str
                report_store = ReportStore()
                report_store.version = 1
                self.assertEqual(expected, report_store.load())

    def test_crypt(self):
        test_cases = [
            ("case1", "test", "test", False),
            (
                "case2",
                " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                False,
            ),
            ("error", None, "error test", True),
        ]
        for case_name, expected, target, is_old_stored in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                target=target,
                is_old_stored=is_old_stored,
            ):
                report_store = ReportStore()
                crypt_str = report_store._crypt(target)  # pylint: disable=W0212
                if is_old_stored:
                    crypt_str = target
                decrypt_str = report_store._decrypt(crypt_str)  # pylint: disable=W0212
                self.assertEqual(decrypt_str, expected)
