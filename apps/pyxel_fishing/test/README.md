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
python -m unittest test.test_pyxel_combo_card_card.TestCard.test_card_rank -v
```

## 実行結果の見方

### 成功時
```
test_card_rank (test.test_pyxel_combo_card_card.TestCard) ... ok
...

Ran 34 tests in 0.150s

OK
```

### 失敗時
```
test_card_rank (test.test_pyxel_combo_card_card.TestCard) ... FAIL
...

Ran 34 tests in 0.150s

FAILED (failures=1, errors=0)
```

## 終了コード

- `0`: 全テスト成功
- `1`: テスト失敗あり

## ファイル構成

```
test/
  __init__.py                      # パッケージ化
  run_tests.py                     # テストドライバー（main関数）
  test_run_tests.py                # テストドライバー自体のテスト
  test_pyxel_combo_card_card.py    # Card クラステスト
  test_pyxel_combo_card_hand.py    # Hand クラステスト
  test_pyxel_combo_card_game.py    # Game クラステスト
  test_pyxel_combo_card_main.py    # GameCore クラステスト
  README.md                        # このファイル
```

## 特徴

- ✅ 単一エントリーポイント：`python test/run_tests.py` で全テスト実行
- ✅ 各テストファイルに main は不要
- ✅ unittest 標準機能を活用
- ✅ 新しいテストファイルを追加すれば自動対応（`test_*.py` の命名規則を守る）
