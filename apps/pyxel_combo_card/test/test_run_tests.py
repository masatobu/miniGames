"""
テストドライバーのテスト
"""

import unittest

from .run_tests import TestRunner


class TestModuleDiscovery(unittest.TestCase):
    """テストモジュール発見機能のテスト"""

    def test_discover_test_modules(self):
        """test/ ディレクトリ下の test_*.py を発見できる"""
        runner = TestRunner()
        modules = runner.discover_test_modules()

        # 期待するモジュール
        expected_modules = [
            "test_pyxel_combo_card_card",
            "test_pyxel_combo_card_hand",
            "test_pyxel_combo_card_game",
            "test_pyxel_combo_card_main",
        ]

        module_names = [m.__name__.split(".")[-1] for m in modules]
        for expected in expected_modules:
            self.assertIn(
                expected, module_names, f"モジュール '{expected}' が発見されていない"
            )

    def test_discover_returns_module_list(self):
        """発見結果がモジュールのリストである"""
        runner = TestRunner()
        modules = runner.discover_test_modules()

        self.assertIsInstance(modules, list, "結果がリストではない")
        self.assertGreater(len(modules), 0, "モジュールが発見されていない")

        # 各要素がモジュール型
        for module in modules:
            self.assertTrue(
                hasattr(module, "__name__"), f"{module} がモジュール型ではない"
            )


class TestClassExtraction(unittest.TestCase):
    """テストクラス抽出機能のテスト"""

    def test_extract_test_classes(self):
        """モジュールから unittest.TestCase を継承したテストクラスを抽出"""
        runner = TestRunner()
        modules = runner.discover_test_modules()

        # 少なくとも1つのモジュールがある
        self.assertGreater(len(modules), 0)

        # 最初のモジュールからテストクラスを抽出
        test_classes = runner.extract_test_classes(modules[0])
        self.assertGreater(
            len(test_classes),
            0,
            f"モジュール {modules[0].__name__} にテストクラスがない",
        )

        # 各クラスが TestCase を継承している
        for test_class in test_classes:
            self.assertTrue(
                issubclass(test_class, unittest.TestCase),
                f"{test_class.__name__} が TestCase を継承していない",
            )

    def test_extract_test_classes_from_all_modules(self):
        """全モジュールからテストクラスを抽出できる"""
        runner = TestRunner()
        modules = runner.discover_test_modules()

        all_classes = []
        for module in modules:
            classes = runner.extract_test_classes(module)
            all_classes.extend(classes)

        self.assertGreater(
            len(all_classes), 0, "全モジュールからテストクラスが抽出されていない"
        )


class TestUnittestIntegration(unittest.TestCase):
    """unittest 統合実行機能のテスト"""

    def test_load_all_tests(self):
        """全テストクラスから TestSuite を生成できる"""
        runner = TestRunner()
        modules = runner.discover_test_modules()

        test_suite = runner.load_all_tests(modules)

        self.assertIsInstance(
            test_suite, unittest.TestSuite, "結果が TestSuite ではない"
        )
        self.assertGreater(test_suite.countTestCases(), 0, "テストケースが0個")

    def test_run_all_tests(self):
        """全テストを実行できる"""
        runner = TestRunner()
        modules = runner.discover_test_modules()
        test_suite = runner.load_all_tests(modules)

        result = runner.run_tests(test_suite)

        self.assertIsInstance(result, unittest.TestResult, "結果が TestResult ではない")
        # テストケース数が 0 より大きい
        total_tests = result.testsRun
        self.assertGreater(total_tests, 0, "実行したテストが0個（期待値 > 0）")


if __name__ == "__main__":
    unittest.main()
