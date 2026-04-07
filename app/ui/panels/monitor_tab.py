import customtkinter as ctk

from app.core.theme import (
    BG_CARD,
    BORDER_COLOR,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_YELLOW,
    ACCENT_BLUE,
    ACCENT_PURPLE,
    ACCENT_ORANGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    F_TITLE,
    F_BODY,
)


class MonitorTab:
    def __init__(self, tabview, on_clear=None):
        self.tabview = tabview
        self.on_clear = on_clear

        self.tab = None
        self.monitor_box = None

    def build(self):
        self.tab = self.tabview.tab("  MONITOR  ")
        self.tab.columnconfigure(0, weight=1)
        self.tab.rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(self.tab, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            hdr,
            text="MONITOR EN TIEMPO REAL",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="🗑 LIMPIAR",
            command=self._handle_clear,
            fg_color=BG_CARD,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_SECONDARY,
            height=40,
            width=130,
            font=ctk.CTkFont(*F_BODY),
        ).pack(side="right")

        self.monitor_box = ctk.CTkTextbox(
            self.tab,
            fg_color=BG_CARD,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont("Consolas", 14),
            border_color=BORDER_COLOR,
            border_width=1,
            state="disabled",
        )
        self.monitor_box.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self._configure_tags()

    def _configure_tags(self):
        tb = self.monitor_box._textbox
        tb.tag_config("error", foreground=ACCENT_RED)
        tb.tag_config("pause", foreground=ACCENT_YELLOW)
        tb.tag_config("ok", foreground=ACCENT_GREEN)
        tb.tag_config("info", foreground=ACCENT_BLUE)
        tb.tag_config("barrera", foreground=ACCENT_PURPLE)
        tb.tag_config("manual", foreground=ACCENT_ORANGE)
        tb.tag_config("normal", foreground=TEXT_PRIMARY)

    def append(self, text, tag="normal"):
        self.monitor_box.configure(state="normal")
        self.monitor_box._textbox.insert("end", text, tag)
        self.monitor_box._textbox.see("end")
        self.monitor_box.configure(state="disabled")

    def clear(self):
        self.monitor_box.configure(state="normal")
        self.monitor_box.delete("1.0", "end")
        self.monitor_box.configure(state="disabled")

    def _handle_clear(self):
        if self.on_clear:
            self.on_clear()
        else:
            self.clear()