import unittest
from unittest.mock import patch
from src.main import IView, IInput, GameCore, Block, Ball


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_rect(self, x, y, w, h, col):
        self.call_params.append(("draw_rect", x, y, w, h, col))

    def draw_line(self, x1, y1, x2, y2, col):
        self.call_params.append(("draw_line", x1, y1, x2, y2, col))

    def draw_circ(self, x, y, r, col):
        self.call_params.append(("draw_circ", x, y, r, col))

    def get_call_params(self):
        return self.call_params


class TestInput(IInput):
    def __init__(self):
        self._btn_pressed = False
        self._btn_down = False
        self._btn_released = False
        self._mouse_x = 0
        self._mouse_y = 0

    def set_btn_pressed(self, pressed):
        self._btn_pressed = pressed

    def set_btn_down(self, down):
        self._btn_down = down

    def set_btn_released(self, released):
        self._btn_released = released

    def set_mouse_x(self, x):
        self._mouse_x = x

    def set_mouse_y(self, y):
        self._mouse_y = y

    def is_btn_pressed(self) -> bool:
        return self._btn_pressed

    def is_btn_down(self) -> bool:
        return self._btn_down

    def is_btn_released(self) -> bool:
        return self._btn_released

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.test_input = TestInput()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_view = self.patcher_view.start()
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_input.stop()
        self.patcher_view.stop()

    @staticmethod
    def _expected_frame_only():
        """壁・ボーダーラインのみの期待描画呼び出しリストを返す"""
        return [
            ("draw_rect", 0, 0, GameCore.SCREEN_WIDTH, GameCore.WALL_WIDTH, 7),
            ("draw_rect", 0, 0, GameCore.WALL_WIDTH, GameCore.SCREEN_HEIGHT, 7),
            (
                "draw_rect",
                GameCore.SCREEN_WIDTH - GameCore.WALL_WIDTH,
                0,
                GameCore.WALL_WIDTH,
                GameCore.SCREEN_HEIGHT,
                7,
            ),
            (
                "draw_line",
                0,
                GameCore.BORDER_Y,
                GameCore.SCREEN_WIDTH - 1,
                GameCore.BORDER_Y,
                2,
            ),
        ]

    @staticmethod
    def _expected_frame_and_blocks():
        """壁・ボーダーライン・ブロック群の期待描画呼び出しリストを返す"""
        return TestParent._expected_frame_only() + [
            (
                "draw_rect",
                GameCore.BLOCK_START_X + col * (Block.W + GameCore.BLOCK_MARGIN_X),
                GameCore.BLOCK_START_Y + row * (Block.H + GameCore.BLOCK_MARGIN_Y),
                Block.W,
                Block.H,
                8,
            )
            for row in range(GameCore.BLOCK_ROWS)
            for col in range(GameCore.BLOCK_COLS)
        ]


class TestBlock(unittest.TestCase):
    def test_block_draw(self):
        """Block.draw(view) が正しい位置・サイズで draw_rect を呼び出すこと"""
        view = TestView()
        block = Block(x=38, y=110)
        block.draw(view)
        self.assertEqual(
            view.get_call_params(),
            [("draw_rect", 38, 110, Block.W, Block.H, 8)],
        )

    def test_block_rise(self):
        """Block.rise(step) が y を step 分だけ減少させること"""
        block = Block(x=38, y=110)
        block.rise(9)
        self.assertEqual(block._y, 101)  # pylint: disable=W0212

    def test_block_rect(self):
        """Block.rect() が (_x, _y, W, H) のタプルを返すこと"""
        block = Block(x=38, y=110)
        self.assertEqual(block.rect(), (38, 110, Block.W, Block.H))

    def test_block_is_above(self):
        """Block.is_above(border_y) が y < border_y のとき True を返すこと"""
        cases = [
            ("above", 19, 20, True),
            ("on_border", 20, 20, False),
            ("below", 21, 20, False),
        ]
        for label, y, border_y, expected in cases:
            with self.subTest(case=label):
                block = Block(x=38, y=y)
                self.assertEqual(block.is_above(border_y), expected)


