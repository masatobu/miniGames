"""ブラウザ経路（.pyxapp 内のトップレベル import）でモジュールを読み込めることを確認する。

pyxel package は src/ をアプリのルートとして包むため、ブラウザではパッケージ ``src`` が存在せず、
``main`` などをトップレベルのモジュールとして import する。その状態を別プロセスで再現する。
"""

import os
import subprocess
import sys
import tempfile
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(APP_ROOT, "src")

MODULES = [
    "main",
    "field",
    "screen",
    "drawing",
    "animation",
    "garage",
    "operation",
    "game",
]


def import_in_browser_layout(module):
    """src/ だけを sys.path に置いた別プロセスで module を import する。"""
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=cwd,
            env={**os.environ, "PYTHONPATH": SRC_DIR},
            capture_output=True,
            text=True,
            check=False,
        )


class TestBrowserImports(unittest.TestCase):
    def test_main_imports_without_src_package(self):
        # FR2.1: パッケージ src が無い状態（.pyxapp のレイアウト）で main が import できる
        result = import_in_browser_layout("main")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_each_module_imports_without_src_package(self):
        # FR2.1: 各モジュールが個別にも import できる
        for module in MODULES:
            with self.subTest(module=module):
                result = import_in_browser_layout(module)
                self.assertEqual(0, result.returncode, result.stderr)

    def test_main_imports_as_package(self):
        # FR2.2: パッケージ経由（テストの import 経路）も壊れていない
        result = subprocess.run(
            [sys.executable, "-c", "import src.main"],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
