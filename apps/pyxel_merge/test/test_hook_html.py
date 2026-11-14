import os
import unittest

HOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dist",
    "pyxel_merge_hook.html",
)
STORAGE_KEY = 'LOCALSTORAGE_KEY = "pyxel_merge"'
LAUNCH = "launchPyxel({"
SETTER = 'Object.defineProperty(window.pyxelContext, "pyodide"'


class TestHookHtml(unittest.TestCase):
    """ブラウザ版のフック HTML（ビルド前のひな形）の特性テスト。"""

    def setUp(self):
        with open(HOOK_PATH, encoding="utf-8") as f:
            self.html = f.read()

    def test_localstorage_key(self):
        """localStorage のキーが pyxel_merge である。"""
        self.assertIn(STORAGE_KEY, self.html)

    def test_save_data_moved_to_localstorage_every_second(self):
        """/save_data.txt を localStorage へ移し、1 秒ごとに繰り返す。"""
        self.assertIn("/save_data.txt", self.html)
        self.assertIn("localStorage.setItem(LOCALSTORAGE_KEY", self.html)
        self.assertIn("setInterval(checkAndSave, 1000)", self.html)

    def test_load_data_written_from_localstorage(self):
        """localStorage の値を /load_data.txt へ書く。"""
        self.assertIn("localStorage.getItem(LOCALSTORAGE_KEY)", self.html)
        self.assertIn("/load_data.txt", self.html)

    def test_pyodide_setter_before_launch(self):
        """pyodide の代入を捕まえる仕組みが launchPyxel の行より前にある。"""
        self.assertIn(SETTER, self.html)
        self.assertLess(self.html.index(SETTER), self.html.index(LAUNCH))

    def test_single_launch_line(self):
        """launchPyxel({ で始まる行が 1 行だけある。"""
        lines = [x for x in self.html.splitlines() if x.startswith(LAUNCH)]
        self.assertEqual(len(lines), 1)

    def test_pyxel_js_loaded_before_launch(self):
        """pyxel.js の読み込みが launchPyxel の行より前にある。"""
        script = "kitao.dev/pyxel/3.0.1/pyxel.js"
        self.assertIn(script, self.html)
        self.assertLess(self.html.index(script), self.html.index(LAUNCH))


if __name__ == "__main__":
    unittest.main()
