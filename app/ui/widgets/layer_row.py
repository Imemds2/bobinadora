import customtkinter as ctk

from app.core.theme import (
    BG_CARD,
    BG_INPUT,
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    TEXT_PRIMARY,
    TEXT_ON_ACCENT,
    BORDER_COLOR,
    DIR_FWD_COLOR,
    DIR_REV_COLOR,
)


class LayerRow(ctk.CTkFrame):
    def __init__(self, parent, num, meta=None, direction=True, on_delete=None):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=6)
        self.num = num
        self._direction = direction
        self.on_delete = on_delete
        self._build(meta)

    def _build(self, meta):
        self.num_label = ctk.CTkLabel(
            self,
            text=f"{self.num:2d}",
            width=70,
            font=ctk.CTkFont("Consolas", 16, "bold"),
            text_color=ACCENT_BLUE,
        )
        self.num_label.pack(side="left", padx=(12, 4), pady=10)

        self.meta_entry = ctk.CTkEntry(
            self,
            placeholder_text="ej: 65.0",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont("Consolas", 15),
            width=180,
            justify="center",
        )
        if meta is not None:
            self.meta_entry.insert(0, str(meta))
        self.meta_entry.pack(side="left", padx=10, pady=10)

        self.dir_btn = ctk.CTkButton(
            self,
            text=self._dir_text(),
            command=self._toggle_dir,
            fg_color=self._dir_color(),
            hover_color=self._dir_hover(),
            text_color=TEXT_ON_ACCENT,
            width=180,
            height=44,
            font=ctk.CTkFont("Consolas", 14, "bold"),
            corner_radius=8,
        )
        self.dir_btn.pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            self,
            text="✕",
            width=50,
            height=44,
            fg_color=BG_INPUT,
            hover_color=ACCENT_RED,
            text_color=ACCENT_RED,
            font=ctk.CTkFont("Consolas", 16, "bold"),
            command=lambda: self.on_delete(self) if self.on_delete else None,
        ).pack(side="left", padx=(4, 12), pady=10)

    def _dir_text(self):
        return "→  HACIA MAX" if self._direction else "←  HACIA MIN"

    def _dir_color(self):
        return DIR_FWD_COLOR if self._direction else DIR_REV_COLOR

    def _dir_hover(self):
        return "#00CC6A" if self._direction else "#CC2222"

    def _toggle_dir(self):
        self._direction = not self._direction
        self.dir_btn.configure(
            text=self._dir_text(),
            fg_color=self._dir_color(),
            hover_color=self._dir_hover(),
            text_color=TEXT_ON_ACCENT,
        )

    def update_num(self, n):
        self.num = n
        self.num_label.configure(text=f"{n:2d}")

    def get_meta(self):
        return self.meta_entry.get().strip()

    def get_direction(self):
        return self._direction
