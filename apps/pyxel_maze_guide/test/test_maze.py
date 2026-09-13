import random
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from src.main import Direction, GameState, Maze

NEIGHBOR_OFFSET = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}
OPPOSITE = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}
ALL_POSITIONS = {(col, row) for col in range(Maze.COLS) for row in range(Maze.ROWS)}


def neighbor_of(col, row, direction):
    dcol, drow = NEIGHBOR_OFFSET[direction]
    return (col + dcol, row + drow)


# test_main.py の同名ヘルパーとの重複は意図的（ID-003_subtasks.md「テスト戦略」参照）。
# 共通化は同じヘルパーが3ファイル以上に並んだ時点で検討する方針のため抑制する
@contextmanager
def fixed_maze(cols, rows, grid):
    """迷路のサイズと生成結果を、テストが指定した任意のグリッドに差し替える"""
    # pylint: disable-next=duplicate-code
    with patch.object(Maze, "COLS", cols), patch.object(
        Maze, "ROWS", rows
    ), patch.object(Maze, "GOAL", (cols - 1, rows - 1)), patch.object(
        Maze, "_generate", lambda self: grid
    ):
        yield


class TestMazeGeneration(unittest.TestCase):
    def setUp(self):
        self.maze = Maze()

    def test_outside_of_the_maze_has_no_connection(self):
        """迷路の範囲外の座標は道を持たないこと"""
        for col, row in [(-1, 0), (0, -1), (Maze.COLS, 0), (0, Maze.ROWS)]:
            with self.subTest(cell=(col, row)):
                self.assertEqual(set(), self.maze.get_connections(col, row))

    def test_connections_are_mutual(self):
        """迷路の内部に向かう道は、その隣のグリッドが必ず逆方向の道を持つこと"""
        for col, row in ALL_POSITIONS:
            for direction in self.maze.get_connections(col, row):
                neighbor = neighbor_of(col, row, direction)
                if neighbor not in ALL_POSITIONS:
                    continue  # 入口・出口は相手のグリッドを持たない
                with self.subTest(cell=(col, row), direction=direction):
                    self.assertIn(
                        OPPOSITE[direction], self.maze.get_connections(*neighbor)
                    )

    def test_only_entrance_and_exit_lead_outside(self):
        """迷路の外へ出る道が、入口（スタートの左）と出口（ゴールの右）の 2 本だけであること"""
        outside_roads = {
            ((col, row), direction)
            for col, row in ALL_POSITIONS
            for direction in self.maze.get_connections(col, row)
            if neighbor_of(col, row, direction) not in ALL_POSITIONS
        }
        self.assertEqual(
            {(Maze.START, Direction.LEFT), (Maze.GOAL, Direction.RIGHT)},
            outside_roads,
        )

    def test_all_cells_are_reachable_from_start(self):
        """スタートから道を辿ると全グリッドに到達できること"""
        visited = {Maze.START}
        stack = [Maze.START]
        while stack:
            col, row = stack.pop()
            for direction in self.maze.get_connections(col, row):
                neighbor = neighbor_of(col, row, direction)
                if neighbor in ALL_POSITIONS and neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        self.assertEqual(ALL_POSITIONS, visited)

    def test_maze_has_no_loop(self):
        """迷路が閉路を持たないこと（内部の道の本数がグリッド数 - 1 であること）"""
        inside_roads = sum(
            1
            for col, row in ALL_POSITIONS
            for direction in self.maze.get_connections(col, row)
            if neighbor_of(col, row, direction) in ALL_POSITIONS
        )
        self.assertEqual((Maze.COLS * Maze.ROWS - 1) * 2, inside_roads)


