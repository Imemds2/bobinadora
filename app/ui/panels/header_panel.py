import customtkinter as ctk

from app.core.theme import (
    BG_PANEL,
    ACCENT_GREEN,
    ACCENT_RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER_COLOR,
    F_TITLE,
    F_BODY,
    F_BODY_B,
)


class HeaderPanel:
    def __init__(self, parent, on_toggle_theme=None, theme_label="Claro"):
        self.parent = parent
        self.on_toggle_theme = on_toggle_theme
        self.theme_label = theme_label
        self.frame = None
        self.conn_indicator = None
        self.clock_label = None
        self.theme_button = None

    def build(self):
        self.frame = ctk.CTkFrame(
            self.parent,
            fg_color=BG_PANEL,
            height=68,
            corner_radius=0,
        )
        self.frame.pack(fill="x")
        self.frame.pack_propagate(False)

        ctk.CTkLabel(
            self.frame,
            text="⚙  BOBINADORA HMI",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=24)

        self.conn_indicator = ctk.CTkLabel(
            self.frame,
            text="● DESCONECTADO",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=ACCENT_RED,
        )
        self.conn_indicator.pack(side="right", padx=24)

        self.clock_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
        )
        self.clock_label.pack(side="right", padx=24)

        self.theme_button = ctk.CTkButton(
            self.frame,
            text=self._build_theme_button_text(),
            command=self._handle_toggle_theme,
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            height=36,
            width=130,
            font=ctk.CTkFont(*F_BODY),
        )
        self.theme_button.pack(side="right", padx=(0, 12))

        return self.frame

    def set_connection_status(self, connected: bool, info: str = ""):
        if connected:
            text = f"● {info}" if info else "● CONECTADO"
            self.conn_indicator.configure(
                text=text,
                text_color=ACCENT_GREEN,
            )
        else:
            self.conn_indicator.configure(
                text="● DESCONECTADO",
                text_color=ACCENT_RED,
            )

    def set_clock(self, text: str):
        self.clock_label.configure(text=text)

    def set_theme_label(self, theme_label: str):
        self.theme_label = theme_label
        if self.theme_button:
            self.theme_button.configure(text=self._build_theme_button_text())

    def _build_theme_button_text(self) -> str:
        icon = "🌙" if self.theme_label == "Oscuro" else "☀"
        return f"{icon} {self.theme_label}"

    def _handle_toggle_theme(self):
        if self.on_toggle_theme:
            self.on_toggle_theme()
