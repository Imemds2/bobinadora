import customtkinter as ctk

from app.core.theme import (
    BG_INPUT,
    BG_CARD,
    ACCENT_YELLOW,
    ACCENT_RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER_COLOR,
    F_BODY,
    F_SMALL,
)


class DerivacionRow(ctk.CTkFrame):
    def __init__(self, parent, vuelta=None, etiqueta=None, mensaje=None, on_delete=None):
        super().__init__(parent, fg_color=BG_INPUT, corner_radius=6)
        self.on_delete = on_delete
        self._build(vuelta, etiqueta, mensaje)

    def _build(self, vuelta, etiqueta, mensaje):
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x")

        ctk.CTkLabel(
            row1,
            text="⚡ Vuelta:",
            font=ctk.CTkFont(*F_BODY),
            text_color=ACCENT_YELLOW,
        ).pack(side="left", padx=(10, 4), pady=6)

        self.vuelta_entry = ctk.CTkEntry(
            row1,
            placeholder_text="ej: 15.5",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=ACCENT_YELLOW,
            font=ctk.CTkFont("Consolas", 14),
            width=130,
            justify="center",
        )
        if vuelta is not None:
            self.vuelta_entry.insert(0, str(vuelta))
        self.vuelta_entry.pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(
            row1,
            text="Etiqueta:",
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(14, 4))

        self.etiq_entry = ctk.CTkEntry(
            row1,
            placeholder_text="ej: TAP1",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Consolas", 14),
            width=120,
            justify="center",
        )
        if etiqueta:
            self.etiq_entry.insert(0, etiqueta)
        self.etiq_entry.pack(side="left", padx=6, pady=6)

        ctk.CTkButton(
            row1,
            text="✕",
            width=42,
            height=36,
            fg_color="transparent",
            hover_color=ACCENT_RED,
            text_color=ACCENT_RED,
            font=ctk.CTkFont("Consolas", 15, "bold"),
            command=lambda: self.on_delete(self) if self.on_delete else None,
        ).pack(side="left", padx=(6, 10), pady=6)

        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x")

        ctk.CTkLabel(
            row2,
            text="💬 Mensaje:",
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(10, 4), pady=(0, 8))

        self.msg_entry = ctk.CTkEntry(
            row2,
            placeholder_text="ej: INSERTAR PANTALLA",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=ACCENT_YELLOW,
            font=ctk.CTkFont("Consolas", 13),
            width=440,
        )
        if mensaje:
            self.msg_entry.insert(0, mensaje)
        self.msg_entry.pack(side="left", padx=6, pady=(0, 8))

    def get_vuelta(self):
        return self.vuelta_entry.get().strip()

    def get_etiqueta(self):
        return self.etiq_entry.get().strip()

    def get_mensaje(self):
        return self.msg_entry.get().strip()