class TestMazeRandomness(unittest.TestCase):
    def _snapshot(self, maze):
        return {
            (col, row): maze.get_connections(col, row) for col, row in ALL_POSITIONS
        }

    def test_different_seed_generates_different_maze(self):
        """異なるシードでは異なる迷路が生成されること"""
        random.seed(0)
        first = self._snapshot(Maze())
        random.seed(1)
        second = self._snapshot(Maze())
        self.assertNotEqual(first, second)

    def test_same_seed_generates_same_maze(self):
        """同じシードでは同じ迷路が再現されること"""
        random.seed(0)
        first = self._snapshot(Maze())
        random.seed(0)
        second = self._snapshot(Maze())
        self.assertEqual(first, second)


class TestMazeMobMovement(unittest.TestCase):
    # 一本道（スタートから隣のセルへの道が 1 本だけの盤面）。
    # 進行方向が一意に定まるため、「1 セル動く」ことだけを問える
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    # スタートが迷路の外（入口）と内側の両方に道を持つ盤面。
    # 入口を除外できていなければ、迷路の外(-1, 0)へ動いてしまう
    _GATE_GRID = {
        (0, 0): {Direction.LEFT, Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    # (0,0) から (1,0) への一本道の先に、(2,0)・(1,1) への分岐がある盤面。
    # (1,0) では、直前に通ってきた (0,0) 方向 (LEFT) を除いた
    # RIGHT・DOWN の 2 方向が未探索の分岐候補になる
    _BRANCH_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT, Direction.DOWN},
        (2, 0): {Direction.LEFT},
        (1, 1): {Direction.UP},
    }

    # スタート (0,0) から (1,0) への一本道の先が行き止まりになる盤面（2 列 2 行）。
    # GOAL は fixed_maze により (1,1) になり、行き止まり (1,0) とは別セルになる
    _DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    # スタートから (1,0) → (2,0) → (3,0) と 3 セル進んだ先が行き止まりになる盤面
    # （4 列 2 行）。分岐を持たない一本道のため、後退が来た順の逆順で
    # 複数セルぶん辿ることだけを問える。GOAL は fixed_maze により (3,1) になる
    _LONG_DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT, Direction.RIGHT},
        (3, 0): {Direction.LEFT},
    }

    # スタート (0,0) が行き止まり (1,0) に 1 本だけつながる盤面（3 列 1 行）。
    # GOAL は fixed_maze により (2,0) になり、行き止まり (1,0) や
    # スタート (0,0) とは別セルになる（ゴール到達による停止と混同しないため）
    _START_DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    # スタート (0,0) から (1,0) を経て (2,0) へ続く一本道（3 列 1 行）。
    # 通過済みのセルと、まだ先にあり到達していないセルを区別して問える
    _VISITED_QUERY_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }

    def test_mob_position_after_kicks(self):
        """モブがスタート地点から始まり、1 回のキックで隣接する道の先へ 1 セル動くこと"""
        test_cases = [
            (0, Maze.START),  # 生成直後: まだキックしていない
            (1, (1, 0)),  # 1 回キック: 唯一の道の先へ 1 セル動く
        ]
        for num_kicks, expected_position in test_cases:
            with self.subTest(num_kicks=num_kicks):
                with fixed_maze(2, 1, self._ONE_WAY_GRID):
                    maze = Maze()
                    for _ in range(num_kicks):
                        maze.kick()
                self.assertEqual(expected_position, maze.get_mob_position())

    def test_mob_moves_to_the_inside_neighbor_ignoring_the_gate_to_outside(self):
        """迷路の外へ開いた道と内側の道の両方を持つセルから、モブが内側の道へ動くこと"""
        with fixed_maze(2, 1, self._GATE_GRID):
            maze = Maze()
            maze.kick()
        self.assertEqual((1, 0), maze.get_mob_position())

    def test_mob_moves_to_the_direction_returned_by_patched_random_choice(self):
        """未探索方向が複数ある分岐で、patch した乱数の戻り値に対応する方向へ動くこと"""
        with fixed_maze(3, 2, self._BRANCH_GRID):
            with patch("src.main.random.choice", return_value=Direction.DOWN):
                maze = Maze()
                maze.kick()  # (0,0) -> (1,0)：一本道なので乱数は使われない
                maze.kick()  # (1,0) の分岐で、乱数の戻り値 DOWN の方向へ動く
        self.assertEqual((1, 1), maze.get_mob_position())

    def test_mob_excludes_the_previous_cell_from_branch_candidates(self):
        """直前に通ってきたセルへ戻る方向が、分岐での進行先候補に含まれないこと"""
        with fixed_maze(3, 2, self._BRANCH_GRID):
            with patch(
                "src.main.random.choice", return_value=Direction.RIGHT
            ) as mock_choice:
                maze = Maze()
                maze.kick()
                maze.kick()
                candidates = mock_choice.call_args.args[0]
        self.assertEqual({Direction.RIGHT, Direction.DOWN}, set(candidates))
        self.assertEqual((2, 0), maze.get_mob_position())

    def test_mob_backs_away_after_reaching_a_dead_end(self):
        """行き止まりに達した後のキックで、来た道を 1 セル戻ること"""
        with fixed_maze(2, 2, self._DEAD_END_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)：行き止まりへ前進
            maze.kick()  # (1,0)：未探索方向がないため (0,0) へ後退
        self.assertEqual((0, 0), maze.get_mob_position())

    def test_mob_backtracks_through_multiple_cells_in_reverse_order(self):
        """分岐まで複数セル戻る場合も、来た順の逆順で辿ること"""
        test_cases = [
            (3, (3, 0)),  # 3 回前進して行き止まりへ到達
            (4, (2, 0)),  # 1 回目の後退
            (5, (1, 0)),  # 2 回目の後退（来た順の逆順）
            (6, (0, 0)),  # 3 回目の後退（来た順の逆順）
        ]
        for num_kicks, expected_position in test_cases:
            with self.subTest(num_kicks=num_kicks):
                with fixed_maze(4, 2, self._LONG_DEAD_END_GRID):
                    maze = Maze()
                    for _ in range(num_kicks):
                        maze.kick()
                self.assertEqual(expected_position, maze.get_mob_position())

    def test_mob_does_not_move_after_reaching_the_goal(self):
        """ゴールセルにいるモブが、キックを何回受けても位置が変わらないこと"""
        test_cases = [0, 1, 2, 3]  # ゴール到達後の追加キック回数
        for extra_kicks in test_cases:
            with self.subTest(extra_kicks=extra_kicks):
                with fixed_maze(2, 1, self._ONE_WAY_GRID):
                    maze = Maze()
                    maze.kick()  # ゴール(1, 0)へ到達（1 回目のキック）
                    for _ in range(extra_kicks):
                        maze.kick()
                    self.assertEqual((1, 0), maze.get_mob_position())

    def test_mob_resumes_forward_then_retraces_the_resumed_path_on_backtrack(self):
        """後退の途中で未探索の分岐に達したらそちらへ前進し直し、
        前進復帰後はそこから先が新たな来た道として積み上がること"""
        test_cases = [
            (1, (1, 0)),  # (0,0) -> (1,0)：一本道
            (2, (1, 1)),  # (1,0) の分岐で乱数の戻り値 DOWN の方向へ前進
            (3, (1, 0)),  # (1,1) は行き止まり：(1,0) へ後退
            (4, (2, 0)),  # (1,0) の残る未探索方向 RIGHT へ前進し直す（前進復帰）
            (5, (1, 0)),  # (2, 0) は行き止まり：(1,0) へ後退
            (6, (0, 0)),  # (1,0) はもう未探索方向がない：(0,0) へ後退
            (7, (0, 0)),  # (0,0) も未探索方向がなく、これ以上戻れない：停止
        ]
        for num_kicks, expected_position in test_cases:
            with self.subTest(num_kicks=num_kicks):
                with fixed_maze(3, 2, self._BRANCH_GRID):
                    with patch("src.main.random.choice", return_value=Direction.DOWN):
                        maze = Maze()
                        for _ in range(num_kicks):
                            maze.kick()
                self.assertEqual(expected_position, maze.get_mob_position())

    def test_mob_does_not_move_after_backtracking_to_start_with_no_unexplored_neighbor(
        self,
    ):
        """分岐を探索し尽くして後退でスタートまで戻った後、キックしても位置が変わらないこと"""
        test_cases = [0, 1, 2, 3]  # スタートまで戻った後の追加キック回数
        for extra_kicks in test_cases:
            with self.subTest(extra_kicks=extra_kicks):
                with fixed_maze(3, 1, self._START_DEAD_END_GRID):
                    maze = Maze()
                    maze.kick()  # (0,0) -> (1,0)：行き止まりへ前進
                    maze.kick()  # (1,0)：未探索方向がないため (0,0) へ後退
                    for _ in range(extra_kicks):
                        maze.kick()
                    self.assertEqual((0, 0), maze.get_mob_position())

    def test_is_visited_reflects_whether_the_mob_has_passed_through_the_cell(self):
        """探索済み問い合わせが、モブの通過状況を正しく反映すること"""
        test_cases = [
            (0, Maze.START, True),  # 生成直後: モブがいるスタートは探索済み
            (0, (1, 0), False),  # 生成直後: スタート以外は探索済みでない
            (0, (2, 0), False),
            (1, (1, 0), True),  # 1 回キック: 通過したセルが探索済みになる
            (1, (2, 0), False),  # 一本道の先のまだ通っていないセルは探索済みでない
        ]
        for num_kicks, cell, expected in test_cases:
            with self.subTest(num_kicks=num_kicks, cell=cell):
                with fixed_maze(3, 1, self._VISITED_QUERY_GRID):
                    maze = Maze()
                    for _ in range(num_kicks):
                        maze.kick()
                self.assertEqual(expected, maze.is_visited(*cell))


