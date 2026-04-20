import customtkinter as ctk
import tkinter as tk

from app.core.theme import (
    BG_CARD,
    BG_INPUT,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_YELLOW,
    ACCENT_BLUE,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_ON_ACCENT,
    BORDER_COLOR,
    F_TITLE,
    F_BODY,
    F_BODY_B,
    F_BIG,
    F_SMALL,
)


class PositionTab:
    def __init__(
        self,
        tabview,
        on_recipe_change=None,
        on_section_change=None,
        on_inc_vuelta=None,
        on_apply_position=None,
    ):
        self.tabview = tabview

        self.on_recipe_change = on_recipe_change
        self.on_section_change = on_section_change
        self.on_inc_vuelta = on_inc_vuelta
        self.on_apply_position = on_apply_position

        self.tab = None

        self.pos_recipe_var = tk.StringVar()
        self.pos_recipe_combo = None

        self.pos_sec_var = tk.StringVar(value="1")
        self.pos_sec_combo = None

        self.pos_sec_info = None
        self.pos_capa_var = tk.StringVar(value="--")
        self.pos_capa_info = None
        self.pos_vuelta_var = tk.StringVar(value="0.0")
        self.pos_summary = None

    def build(self):
        self.tab = self.tabview.tab("  POSICIÓN  ")
        self.tab.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.tab,
            text="REANUDAR DESDE POSICIÓN",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            self.tab,
            text=(
                "Introduce la vuelta acumulada desde el inicio de la sección. "
                "La capa se detecta automáticamente."
            ),
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
            wraplength=900,
        ).pack(pady=(0, 12))

        card = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=10)
        card.pack(fill="x", padx=40, pady=10)
        card.columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            card,
            text="Receta:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.pos_recipe_combo = ctk.CTkComboBox(
            card,
            variable=self.pos_recipe_var,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=BG_CARD,
            dropdown_fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
            width=320,
            command=self._handle_recipe_change,
        )
        self.pos_recipe_combo.grid(
            row=0, column=1, padx=10, pady=(20, 5), sticky="ew", columnspan=3
        )

        ctk.CTkLabel(
            card,
            text="Sección:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=1, column=0, padx=20, pady=10, sticky="w")

        self.pos_sec_combo = ctk.CTkComboBox(
            card,
            variable=self.pos_sec_var,
            values=["1"],
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=BG_CARD,
            dropdown_fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
            width=130,
            command=self._handle_section_change,
        )
        self.pos_sec_combo.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.pos_sec_info = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=ACCENT_PURPLE,
        )
        self.pos_sec_info.grid(
            row=1, column=2, padx=10, pady=10, sticky="w", columnspan=2
        )

        ctk.CTkLabel(
            card,
            text="Capa detectada:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=2, column=0, padx=20, pady=10, sticky="w")

        ctk.CTkLabel(
            card,
            textvariable=self.pos_capa_var,
            font=ctk.CTkFont(*F_BIG),
            text_color=ACCENT_ORANGE,
        ).grid(row=2, column=1, padx=10, pady=10, sticky="w")

        self.pos_capa_info = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=ACCENT_YELLOW,
        )
        self.pos_capa_info.grid(
            row=2, column=2, padx=20, pady=10, sticky="w", columnspan=2
        )

        ctk.CTkLabel(
            card,
            text="Vuelta acumulada:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=3, column=0, padx=20, pady=10, sticky="w")

        ctk.CTkEntry(
            card,
            textvariable=self.pos_vuelta_var,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(*F_BIG),
            width=210,
            justify="center",
        ).grid(row=3, column=1, padx=10, pady=10, sticky="w")

        vb = ctk.CTkFrame(card, fg_color="transparent")
        vb.grid(row=3, column=2, padx=5, pady=10, sticky="w", columnspan=2)

        for delta, label, color in [
            (100, "+100", ACCENT_GREEN),
            (10, "+10", ACCENT_GREEN),
            (1, "+1", ACCENT_BLUE),
            (-1, "-1", ACCENT_ORANGE),
            (-10, "-10", ACCENT_RED),
            (-100, "-100", ACCENT_RED),
        ]:
            ctk.CTkButton(
                vb,
                text=label,
                width=74,
                height=42,
                font=ctk.CTkFont("Consolas", 13, "bold"),
                fg_color=BG_INPUT,
                hover_color=BORDER_COLOR,
                text_color=color,
                command=lambda d=delta: self._handle_inc_vuelta(d),
            ).pack(side="left", padx=3)

        ctk.CTkLabel(
            card,
            text="Vueltas acumuladas desde inicio de sección — ej: S4 C5 = 461v",
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).grid(row=4, column=0, columnspan=4, padx=20, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            self.tab,
            text="▶  INICIAR DESDE ESTA POSICIÓN",
            command=self._handle_apply_position,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=TEXT_ON_ACCENT,
            height=62,
            width=500,
            font=ctk.CTkFont("Consolas", 18, "bold"),
        ).pack(pady=18)

        self.pos_summary = ctk.CTkLabel(
            self.tab,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=ACCENT_YELLOW,
        )
        self.pos_summary.pack()

    def _handle_recipe_change(self, value=None):
        if self.on_recipe_change:
            self.on_recipe_change(value)

    def _handle_section_change(self, value=None):
        if self.on_section_change:
            self.on_section_change(value)

    def _handle_inc_vuelta(self, delta):
        if self.on_inc_vuelta:
            self.on_inc_vuelta("vuelta", delta)

    def _handle_apply_position(self):
        if self.on_apply_position:
            self.on_apply_position()

    def set_recipe_values(self, values):
        self.pos_recipe_combo.configure(values=values)

    def set_recipe(self, value):
        self.pos_recipe_var.set(value)

    def get_recipe(self):
        return self.pos_recipe_var.get()

    def set_section_values(self, values):
        self.pos_sec_combo.configure(values=values)

    def set_section(self, value):
        self.pos_sec_var.set(value)

    def get_section(self):
        return self.pos_sec_var.get()

    def set_section_info(self, text):
        self.pos_sec_info.configure(text=text)

    def set_capa(self, value):
        self.pos_capa_var.set(value)

    def set_capa_info(self, text):
        self.pos_capa_info.configure(text=text)

    def set_vuelta(self, value):
        self.pos_vuelta_var.set(value)

    def get_vuelta(self):
        return self.pos_vuelta_var.get()

    def set_summary(self, text):
        self.pos_summary.configure(text=text)
