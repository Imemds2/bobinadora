import customtkinter as ctk

from app.core.theme import (
    BG_CARD,
    BG_INPUT,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_YELLOW,
    ACCENT_BLUE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_ON_ACCENT,
    BORDER_COLOR,
    F_TITLE,
    F_HEAD,
    F_BODY,
    F_BODY_B,
)


class RecipesTab:
    def __init__(
        self,
        tabview,
        on_new_recipe=None,
        on_delete_recipe=None,
        on_send_to_controller=None,
        on_edit_recipe=None,
    ):
        self.tabview = tabview

        self.on_new_recipe = on_new_recipe
        self.on_delete_recipe = on_delete_recipe
        self.on_send_to_controller = on_send_to_controller
        self.on_edit_recipe = on_edit_recipe

        self.tab = None
        self.recipe_list_frame = None
        self.recipe_detail = None

    def build(self):
        self.tab = self.tabview.tab("  RECETAS  ")
        self.tab.columnconfigure(0, weight=1)
        self.tab.columnconfigure(1, weight=2)
        self.tab.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.tab,
            text="GESTIÓN DE RECETAS",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, pady=(15, 10))

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        left = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(15, 5), pady=(0, 15))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left,
            text="RECETAS LOCALES (JSON)",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, pady=(14, 6), padx=15, sticky="w")

        self.recipe_list_frame = ctk.CTkScrollableFrame(
            left,
            fg_color="transparent",
        )
        self.recipe_list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.recipe_list_frame.columnconfigure(0, weight=1)

        br = ctk.CTkFrame(left, fg_color="transparent")
        br.grid(row=2, column=0, pady=10, padx=10, sticky="ew")

        ctk.CTkButton(
            br,
            text="+ NUEVA",
            command=self._handle_new_recipe,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=TEXT_ON_ACCENT,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            br,
            text="🗑 BORRAR",
            command=self._handle_delete_recipe,
            fg_color=ACCENT_RED,
            hover_color="#CC2222",
            text_color=TEXT_ON_ACCENT,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

    def _build_right_panel(self):
        right = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(5, 15), pady=(0, 15))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right,
            text="DETALLE DE RECETA",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(14, 6), padx=15, anchor="w")

        self.recipe_detail = ctk.CTkTextbox(
            right,
            fg_color=BG_INPUT,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(*F_BODY),
            border_color=BORDER_COLOR,
            border_width=1,
            state="disabled",
        )
        self.recipe_detail.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        br2 = ctk.CTkFrame(right, fg_color="transparent")
        br2.pack(pady=(0, 12), padx=10, fill="x")

        ctk.CTkButton(
            br2,
            text="📤 ENVIAR AL CONTROLADOR",
            command=self._handle_send_to_controller,
            fg_color=ACCENT_BLUE,
            hover_color="#4080CC",
            text_color=TEXT_ON_ACCENT,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            br2,
            text="✏ EDITAR",
            command=self._handle_edit_recipe,
            fg_color=ACCENT_YELLOW,
            hover_color="#CC9200",
            text_color=TEXT_ON_ACCENT,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

    def _handle_new_recipe(self):
        if self.on_new_recipe:
            self.on_new_recipe()

    def _handle_delete_recipe(self):
        if self.on_delete_recipe:
            self.on_delete_recipe()

    def _handle_send_to_controller(self):
        if self.on_send_to_controller:
            self.on_send_to_controller()

    def _handle_edit_recipe(self):
        if self.on_edit_recipe:
            self.on_edit_recipe()

    def set_recipe_detail(self, text: str):
        self.recipe_detail.configure(state="normal")
        self.recipe_detail.delete("1.0", "end")
        self.recipe_detail.insert("1.0", text)
        self.recipe_detail.configure(state="disabled")

    def clear_recipe_detail(self):
        self.recipe_detail.configure(state="normal")
        self.recipe_detail.delete("1.0", "end")
        self.recipe_detail.configure(state="disabled")