# ゲーム状態（探索中/クリア/ゲームオーバー）の導出は移動の規則とは別の関心事であり、
# TestMazeMobMovement とは別クラスに分ける。フィクスチャは訂正 D のとおり
# TestMazeMobMovement のクラス属性を直接使えないため再定義する（ID-006_subtasks.md
# 「未決事項」で決定した既存の書き方 = _ONE_WAY_GRID の重複定義と同じ扱い）
class TestMazeGameState(unittest.TestCase):
    # 一本道（2 列 1 行）。1 回キックするとゴール (1, 0) に到達する
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    # スタート (0,0) が行き止まり (1,0) に 1 本だけつながる盤面（3 列 1 行）。
    # GOAL は fixed_maze により (2,0) になり、行き止まりやスタートとは別セルになる
    _START_DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    def test_exploring_right_after_generation(self):
        """生成直後（モブがスタートにいて未探索の道がある）は探索中であること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            maze = Maze()
            self.assertEqual(GameState.EXPLORING, maze.state)

    def test_cleared_when_the_mob_reaches_the_goal(self):
        """モブがゴールに到達した時点でクリアになること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)：唯一の道の先がゴール
            self.assertEqual(GameState.CLEARED, maze.state)

    def test_still_exploring_at_a_dead_end_before_retreating(self):
        """行き止まりに達した直後、まだ後退していない間は探索中のままであること"""
        with fixed_maze(3, 1, self._START_DEAD_END_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)：行き止まりへ前進
            self.assertEqual(GameState.EXPLORING, maze.state)

    def test_game_over_after_retreating_to_start_with_no_unexplored_road(self):
        """後退し切ってスタートへ戻り、進める未探索の道がなくなった時点で
        ゲームオーバーであること"""
        with fixed_maze(3, 1, self._START_DEAD_END_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)：行き止まりへ前進
            maze.kick()  # (1,0)：未探索方向がないため (0,0) へ後退
            self.assertEqual(GameState.GAME_OVER, maze.state)

    def test_game_over_when_taught_at_start_removes_the_last_road(self):
        """スタート地点で「教える」を行い、進める道がなくなった場合も
        ゲームオーバーであること"""
        with fixed_maze(3, 1, self._START_DEAD_END_GRID):
            maze = Maze()
            maze.teach()  # スタートにブロックを置き、進める道をなくす
            self.assertEqual(GameState.GAME_OVER, maze.state)

    def test_cleared_and_game_over_are_never_both_true(self):
        """クリアとゲームオーバーが同時に成立しないこと（スタートとゴールは別セル、
        状態は3値のうちちょうど1つに決まる）"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            maze = Maze()
            maze.kick()  # ゴールへ到達
            self.assertIn(maze.state, {GameState.CLEARED, GameState.EXPLORING})
            self.assertNotEqual(GameState.GAME_OVER, maze.state)


# ブロックの記録・問い合わせは移動の規則（前進の抑止・戻るモード）とは別の関心事であり、
# 盤面も「教える」を呼ぶタイミングだけが変わる最小のものでよいため、
# TestMazeMobMovement とは別クラスに分ける（ID-006_subtasks.md「未決事項」で決定）
class TestMazeBlocks(unittest.TestCase):
    # 一本道（2 列 1 行）。ブロックの記録・問い合わせだけを問うため、
    # 分岐や行き止まりは持たない最小の盤面にする
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    # (0,0) から (1,0) への一本道の先に、(2,0)・(1,1) への分岐がある盤面
    # （TestMazeMobMovement._BRANCH_GRID と同型）。教えた枝から退いた後、
    # もう一方の未探索の枝へ進み直すことを使って「異なる2地点」を作る
    # （前進の抑止＝006-3 が入った後もブロックを移動なしに2つ作る一本道が
    # 組めないため、盤面を分岐に変更した）
    _BRANCH_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT, Direction.DOWN},
        (2, 0): {Direction.LEFT},
        (1, 1): {Direction.UP},
    }

    def test_no_cell_is_blocked_right_after_generation(self):
        """迷路生成直後は、どのセルにもブロックが置かれていないこと"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            maze = Maze()
        self.assertEqual([], maze.get_blocked_positions())

    def test_teach_places_a_block_at_the_mobs_current_position(self):
        """「教える」を受けると、その時点でモブがいるセルだけがブロックになること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)
            maze.teach()
        self.assertEqual([(1, 0)], maze.get_blocked_positions())

    def test_teaching_twice_at_different_positions_keeps_both_blocks(self):
        """モブが移動した後にもう一度「教える」を受けても、
        両方のセルがブロックのまま残ること"""
        with fixed_maze(3, 2, self._BRANCH_GRID):
            with patch("src.main.random.choice", return_value=Direction.RIGHT):
                maze = Maze()
                maze.kick()  # (0,0) -> (1,0)
                maze.kick()  # 分岐で乱数の戻り値 RIGHT の方向へ： (1,0) -> (2,0)
                maze.teach()  # (2,0) にブロック（前進の抑止で (1,0) へ後退する）
                maze.kick()  # (2,0) -> (1,0)：後退
                maze.kick()  # (1,0) の残る未探索方向 DOWN へ： (1,0) -> (1,1)
                maze.teach()  # (1,1) にもブロック
        self.assertEqual([(1, 1), (2, 0)], maze.get_blocked_positions())

    def test_teaching_the_same_cell_twice_does_not_break_state(self):
        """同じセルで二度「教える」を受けても、状態が壊れないこと"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            maze = Maze()
            maze.teach()
            maze.teach()
        self.assertEqual([(0, 0)], maze.get_blocked_positions())


