class Button:
    ICON_SIZE = 16
    NORMAL_BG_COLOR = 0
    ACTIVE_BG_COLOR = 14
    DISABLED_BG_COLOR = 12

    def __init__(self, x, y, width, height, icon):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.icon = icon  # (u, v) tuple
        self._is_active = False

    @property
    def is_active(self):
        return self._is_active

    def set_active(self, active):
        self._is_active = active

    def is_clicked(self, mouse_x, mouse_y):
        return (
            self.x <= mouse_x < self.x + self.width
            and self.y <= mouse_y < self.y + self.height
        )

    def draw(self, view, count=None):
        if count == 0:
            bg = self.DISABLED_BG_COLOR
        elif self._is_active:
            bg = self.ACTIVE_BG_COLOR
        else:
            bg = self.NORMAL_BG_COLOR
        view.draw_rect(self.x, self.y, self.width, self.height, bg)
        view.draw_rectb(self.x, self.y, self.width, self.height, 7)
        u, v = self.icon
        icon_x = self.x + (self.width - self.ICON_SIZE) // 2
        icon_y = self.y + (self.height - self.ICON_SIZE) // 2
        view.draw_image(icon_x, icon_y, 1, u, v, self.ICON_SIZE, self.ICON_SIZE, 0)
        if count is not None:
            label = str(count) if count < 10 else "9+"
            view.draw_text(self.x + self.width - 8, self.y + self.height - 8, label)