class TestBall(unittest.TestCase):
    def test_ball_move(self):
        """Ball.move() が速度分だけ位置を更新すること（正負両方向）"""
        cases = [
            ((75.0, 50.0), (1.0, 2.0), (76.0, 52.0)),
            ((75.0, 50.0), (-1.0, -2.0), (74.0, 48.0)),
        ]
        for (x, y), (vx, vy), (ex, ey) in cases:
            with self.subTest(vx=vx, vy=vy):
                ball = Ball(x, y, vx, vy)
                ball.move()
                self.assertAlmostEqual(ball.x, ex)
                self.assertAlmostEqual(ball.y, ey)

    def test_is_below(self):
        """Ball.is_below(bottom_y) が y+R >= bottom_y のとき True を返すこと"""
        ball_r = Ball.R
        cases = [
            # (label, by, bottom_y, expected)
            ("below", float(100 - ball_r), 100, True),  # y+ball_r = bottom_y（境界値）
            ("past", float(100 - ball_r + 1), 100, True),  # y+ball_r > bottom_y
            ("not_yet", float(100 - ball_r - 1), 100, False),  # y+ball_r < bottom_y
        ]
        for label, by, bottom_y, expected in cases:
            with self.subTest(case=label):
                ball = Ball(75.0, by, 0.0, 0.0)
                self.assertEqual(ball.is_below(bottom_y), expected)

    def test_ball_draw(self):
        """Ball.draw(view) が round() した座標で draw_circ を呼び出すこと"""
        view = TestView()
        ball = Ball(10.3, 20.7, 0.0, 0.0)
        ball.draw(view)
        self.assertEqual(view.get_call_params(), [("draw_circ", 10, 21, Ball.R, 7)])

    def test_is_hit(self):
        """is_hit: 衝突あり/なし/境界接触を検証する"""
        ball_r = Ball.R
        rect_x, rect_y, rect_w, rect_h = 10, 10, 20, 20
        # (label, bx, by, expected)
        cases = [
            # 矩形から十分離れた位置 → False
            ("no_collision", 50.0, 50.0, False),
            # 矩形右側から1ピクセル侵入: x + R - 1 = rect_x + rect_w → True
            (
                "collision",
                float(rect_x + rect_w + ball_r - 1),
                float(rect_y + rect_h // 2),
                True,
            ),
            # 境界ちょうど接触: x + R = rect_x → 条件 x + R > rect_x が不成立 → False
            (
                "boundary_miss",
                float(rect_x - ball_r),
                float(rect_y + rect_h // 2),
                False,
            ),
        ]
        for label, bx, by, expected in cases:
            with self.subTest(case=label):
                ball = Ball(bx, by, 0.0, 0.0)
                self.assertEqual(ball.is_hit(rect_x, rect_y, rect_w, rect_h), expected)

    def test_reflect_no_collision(self):
        """衝突なし: ボールが矩形に重なっていないとき位置・速度は変化しないこと"""
        ball = Ball(50.0, 50.0, -3.0, 0.0)
        ball.reflect(100, 100, 20, 20)
        self.assertAlmostEqual(ball.x, 50.0)
        self.assertAlmostEqual(ball.y, 50.0)
        self.assertAlmostEqual(ball.vx, -3.0)
        self.assertAlmostEqual(ball.vy, 0.0)

    def test_reflect_aabb_miss(self):
        """AABB外れ: x方向またはy方向が矩形範囲外のとき反射しないこと"""
        ball_r = Ball.R
        rect_x, rect_y, rect_w, rect_h = 10, 10, 20, 20
        # ボールが境界ちょうどで外れる4方向を検証する
        # (label, bx, by, vx, vy)
        cases = [
            # x-ball_r = rect_x+rect_w → x方向右側が外れる（y方向は重なる）
            ("x_right_miss", float(rect_x + rect_w + ball_r), 20.0, -3.0, 0.0),
            # x+ball_r = rect_x      → x方向左側が外れる（y方向は重なる）
            ("x_left_miss", float(rect_x - ball_r), 20.0, 3.0, 0.0),
            # y-ball_r = rect_y+rect_h → y方向下側が外れる（x方向は重なる）
            ("y_bottom_miss", 20.0, float(rect_y + rect_h + ball_r), 0.0, -3.0),
            # y+ball_r = rect_y        → y方向上側が外れる（x方向は重なる）
            ("y_top_miss", 20.0, float(rect_y - ball_r), 0.0, 3.0),
        ]
        for label, bx, by, vx, vy in cases:
            with self.subTest(case=label):
                ball = Ball(bx, by, vx, vy)
                ball.reflect(rect_x, rect_y, rect_w, rect_h)
                self.assertAlmostEqual(ball.x, bx, msg=f"{label}: x should not change")
                self.assertAlmostEqual(ball.y, by, msg=f"{label}: y should not change")
                self.assertAlmostEqual(
                    ball.vx, vx, msg=f"{label}: vx should not change"
                )
                self.assertAlmostEqual(
                    ball.vy, vy, msg=f"{label}: vy should not change"
                )

    def test_reflect_sides(self):
        """各方向の反射: 最小侵入方向に応じて速度・位置が鏡面反射されること"""
        ball_r = Ball.R
        rect_x, rect_y, rect_w, rect_h = 10, 10, 20, 20
        # pen_XXX=1 になるよう境界ギリギリの初期位置を設定する
        cases = [
            # (label, bx, by, vx, vy, ex, ey, evx, evy)
            # 右側から衝突: pen_right=1が最小 → vxが正、x鏡面反射
            (
                "right",
                32.0,
                20.0,
                -3.0,
                0.0,
                2 * (rect_x + rect_w + ball_r) - 32.0,
                20.0,
                3.0,
                0.0,
            ),
            # 左側から衝突: pen_left=1が最小 → vxが負、x鏡面反射
            ("left", 8.0, 20.0, 3.0, 0.0, 2 * (rect_x - ball_r) - 8.0, 20.0, -3.0, 0.0),
            # 下側から衝突: pen_bottom=1が最小 → vyが正、y鏡面反射
            (
                "bottom",
                20.0,
                32.0,
                0.0,
                -3.0,
                20.0,
                2 * (rect_y + rect_h + ball_r) - 32.0,
                0.0,
                3.0,
            ),
            # 上側から衝突: pen_top=1が最小 → vyが負、y鏡面反射
            ("top", 20.0, 8.0, 0.0, 3.0, 20.0, 2 * (rect_y - ball_r) - 8.0, 0.0, -3.0),
        ]
        for label, bx, by, vx, vy, ex, ey, evx, evy in cases:
            with self.subTest(side=label):
                ball = Ball(bx, by, vx, vy)
                ball.reflect(rect_x, rect_y, rect_w, rect_h)
                self.assertAlmostEqual(ball.x, ex, msg=f"{label}: x")
                self.assertAlmostEqual(ball.y, ey, msg=f"{label}: y")
                self.assertAlmostEqual(ball.vx, evx, msg=f"{label}: vx")
                self.assertAlmostEqual(ball.vy, evy, msg=f"{label}: vy")


class TestAimingDraw(TestParent):
    def test_arrow_drawn_with_direction(self):
        """押下中はマウス方向（クランプ含む）に矢印が描画されること"""
        lcx, lcy = GameCore.LEFT_CORNER_DIR
        rcx, rcy = GameCore.RIGHT_CORNER_DIR
        # 左右コーナー境界のすぐ内側の期待方向（x_cross が壁端±1 の地点）
        # x_cross = BALL_START_X + (dx/dy) * (BORDER_Y - BALL_START_Y)
        # 左: mouse=(WALL_WIDTH+1, BORDER_Y) → x_cross=3 > WALL_WIDTH(2) → クランプなし
        lbdx, lbdy = GameCore._make_dir(  # pylint: disable=W0212
            GameCore.WALL_WIDTH + 1 - GameCore.BALL_START_X,
            GameCore.BORDER_Y - GameCore.BALL_START_Y,
        )
        # 右: mouse=(SCREEN_WIDTH-WALL_WIDTH-1, BORDER_Y) → x_cross=147 < SCREEN_WIDTH-WALL_WIDTH(148) → クランプなし
        rbdx, rbdy = GameCore._make_dir(  # pylint: disable=W0212
            GameCore.SCREEN_WIDTH - GameCore.WALL_WIDTH - 1 - GameCore.BALL_START_X,
            GameCore.BORDER_Y - GameCore.BALL_START_Y,
        )
        cases = [
            # (mx, my, exp_dx, exp_dy)
            (GameCore.BALL_START_X, GameCore.BALL_START_Y + 1, 0.0, 1.0),  # 真下
            (GameCore.BALL_START_X + 3, GameCore.BALL_START_Y + 4, 0.6, 0.8),  # 斜め
            (0, 5, lcx, lcy),  # 上向き左側 → 左コーナークランプ
            (0, 15, lcx, lcy),  # 左コーナー角超過 → 左コーナークランプ
            (75, 100, 0.0, 1.0),  # 中央真下 → クランプなし
            (150, 15, rcx, rcy),  # 右コーナー角超過 → 右コーナークランプ
            (
                GameCore.WALL_WIDTH + 1,
                GameCore.BORDER_Y,
                lbdx,
                lbdy,
            ),  # 左境界のすぐ内側 → クランプなし
            (
                GameCore.SCREEN_WIDTH - GameCore.WALL_WIDTH - 1,
                GameCore.BORDER_Y,
                rbdx,
                rbdy,
            ),  # 右境界のすぐ内側 → クランプなし
        ]
        for mx, my, exp_dx, exp_dy in cases:
            with self.subTest(mx=mx, my=my):
                self.test_view.call_params.clear()
                self.test_input.set_btn_down(True)
                self.test_input.set_mouse_x(mx)
                self.test_input.set_mouse_y(my)
                core = GameCore()
                core.update()
                core.draw()
                end_x = round(GameCore.BALL_START_X + exp_dx * GameCore.ARROW_LENGTH)
                end_y = round(GameCore.BALL_START_Y + exp_dy * GameCore.ARROW_LENGTH)
                expected_calls = self._expected_frame_and_blocks() + [
                    (
                        "draw_line",
                        GameCore.BALL_START_X,
                        GameCore.BALL_START_Y,
                        end_x,
                        end_y,
                        7,
                    ),
                    (
                        "draw_circ",
                        GameCore.BALL_START_X,
                        GameCore.BALL_START_Y,
                        Ball.R,
                        7,
                    ),
                ]
                self.assertEqual(expected_calls, self.test_view.get_call_params())

    def test_arrow_not_drawn_when_not_pressed(self):
        """押下していない状態ではdraw()がフレームとブロックと発射地点ボールを描画すること"""
        core = GameCore()
        core.update()
        core.draw()
        expected_calls = self._expected_frame_and_blocks() + [
            ("draw_circ", GameCore.BALL_START_X, GameCore.BALL_START_Y, Ball.R, 7),
        ]
        self.assertEqual(
            expected_calls,
            self.test_view.get_call_params(),
            "押下していないときはフレームとブロックと発射地点ボールが描画されるべき",
        )

    def test_no_arrow_when_ball_flying(self):
        """ボール飛行中に btn_down=True にしても矢印が描画されないこと"""
        core = GameCore()
        core._ball = Ball(  # pylint: disable=W0212
            75.0, 100.0, 0.0, GameCore.BALL_SPEED
        )
        self.test_input.set_btn_down(True)
        self.test_input.set_mouse_x(GameCore.BALL_START_X)
        self.test_input.set_mouse_y(GameCore.BALL_START_Y + 10)
        core.update()
        self.test_view.call_params.clear()
        core.draw()
        after_y = round(100.0 + GameCore.BALL_SPEED)
        expected_calls = self._expected_frame_and_blocks() + [
            ("draw_circ", 75, after_y, Ball.R, 7),
        ]
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestBallDraw(TestParent):
    def test_ball_drawn_after_button_release(self):
        """ボタン押下後に離すと、フレーム・ブロック・ボールが描画されること"""
        self.test_input.set_btn_down(True)
        self.test_input.set_mouse_x(GameCore.BALL_START_X)
        self.test_input.set_mouse_y(GameCore.BALL_START_Y + 10)
        core = GameCore()
        core.update()
        self.test_input.set_btn_down(False)
        self.test_input.set_btn_released(True)
        core.update()
        self.test_view.call_params.clear()
        core.draw()
        # 発射フレームはアーリーリターンのためボールは静止: y = BALL_START_Y
        expected_calls = self._expected_frame_and_blocks() + [
            (
                "draw_circ",
                GameCore.BALL_START_X,
                GameCore.BALL_START_Y,
                Ball.R,
                7,
            ),
        ]
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestBallReflect(TestParent):
    def _make_core_with_ball(self, bx, by, vx, vy):
        """ボール位置・速度を設定した GameCore を返す（入力は非押下状態）"""
        core = GameCore()
        core._ball = Ball(bx, by, vx, vy)  # pylint: disable=W0212
        return core

    def test_wall_reflect(self):
        """各壁への反射後、ボールが正しい位置に描画されること"""
        left_b = GameCore.WALL_WIDTH + Ball.R  # 5
        right_b = GameCore.SCREEN_WIDTH - GameCore.WALL_WIDTH - Ball.R  # 145
        top_b = GameCore.WALL_WIDTH + Ball.R  # 5
        # (label, bx, by, vx, vy, expected_x, expected_y)
        # 初期位置は各境界値、速度±3で境界を越えさせ、鏡面反射後の座標を期待値とする
        cases = [
            (
                "left_wall",
                float(left_b),
                50.0,
                -3.0,
                1.0,
                2 * left_b - (left_b - 3.0),
                51.0,
            ),
            (
                "right_wall",
                float(right_b),
                50.0,
                3.0,
                1.0,
                2 * right_b - (right_b + 3.0),
                51.0,
            ),
            (
                "top_wall",
                75.0,
                float(top_b),
                1.0,
                -3.0,
                76.0,
                2 * top_b - (top_b - 3.0),
            ),
        ]
        for label, bx, by, vx, vy, ex, ey in cases:
            with self.subTest(wall=label):
                self.test_view.call_params.clear()
                core = self._make_core_with_ball(bx, by, vx, vy)
                core.update()
                core.draw()
                expected_calls = self._expected_frame_and_blocks() + [
                    ("draw_circ", round(ex), round(ey), Ball.R, 7),
                ]
                self.assertEqual(self.test_view.call_params, expected_calls)


class TestBallBottom(TestParent):
    def _make_core_with_ball(self, bx, by, vx, vy):
        """ボール位置・速度を設定した GameCore を返す（入力は非押下状態）"""
        core = GameCore()
        core._ball = Ball(bx, by, vx, vy)  # pylint: disable=W0212
        return core

    def test_ball_disappears_at_bottom(self):
        """ボールが下端に到達したとき update() 後の draw() で飛行ボールが消え発射地点ボールが描画されること"""
        # move() 後に y+R = SCREEN_HEIGHT ちょうど → 消滅・ブロック上昇 → 発射地点ボール表示
        by = GameCore.SCREEN_HEIGHT - Ball.R - GameCore.BALL_SPEED
        core = self._make_core_with_ball(75.0, by, 0.0, GameCore.BALL_SPEED)
        core.update()
        core.draw()
        step = Block.H + GameCore.BLOCK_MARGIN_Y
        expected_blocks = [
            (
                "draw_rect",
                GameCore.BLOCK_START_X + col * (Block.W + GameCore.BLOCK_MARGIN_X),
                GameCore.BLOCK_START_Y
                - step
                + row * (Block.H + GameCore.BLOCK_MARGIN_Y),
                Block.W,
                Block.H,
                8,
            )
            for row in range(GameCore.BLOCK_ROWS)
            for col in range(GameCore.BLOCK_COLS)
        ]
        expected_calls = (
            self._expected_frame_only()
            + expected_blocks
            + [
                ("draw_circ", GameCore.BALL_START_X, GameCore.BALL_START_Y, Ball.R, 7),
            ]
        )
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestBlockReflect(TestParent):
    def _make_core_flying(self, bx, by, vx, vy, block_x, block_y):
        """単一ブロックと飛行中ボールを持つ GameCore を返す（入力は非押下状態）"""
        core = GameCore()
        core._ball = Ball(bx, by, vx, vy)  # pylint: disable=W0212
        core._blocks = [Block(x=block_x, y=block_y)]  # pylint: disable=W0212
        return core

    def test_ball_reflects_off_block_right_side(self):
        """ブロック右側から当たると反射後の正しい位置にボールが描画されること"""
        block_x = GameCore.BLOCK_START_X
        block_y = GameCore.BLOCK_START_Y
        # move後にブロック右側へ侵入: pen_right=1 が最小
        # x_after_move = block_x + Block.W + Ball.R - 1 → pen_right = 1
        # bx = x_after_move + BALL_SPEED（move前に戻す）
        bx = float(block_x + Block.W + Ball.R - 1) + GameCore.BALL_SPEED
        by = float(block_y + Block.H // 2)
        vx = -GameCore.BALL_SPEED
        vy = 0.0
        x_after_move = float(block_x + Block.W + Ball.R - 1)
        ex = 2 * (block_x + Block.W + Ball.R) - x_after_move
        ey = by  # vy=0 なので変化なし
        # 2枚目のブロックをボールの経路外に配置してクリア状態を防ぐ
        block2_x = block_x + 50
        block2_y = block_y + 50
        self.test_view.call_params.clear()
        core = self._make_core_flying(bx, by, vx, vy, block_x, block_y)
        core._blocks.append(Block(x=block2_x, y=block2_y))  # pylint: disable=W0212
        core.update()
        core.draw()
        # 衝突ブロックは消滅、2枚目は残る
        expected_calls = self._expected_frame_only() + [
            ("draw_rect", block2_x, block2_y, Block.W, Block.H, 8),
            ("draw_circ", round(ex), round(ey), Ball.R, 7),
        ]
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestBlockDisappear(TestParent):
    def _make_core_flying(self, bx, by, vx, vy, blocks):
        """指定されたブロックリストと飛行中ボールを持つ GameCore を返す"""
        core = GameCore()
        core._ball = Ball(bx, by, vx, vy)  # pylint: disable=W0212
        core._blocks = blocks  # pylint: disable=W0212
        return core

    def _ball_hitting_block_from_right(self, block_x, block_y):
        """ブロック右側に侵入するボールの位置・速度を返す（pen_right=1 が最小）"""
        bx = float(block_x + Block.W + Ball.R - 1) + GameCore.BALL_SPEED
        by = float(block_y + Block.H // 2)
        vx = -GameCore.BALL_SPEED
        vy = 0.0
        return bx, by, vx, vy

    def test_only_hit_block_disappears(self):
        """複数ブロックが存在するとき、当たったブロックのみ消えること"""
        block_x = GameCore.BLOCK_START_X
        block_y = GameCore.BLOCK_START_Y
        # block2 はボールの反射先にない十分離れた位置（block_x+50）
        block2_x = block_x + 50
        block2_y = block_y
        bx, by, vx, vy = self._ball_hitting_block_from_right(block_x, block_y)
        # 反射後ボール位置（pen_right=1 で右側衝突）
        x_after_move = float(block_x + Block.W + Ball.R - 1)
        ex = 2 * (block_x + Block.W + Ball.R) - x_after_move
        ey = by
        blocks = [Block(x=block_x, y=block_y), Block(x=block2_x, y=block2_y)]
        core = self._make_core_flying(bx, by, vx, vy, blocks)
        core.update()
        core.draw()
        expected_calls = self._expected_frame_only() + [
            ("draw_rect", block2_x, block2_y, Block.W, Block.H, 8),
            ("draw_circ", round(ex), round(ey), Ball.R, 7),
        ]
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestGameClear(TestParent):

    def _make_clear_core(self):
        """クリア状態の GameCore を返すヘルパー"""
        core = GameCore()
        core._blocks = []  # pylint: disable=W0212
        core._ball = Ball(  # pylint: disable=W0212
            float(GameCore.BALL_START_X),
            float(GameCore.SCREEN_HEIGHT // 2),
            0.0,
            GameCore.BALL_SPEED,
        )
        core.update()  # _game_clear = True になる
        return core

    def _clear_text_positions(self):
        """2行テキスト（CLEAR / Click to restart）の (x, y) を返すヘルパー"""
        center_x = GameCore.POPUP_X + GameCore.POPUP_W // 2
        center_y = GameCore.POPUP_Y + GameCore.POPUP_H // 2
        # 2行テキストブロック: 5px + 4px gap + 5px = 14px
        line1_y = center_y - 14 // 2
        line2_y = line1_y + 5 + 4
        clear_x = (
            center_x - (5 * 4) // 2
        )  # "CLEAR" 5文字 = 20px (3px幅+1px余白=4px/文字)
        restart_x = (
            center_x - (16 * 4) // 2
        )  # "Click to restart" 16文字 = 64px (3px幅+1px余白=4px/文字)
        return (clear_x, line1_y), (restart_x, line2_y)

    def test_ball_stops_updating_after_clear(self):
        """クリア状態になった後、update() を呼んでもボールが動かないこと"""
        core = GameCore()
        core._blocks = []  # pylint: disable=W0212
        core._ball = Ball(  # pylint: disable=W0212
            float(GameCore.BALL_START_X),
            float(GameCore.SCREEN_HEIGHT // 2),
            0.0,
            GameCore.BALL_SPEED,
        )
        core.update()  # _blocks=[] → _game_clear=True、ボールが1回だけ動く
        core.update()  # ガード return → ボールは動かない
        self.test_view.call_params.clear()
        core.draw()
        # ブロックなし・クリア後の静止位置（1回分だけ移動した y）でボールが描画され、ポップアップも描画されること
        expected_y = round(GameCore.SCREEN_HEIGHT // 2 + GameCore.BALL_SPEED)
        (clear_x, clear_y), (restart_x, restart_y) = self._clear_text_positions()
        expected_calls = self._expected_frame_only() + [
            ("draw_circ", GameCore.BALL_START_X, expected_y, Ball.R, 7),
            (
                "draw_rect",
                GameCore.POPUP_X,
                GameCore.POPUP_Y,
                GameCore.POPUP_W,
                GameCore.POPUP_H,
                1,
            ),
            ("draw_text", clear_x, clear_y, "CLEAR"),
            ("draw_text", restart_x, restart_y, "Click to restart"),
        ]
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestPopupReset(TestParent):

    def _make_clear_core(self):
        """クリア状態の GameCore を返すヘルパー"""
        core = GameCore()
        core._blocks = []  # pylint: disable=W0212
        core._ball = Ball(  # pylint: disable=W0212
            float(GameCore.BALL_START_X),
            float(GameCore.SCREEN_HEIGHT // 2),
            0.0,
            GameCore.BALL_SPEED,
        )
        core.update()  # _game_clear = True になる
        return core

    def test_needs_reset_initial_value_is_false(self):
        """GameCore の初期状態で needs_reset が False を返すこと"""
        core = GameCore()
        self.assertFalse(core.needs_reset)

    def test_clear_popup_click_inside_sets_needs_reset(self):
        """クリアポップアップ内クリックで needs_reset が True になること（中央・各辺境界値）"""
        cx = GameCore.POPUP_X + GameCore.POPUP_W // 2
        cy = GameCore.POPUP_Y + GameCore.POPUP_H // 2
        cases = [
            ("center", cx, cy),
            ("left_edge", GameCore.POPUP_X, cy),
            ("right_edge", GameCore.POPUP_X + GameCore.POPUP_W - 1, cy),
            ("top_edge", cx, GameCore.POPUP_Y),
            ("bottom_edge", cx, GameCore.POPUP_Y + GameCore.POPUP_H - 1),
        ]
        for label, mx, my in cases:
            with self.subTest(case=label):
                core = self._make_clear_core()
                self.test_input.set_btn_released(True)
                self.test_input.set_mouse_x(mx)
                self.test_input.set_mouse_y(my)
                core.update()
                self.assertTrue(core.needs_reset)

    def test_clear_popup_click_outside_does_not_reset(self):
        """クリアポップアップ外クリックで needs_reset が False のままであること（各辺境界外値）"""
        cx = GameCore.POPUP_X + GameCore.POPUP_W // 2
        cy = GameCore.POPUP_Y + GameCore.POPUP_H // 2
        cases = [
            ("just_left", GameCore.POPUP_X - 1, cy),
            ("just_right", GameCore.POPUP_X + GameCore.POPUP_W, cy),
            ("just_above", cx, GameCore.POPUP_Y - 1),
            ("just_below", cx, GameCore.POPUP_Y + GameCore.POPUP_H),
        ]
        for label, mx, my in cases:
            with self.subTest(case=label):
                core = self._make_clear_core()
                self.test_input.set_btn_released(True)
                self.test_input.set_mouse_x(mx)
                self.test_input.set_mouse_y(my)
                core.update()
                self.assertFalse(core.needs_reset)

    def _make_game_over_core(self):
        """ゲームオーバー状態の GameCore を返すヘルパー"""
        core = GameCore()
        step = Block.H + GameCore.BLOCK_MARGIN_Y
        block = Block(GameCore.BLOCK_START_X, GameCore.BORDER_Y + step - 1)
        core._blocks = [block]  # pylint: disable=W0212
        core._ball = Ball(  # pylint: disable=W0212
            float(GameCore.BALL_START_X),
            float(GameCore.SCREEN_HEIGHT - Ball.R),
            0.0,
            0.0,
        )
        core.update()  # _game_over = True になる
        return core

    def test_game_over_popup_click_sets_needs_reset(self):
        """ゲームオーバー状態でもポップアップ内クリックで needs_reset が True になること"""
        core = self._make_game_over_core()
        self.test_input.set_btn_released(True)
        self.test_input.set_mouse_x(GameCore.POPUP_X + GameCore.POPUP_W // 2)
        self.test_input.set_mouse_y(GameCore.POPUP_Y + GameCore.POPUP_H // 2)
        core.update()
        self.assertTrue(core.needs_reset)

    def test_app_recreates_game_core_on_needs_reset(self):
        """App は needs_reset のとき GameCore を新規生成すること"""
        from src.main import App  # pylint: disable=C0415

        app = App.__new__(App)
        app._core = self._make_clear_core()
        original_core = app._core
        original_core._needs_reset = True  # pylint: disable=W0212
        app.update()
        self.assertIsNot(
            app._core, original_core, "needs_reset 時に GameCore が再生成されること"
        )


class TestGameOver(TestParent):

    def _make_game_over_core(self):
        """ゲームオーバー状態の GameCore を返すヘルパー"""
        core = GameCore()
        step = Block.H + GameCore.BLOCK_MARGIN_Y  # = 9
        # rise(step) 後に y < BORDER_Y になる位置（BORDER_Y + step - 1 = 28）
        block = Block(GameCore.BLOCK_START_X, GameCore.BORDER_Y + step - 1)
        core._blocks = [block]  # pylint: disable=W0212
        # is_below(SCREEN_HEIGHT) が True: y + R = (SCREEN_HEIGHT - R) + R = SCREEN_HEIGHT ✓
        core._ball = Ball(  # pylint: disable=W0212
            float(GameCore.BALL_START_X),
            float(GameCore.SCREEN_HEIGHT - Ball.R),
            0.0,
            0.0,
        )
        core.update()  # is_below → _advance_turn() → block.rise(9) → y=19 < 20 → _game_over=True
        return core

    def _game_over_text_positions(self):
        """2行テキスト（GAME OVER / Click to restart）の (x, y) を返すヘルパー"""
        center_x = GameCore.POPUP_X + GameCore.POPUP_W // 2
        center_y = GameCore.POPUP_Y + GameCore.POPUP_H // 2
        # 2行テキストブロック: 5px + 4px gap + 5px = 14px
        line1_y = center_y - 14 // 2
        line2_y = line1_y + 5 + 4
        # Pyxel デフォルトフォント: 3px幅 + 1px余白 = 4px/文字
        game_over_x = center_x - (9 * 4) // 2  # "GAME OVER" 9文字 = 36px
        restart_x = center_x - (16 * 4) // 2  # "Click to restart" 16文字 = 64px
        return (game_over_x, line1_y), (restart_x, line2_y)

    def test_game_over_popup_drawn(self):
        """ゲームオーバー状態で draw() を呼ぶと、正しい描画呼び出し列が生成されること"""
        core = self._make_game_over_core()
        self.test_input.set_btn_down(True)  # 矢印が出ないことも同時検証
        self.test_input.set_mouse_x(GameCore.BALL_START_X)
        self.test_input.set_mouse_y(GameCore.BORDER_Y + 50)
        core.update()
        self.test_view.call_params.clear()
        core.draw()
        block_y = GameCore.BORDER_Y - 1  # = 19: rise 後のブロック y
        (go_x, line1_y), (restart_x, line2_y) = self._game_over_text_positions()
        expected_calls = self._expected_frame_only() + [
            # ゲームオーバー後のブロック（y=19）
            ("draw_rect", GameCore.BLOCK_START_X, block_y, Block.W, Block.H, 8),
            # ゲームオーバー中は発射地点ボールを表示しない
            # ゲームオーバーポップアップ背景
            (
                "draw_rect",
                GameCore.POPUP_X,
                GameCore.POPUP_Y,
                GameCore.POPUP_W,
                GameCore.POPUP_H,
                1,  # 背景色: 青
            ),
            # ゲームオーバーテキスト（2行）
            ("draw_text", go_x, line1_y, "GAME OVER"),
            ("draw_text", restart_x, line2_y, "Click to restart"),
        ]
        self.assertEqual(self.test_view.call_params, expected_calls)


class TestBlocksDraw(TestParent):
    def test_blocks_drawn(self):
        """GameCore.draw() が壁・ボーダーライン・ブロック群・発射地点ボールを正しい順序で描画すること"""
        core = GameCore()
        core.draw()
        expected_calls = self._expected_frame_and_blocks() + [
            ("draw_circ", GameCore.BALL_START_X, GameCore.BALL_START_Y, Ball.R, 7),
        ]
        self.assertEqual(
            expected_calls,
            self.test_view.get_call_params(),
            f"描画呼び出しの順序・パラメータが期待値と異なる:\n期待: {expected_calls}\n実際: {self.test_view.get_call_params()}",
        )