# ブロックが移動規則（前進の抑止）に与える影響を問うため、記録・問い合わせのみを
# 問う TestMazeBlocks とは分ける（ID-006_subtasks.md 006-3 のテストの意図）
class TestMazeBlockedMovement(unittest.TestCase):
    # 4 列 1 行の一本道。(2,0) は行き止まりではなく、教えなければ (3,0)（GOAL）へ
    # 進めてしまう点が 006-3 の観点（行き止まりでの後退と区別するため）
    _ONE_WAY_WITH_FORWARD_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT, Direction.RIGHT},
        (3, 0): {Direction.LEFT},
    }

    def test_mob_retreats_on_the_next_kick_after_teaching_while_advancing(self):
        """未探索の道を前進中に「教える」を受けると、次のキックでその先(未探索の
        (3,0))へ進まず、1 セル手前へ戻ること"""
        with fixed_maze(4, 1, self._ONE_WAY_WITH_FORWARD_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)
            maze.kick()  # (1,0) -> (2,0)
            maze.teach()  # (2,0) にブロック
            maze.kick()  # (3,0) へ進まず、来た (1,0) へ戻る
        self.assertEqual((1, 0), maze.get_mob_position())

    def test_mob_never_advances_beyond_a_blocked_cell_afterward(self):
        """ブロックを置いたセルの先にある未探索の道へは、その後も進まないこと
        （後退し切ってスタートで停止するまで、(3,0)/GOAL へ到達しないこと）"""
        test_cases = [
            (0, (1, 0)),  # 教えた直後の後退（上のテストと同じ地点）
            (1, (0, 0)),  # (1,0) も未探索方向がなく (0,0) へ後退
            (2, (0, 0)),  # (0,0) も未探索方向がなく、これ以上戻れず停止
        ]
        for extra_kicks, expected_position in test_cases:
            with self.subTest(extra_kicks=extra_kicks):
                with fixed_maze(4, 1, self._ONE_WAY_WITH_FORWARD_GRID):
                    maze = Maze()
                    maze.kick()  # (0,0) -> (1,0)
                    maze.kick()  # (1,0) -> (2,0)
                    maze.teach()  # (2,0) にブロック
                    maze.kick()  # (2,0) -> (1,0)：後退
                    for _ in range(extra_kicks):
                        maze.kick()
                self.assertEqual(expected_position, maze.get_mob_position())

    # (0,0) から (1,0) への一本道の先に、(2,0)・(1,1) への行き止まりの分岐がある盤面
    # （TestMazeMobMovement._BRANCH_GRID と同型）。分岐セル (1,0) で一方の枝
    # A(RIGHT) を先に探索させ、戻った分岐セルを教えるかどうかで、もう一方の
    # 未探索の枝 B(DOWN) へ前進を再開するかどうかが変わることを確認する
    _BRANCH_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT, Direction.DOWN},
        (2, 0): {Direction.LEFT},
        (1, 1): {Direction.UP},
    }

    def test_mob_keeps_retreating_when_the_branch_cell_is_taught_after_returning(
        self,
    ):
        """分岐セルから枝 A(RIGHT) へ進んで行き止まりに達し、戻った分岐セルで
        「教える」を受けると、未探索の枝 B(DOWN) へは進まず戻り続けること"""
        test_cases = [
            (0, (1, 0)),  # A の行き止まりから後退し、分岐セルを教えた直後
            (1, (0, 0)),  # B(DOWN) へ進まず、スタートへ後退
            (2, (0, 0)),  # (0,0) も未探索方向がなく、これ以上戻れず停止
        ]
        for extra_kicks, expected_position in test_cases:
            with self.subTest(extra_kicks=extra_kicks):
                with fixed_maze(3, 2, self._BRANCH_GRID):
                    with patch("src.main.random.choice", return_value=Direction.RIGHT):
                        maze = Maze()
                        maze.kick()  # (0,0) -> (1,0)：一本道
                        maze.kick()  # 分岐で A(RIGHT) へ前進：(1,0) -> (2,0)
                        maze.kick()  # (2,0) は行き止まり：(1,0) へ後退
                        maze.teach()  # 戻った分岐セル (1,0) を教える
                        for _ in range(extra_kicks):
                            maze.kick()
                self.assertEqual(expected_position, maze.get_mob_position())

    def test_mob_resumes_forward_into_the_unblocked_branch_when_not_taught(self):
        """分岐セルから枝 A(RIGHT) へ進んで行き止まりに達し、戻った分岐セルを
        教えなければ、未探索の枝 B(DOWN) へ前進を再開すること。
        再開後に A(2,0) へ戻ることもないこと"""
        test_cases = [
            (0, (1, 0)),  # A の行き止まりから後退した直後（分岐セルは教えない）
            (1, (1, 1)),  # 残る未探索方向 B(DOWN) へ前進を再開
            (2, (1, 0)),  # (1,1) も行き止まり：(1,0) へ後退
            (3, (0, 0)),  # (1,0) はもう未探索方向がない：(0,0) へ後退
            (4, (0, 0)),  # これ以上戻れず停止
        ]
        for extra_kicks, expected_position in test_cases:
            with self.subTest(extra_kicks=extra_kicks):
                with fixed_maze(3, 2, self._BRANCH_GRID):
                    with patch("src.main.random.choice", return_value=Direction.RIGHT):
                        maze = Maze()
                        maze.kick()  # (0,0) -> (1,0)
                        maze.kick()  # 分岐で A(RIGHT) へ前進：(1,0) -> (2,0)
                        maze.kick()  # (2,0) は行き止まり：(1,0) へ後退（教えない）
                        for _ in range(extra_kicks):
                            maze.kick()
                self.assertEqual(expected_position, maze.get_mob_position())


