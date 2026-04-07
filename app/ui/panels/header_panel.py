import customtkinter as ctk

from app.core.theme import (
    BG_PANEL,
    ACCENT_GREEN,
    ACCENT_RED,
    TEXT_SECONDARY,
    F_TITLE,
    F_BODY,
    F_BODY_B,
)


class HeaderPanel:
    def __init__(self, parent):
        self.parent = parent
        self.frame = None
        self.conn_indicator = None
        self.clock_label = None

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
            text_color=ACCENT_GREEN,
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