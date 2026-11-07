# テストドライバー使用方法

## 概要

`test/` ディレクトリ配下の全テストを単一コマンドで実行できるテストドライバーです。

## 使い方

### 全テストを実行

```bash
python test/run_tests.py
```

### unittest モジュール経由で実行

```bash
python -m unittest discover -s test -p "test_*.py"
```

### 特定のテストだけ実行

```bash
python -m unittest test.test_main.TestGameCore.test_draw -v
```

## 実行結果の見方

### 成功時
```
test_draw (test.test_main.TestGameCore) ... ok
...

Ran 1 test in 0.050s

OK
```

### 失敗時
```
test_draw (test.test_main.TestGameCore) ... FAIL
...

Ran 1 test in 0.050s

FAILED (failures=1, errors=0)
```

## 終了コード

- `0`: 全テスト成功
- `1`: テスト失敗あり

## ファイル構成

```
test/
  __init__.py    # パッケージ化
  run_tests.py   # テストドライバー（main関数）
  test_main.py   # GameCore クラステスト
  README.md      # このファイル
```

## 特徴

- ✅ 単一エントリーポイント：`python test/run_tests.py` で全テスト実行
- ✅ 各テストファイルに main は不要
- ✅ unittest 標準機能を活用
- ✅ 新しいテストファイルを追加すれば自動対応（`test_*.py` の命名規則を守る）