# スコアの算出規則は移動・ブロックの規則とは別の関心事のため、
# TestMazeGameState・TestMazeBlocks と同じ方針で別クラスに分ける（ID-010-1）
class TestMazeScore(unittest.TestCase):
    # 一本道（2 列 1 行）。スコアの算出は道の形に依存しないため、
    # 盤面の大きさだけが異なる一本道・空セルを用意する
    _GRID_2X1 = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}
    _GRID_3X1 = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }
    # 3 列 2 行（非正方）。COLS と ROWS の取り違えを検出するため正方形を避ける
    _GRID_3X2 = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
        (0, 1): set(),
        (1, 1): set(),
        (2, 1): set(),
    }

    # スタート (0,0) から (1,0) への一本道の先が行き止まりになる盤面（2 列 2 行）。
    # TestMazeMobMovement の同名グリッドと同じ形（クラス属性を共有しないため再定義する。
    # ID-006_subtasks.md「未決事項」で決定した既存の書き方）
    _DEAD_END_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    # (0,0) から (1,0) への一本道の先に、(2,0)・(1,1) への分岐がある盤面。
    # 後退後の前進再開（resume）を確認するため TestMazeMobMovement と同じ形を再定義する
    _BRANCH_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT, Direction.DOWN},
        (2, 0): {Direction.LEFT},
        (1, 1): {Direction.UP},
    }

    def test_initial_score_is_the_number_of_cells_times_ten(self):
        """生成直後のスコアが「道の全セル数 × 10」であること。
        盤面の大きさを変えるとスコアも変わること（3x2 は COLS/ROWS の
        取り違えを検出するための非正方の盤面）"""
        test_cases = [
            (2, 1, self._GRID_2X1),
            (3, 1, self._GRID_3X1),
            (3, 2, self._GRID_3X2),
        ]
        for cols, rows, grid in test_cases:
            with self.subTest(cols=cols, rows=rows):
                with fixed_maze(cols, rows, grid):
                    maze = Maze()
                    self.assertEqual(cols * rows * 10, maze.score)

    def test_score_decreases_by_ten_for_each_newly_reached_cell(self):
        """モブが新しいセルへ到達するたびにスコアが 10 減ること
        （2 セル連続で前進すると 20 減ることも合わせて確認する三点測量）"""
        test_cases = [
            (0, 3 * 1 * 10),  # 生成直後: 減算なし
            (1, 3 * 1 * 10 - 10),  # 1 セル前進: 10 減る
            (2, 3 * 1 * 10 - 20),  # 2 セル連続前進: 20 減る
        ]
        for num_kicks, expected_score in test_cases:
            with self.subTest(num_kicks=num_kicks):
                with fixed_maze(3, 1, self._GRID_3X1):
                    maze = Maze()
                    for _ in range(num_kicks):
                        maze.kick()
                    self.assertEqual(expected_score, maze.score)

    def test_score_does_not_change_while_retreating_from_a_dead_end(self):
        """行き止まりから後退したフレームでは、既に到達済みのセルへ戻るだけなので
        スコアが変わらないこと"""
        with fixed_maze(2, 2, self._DEAD_END_GRID):
            maze = Maze()
            maze.kick()  # (0,0) -> (1,0)：行き止まりへ前進（-10）
            score_after_advance = maze.score
            maze.kick()  # (1,0)：未探索方向がないため (0,0) へ後退
            self.assertEqual(score_after_advance, maze.score)

    def test_score_only_decreases_for_the_newly_reached_cell_after_resuming_forward(
        self,
    ):
        """後退後に前進を再開しても、新しく到達したセルの分だけスコアが減ること
        （既に到達済みのセルを通過し直しても二重に減らない。「新しく到達した」の
        解釈を固定する）"""
        with fixed_maze(3, 2, self._BRANCH_GRID):
            with patch("src.main.random.choice", return_value=Direction.DOWN):
                maze = Maze()
                maze.kick()  # (0,0) -> (1,0)：一本道なので乱数は使われない
                maze.kick()  # (1,0) -> (1,1)：分岐で乱数の戻り値 DOWN の方向へ前進
                maze.kick()  # (1,1)：行き止まりのため (1,0) へ後退
                score_after_retreat = maze.score
                maze.kick()  # (1,0) の残る未探索方向 RIGHT へ前進し直す（(2,0) へ）
                self.assertEqual(score_after_retreat - 10, maze.score)

    def test_score_decreases_by_hundred_for_each_newly_placed_block(self):
        """「教える」で新しくブロックが置かれるとスコアが100減ること
        （異なる2地点でも同様に100ずつ減ることを合わせて確認する三点測量。
        地点間の移動による到達分・後退分の増減は「教える」直前直後の差分を
        比較することで打ち消し、ブロックによる減算だけを取り出す。
        スタート地点を教えると即ゲームオーバーになり以降キックできなくなる
        ため、分岐盤面を使って非スタートの2地点で教える）"""
        with fixed_maze(3, 2, self._BRANCH_GRID):
            with patch("src.main.random.choice", return_value=Direction.RIGHT):
                maze = Maze()
                maze.kick()  # (0,0) -> (1,0)：一本道
                maze.kick()  # 分岐で A(RIGHT) へ前進：(1,0) -> (2,0)（行き止まり）
                score_before_first_teach = maze.score
                maze.teach()  # (2,0) にブロック
                self.assertEqual(score_before_first_teach - 100, maze.score)
                maze.kick()  # ブロックにより (1,0) へ後退
                maze.kick()  # 残る未探索方向 B(DOWN) へ前進：(1,0) -> (1,1)（行き止まり）
                score_before_second_teach = maze.score
                maze.teach()  # (1,1) にブロック（異なる地点）
                self.assertEqual(score_before_second_teach - 100, maze.score)

    def test_score_does_not_change_when_teaching_an_already_blocked_cell(self):
        """既にブロックのある地点へ「教える」をもう一度受けても、
        スコアが変わらないこと（完了条件の明示項目）"""
        with fixed_maze(3, 1, self._GRID_3X1):
            maze = Maze()
            maze.teach()  # (0,0) にブロック：-100
            score_after_first_teach = maze.score
            maze.teach()  # 同じ (0,0) への2回目：ブロックは増えないため変化なし
            self.assertEqual(score_after_first_teach, maze.score)

    def test_score_can_go_negative_without_clamping_to_zero(self):
        """小さな盤面（2x1 = 初期20）で1回「教える」を受けるとスコアが-80になり、
        0でクランプされず負値のまま保持されること"""
        with fixed_maze(2, 1, self._GRID_2X1):
            maze = Maze()
            maze.teach()  # (0,0) にブロック：20 - 100 = -80
            self.assertEqual(-80, maze.score)
