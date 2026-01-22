"""
テストドライバー - test/ ディレクトリ下の全テストを統一実行
"""

import sys
import importlib
import importlib.util
import unittest
from pathlib import Path
from types import ModuleType
from typing import List, Type


class TestRunner:
    """unittest テストドライバー - 全テスト自動発見・統合実行"""

    def __init__(self, test_dir: str = "test") -> None:
        """初期化

        Args:
            test_dir: テストモジュールディレクトリ (デフォルト: 'test')
        """
        self.test_dir = test_dir

    def discover_test_modules(self) -> List[ModuleType]:
        """test/ ディレクトリ下の test_*.py モジュールを発見

        Returns:
            発見されたモジュールのリスト（ソート順）
        """
        modules = []

        # パス解決: スクリプト自体の場所から相対的にテストディレクトリを探す
        if self.test_dir == "test":
            # デフォルト: このスクリプトが test/ にあると想定
            script_dir = Path(__file__).parent
            test_path = script_dir
        else:
            # カスタムパスが指定されている場合
            test_path = Path(self.test_dir)

        if not test_path.exists():
            raise FileNotFoundError(
                f"テストディレクトリが見つかりません: {test_path.absolute()}"
            )

        # sys.path にテストディレクトリを追加
        test_abs_path = str(test_path.absolute().parent)
        if test_abs_path not in sys.path:
            sys.path.insert(0, test_abs_path)

        # test_*.py ファイルをソート順に処理
        for py_file in sorted(test_path.glob("test_*.py")):
            # test_run_tests.py は自身なのでスキップ
            if py_file.name == "test_run_tests.py":
                continue

            module_name = py_file.stem
            try:
                # モジュールをインポート（パッケージ形式）
                module = importlib.import_module(f"{self.test_dir}.{module_name}")
                modules.append(module)
            except ImportError:
                # パッケージ形式がダメな場合は直接ロード
                try:
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    modules.append(module)
                except (ImportError, AttributeError, OSError):
                    print(f"Warning: Failed to import {module_name}")

        return modules

    def extract_test_classes(self, module: ModuleType) -> List[Type[unittest.TestCase]]:
        """モジュールから unittest.TestCase を継承したテストクラスを抽出

        Args:
            module: テストモジュール

        Returns:
            テストクラスのリスト（クラス名昇順）
        """
        test_classes = []
        for name in dir(module):
            obj = getattr(module, name)
            # unittest.TestCase を継承したクラスを抽出
            if (
                isinstance(obj, type)
                and issubclass(obj, unittest.TestCase)
                and obj is not unittest.TestCase
            ):
                test_classes.append(obj)

        # クラス名でソート
        return sorted(test_classes, key=lambda c: c.__name__)

    def load_all_tests(self, modules: List[ModuleType]) -> unittest.TestSuite:
        """全モジュールのテストクラスから TestSuite を生成

        Args:
            modules: テストモジュールのリスト

        Returns:
            生成された TestSuite
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()

        for module in modules:
            test_classes = self.extract_test_classes(module)
            for test_class in test_classes:
                # テストクラスから全テストメソッドをロード
                class_tests = loader.loadTestsFromTestCase(test_class)
                suite.addTests(class_tests)

        return suite

    def run_tests(self, test_suite: unittest.TestSuite) -> unittest.TestResult:
        """TestSuite を実行

        Args:
            test_suite: 実行する TestSuite

        Returns:
            テスト実行結果
        """
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        return result

    def run_all_tests(self) -> unittest.TestResult:
        """テストモジュール発見から実行まで全て実行

        Returns:
            テスト実行結果
        """
        # モジュール発見
        modules = self.discover_test_modules()
        if not modules:
            print("Error: テストモジュールが見つかりません")
            return None

        # TestSuite 生成
        test_suite = self.load_all_tests(modules)

        # 実行
        result = self.run_tests(test_suite)
        return result


def main() -> int:
    """メイン関数 - テストドライバーのエントリーポイント

    Returns:
        終了コード（0: 成功, 1: 失敗）
    """
    runner = TestRunner()
    result = runner.run_all_tests()

    if result is None:
        return 1

    # テスト失敗がある場合は終了コード 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
