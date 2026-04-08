import customtkinter as ctk

from app.core.theme import (
    BG_DARK,
    BG_CARD,
    BG_INPUT,
    ACCENT_GREEN,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER_COLOR,
    F_TITLE,
    F_BODY,
    F_BODY_B,
    F_SMALL,
)


class ConfigTab:
    def __init__(
        self,
        tabview,
        cfg,
        on_save_local=None,
        on_send_config=None,
    ):
        self.tabview = tabview
        self.cfg = cfg

        self.on_save_local = on_save_local
        self.on_send_config = on_send_config

        self.tab = None
        self.cfg_entries = {}

    def build(self):
        self.tab = self.tabview.tab("  CONFIGURACIÓN  ")
        self.tab.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.tab,
            text="CONFIGURACIÓN DEL SISTEMA",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(20, 10))

        card = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=10)
        card.pack(fill="x", padx=40, pady=10)

        params = [
            ("Espesor del alambre (mm)", "espesor_mm", "1.0", "0.1 – 25.0", "float"),
            ("Retardo freno (segundos)", "retardo_freno", "1.5", "0.0 – 10.0", "float"),
            ("Lógica freno  (1=NO, 0=NC)", "freno_no", "1", "0 o 1", "bool"),
            ("Dirección inicial  (1=→, 0=←)", "dir_inicial", "1", "0 o 1", "bool"),
            ("Vueltas prefreno", "vueltas_prefreno", "5", "1 – 50", "int"),
        ]

        self.cfg_entries = {}

        for label, key, default, hint, tipo in params:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)

            ctk.CTkLabel(
                row,
                text=label,
                font=ctk.CTkFont(*F_BODY),
                text_color=TEXT_PRIMARY,
                width=320,
                anchor="w",
            ).pack(side="left")

            val = str(self.cfg.get(key, default))
            entry = ctk.CTkEntry(
                row,
                fg_color=BG_INPUT,
                border_color=BORDER_COLOR,
                text_color=ACCENT_GREEN,
                font=ctk.CTkFont(*F_BODY),
                width=160,
                justify="center",
            )
            entry.insert(0, val)
            entry.pack(side="left", padx=10)

            self.cfg_entries[key] = (entry, tipo)

            ctk.CTkLabel(
                row,
                text=hint,
                font=ctk.CTkFont(*F_SMALL),
                text_color=TEXT_SECONDARY,
            ).pack(side="left", padx=10)

        br = ctk.CTkFrame(card, fg_color="transparent")
        br.pack(pady=16, padx=20, fill="x")

        ctk.CTkButton(
            br,
            text="💾  GUARDAR EN PC",
            command=self._handle_save_local,
            fg_color=BG_INPUT,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_PRIMARY,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            br,
            text="📤  GUARDAR Y ENVIAR AL CONTROLADOR",
            command=self._handle_send_config,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_DARK,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(
            card,
            text=(
                "Los parámetros se guardan en bobinadora_config.json y se envían "
                "al controlador automáticamente al conectar."
            ),
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
            wraplength=700,
        ).pack(pady=(0, 16))

    def _handle_save_local(self):
        if self.on_save_local:
            self.on_save_local()

    def _handle_send_config(self):
        if self.on_send_config:
            self.on_send_config()