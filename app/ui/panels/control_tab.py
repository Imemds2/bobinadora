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
    BORDER_COLOR,
    F_TITLE,
    F_HEAD,
    F_BODY,
    F_BODY_B,
    F_SMALL,
)

class ControlTab:
    def __init__(
        self,
        tabview,
        on_start=None,
        on_stop=None,
        on_reset=None,
        on_homing=None,
        on_run_recipe=None,
        on_manual_toggle=None,
        on_jog_left_single=None,
        on_jog_right_single=None,
        on_jog_left_press=None,
        on_jog_left_release=None,
        on_jog_right_press=None,
        on_jog_right_release=None,
    ):
        self.tabview = tabview

        self.on_start = on_start
        self.on_stop = on_stop
        self.on_reset = on_reset
        self.on_homing = on_homing
        self.on_run_recipe = on_run_recipe
        self.on_manual_toggle = on_manual_toggle

        self.on_jog_left_single = on_jog_left_single
        self.on_jog_right_single = on_jog_right_single
        self.on_jog_left_press = on_jog_left_press
        self.on_jog_left_release = on_jog_left_release
        self.on_jog_right_press = on_jog_right_press
        self.on_jog_right_release = on_jog_right_release

        self.tab = None
        self.alert_frame = None
        self.alert_label = None
        self.run_combo = None
        self.btn_manual = None

        self.jog_left_single = None
        self.jog_left_btn = None
        self.jog_right_btn = None
        self.jog_right_single = None
        self.jog_status = None
        self.jog_paso_actual = None
        self.jog_pos_label = None
        self.jog_paso_entry = None
        self.jog_paso_btns = {}

        self.run_recipe_var = tk.StringVar()
        self.jog_paso_var = tk.DoubleVar(value=1.0)

        self.esp_vueltas = tk.StringVar(value="0.0")
        self.esp_meta = tk.StringVar(value="--")
        self.esp_capa = tk.StringVar(value="--")
        self.esp_rpm = tk.StringVar(value="0")
        self.esp_sec = tk.StringVar(value="--")
        self.esp_tsec = tk.StringVar(value="--")

    def build(self):
        self.tab = self.tabview.tab("  CONTROL  ")
        self.tab.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        ctk.CTkLabel(
            self.tab,
            text="PANEL DE CONTROL",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=6, pady=(15, 10))

        self._build_metrics()
        self._build_alert()
        self._build_main_buttons()
        self._build_manual_mode()
        self._build_jog_panel()
        self._build_run_recipe()
    
    def _build_manual_mode(self):
        mf2 = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=8)
        mf2.grid(row=4, column=0, columnspan=6, sticky="ew", padx=20, pady=(0, 6))

        ctk.CTkLabel(
            mf2,
            text="MODO MANUAL — sin receta, motor libre con pedal",
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=16, pady=12)

        self.btn_manual = ctk.CTkButton(
            mf2,
            text="⚙  ACTIVAR MODO MANUAL",
            command=self._handle_manual_toggle,
            fg_color=ACCENT_ORANGE,
            hover_color="#CC6633",
            text_color=BG_INPUT,
            height=44,
            width=260,
            font=ctk.CTkFont(*F_BODY_B),
        )
        self.btn_manual.pack(side="right", padx=16, pady=10)


    def _build_jog_panel(self):
        jf = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=10)
        jf.grid(row=5, column=0, columnspan=6, sticky="ew", padx=20, pady=(0, 8))

        jog_title = ctk.CTkFrame(jf, fg_color="transparent")
        jog_title.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            jog_title,
            text="MOVIMIENTO MANUAL  (JOG HUSILLO)",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).pack(side="left")

        self.jog_pos_label = ctk.CTkLabel(
            jog_title,
            text="Pos: 0.00 cm",
            font=ctk.CTkFont("Consolas", 14, "bold"),
            text_color=ACCENT_BLUE,
        )
        self.jog_pos_label.pack(side="right")

        paso_frame = ctk.CTkFrame(jf, fg_color=BG_INPUT, corner_radius=8)
        paso_frame.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            paso_frame,
            text="  Paso por pulsación:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(10, 12), pady=10)

        self.jog_paso_btns = {}
        for mm in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]:
            lbl = (f"{mm:.1f}".rstrip("0").rstrip(".") or "0") + "mm"
            btn = ctk.CTkButton(
                paso_frame,
                text=lbl,
                width=72,
                height=40,
                font=ctk.CTkFont("Consolas", 13, "bold"),
                fg_color=BG_CARD,
                hover_color=BORDER_COLOR,
                text_color=TEXT_SECONDARY,
                corner_radius=6,
                command=lambda m=mm: self.set_jog_step(m),
            )
            btn.pack(side="left", padx=4, pady=8)
            self.jog_paso_btns[mm] = btn

        ctk.CTkLabel(
            paso_frame,
            text="  Manual:",
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(12, 4))

        self.jog_paso_entry = ctk.CTkEntry(
            paso_frame,
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont("Consolas", 13),
            width=80,
            justify="center",
        )
        self.jog_paso_entry.insert(0, "1.0")
        self.jog_paso_entry.pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            paso_frame,
            text="✓",
            width=40,
            height=40,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_INPUT,
            font=ctk.CTkFont("Consolas", 14, "bold"),
            command=self._apply_manual_jog_step_from_entry,
        ).pack(side="left", padx=(2, 10), pady=8)

        self.set_jog_step(1.0)

        jog_btn_row = ctk.CTkFrame(jf, fg_color="transparent")
        jog_btn_row.pack(pady=(0, 6))

        self.jog_left_single = ctk.CTkButton(
            jog_btn_row,
            text="◀  ←",
            fg_color="#1C3A5C",
            hover_color="#2A5580",
            text_color=ACCENT_BLUE,
            height=60,
            width=130,
            font=ctk.CTkFont("Consolas", 16, "bold"),
            corner_radius=8,
            command=self._handle_jog_left_single,
        )
        self.jog_left_single.pack(side="left", padx=6)

        self.jog_left_btn = ctk.CTkButton(
            jog_btn_row,
            text="◀◀  CONTINUO",
            fg_color="#1C3A5C",
            hover_color="#2A5580",
            text_color=ACCENT_BLUE,
            height=60,
            width=180,
            font=ctk.CTkFont("Consolas", 15, "bold"),
            corner_radius=8,
        )
        self.jog_left_btn.pack(side="left", padx=6)
        self.jog_left_btn.bind("<ButtonPress-1>", lambda e: self._handle_jog_left_press())
        self.jog_left_btn.bind("<ButtonRelease-1>", lambda e: self._handle_jog_left_release())

        center_frame = ctk.CTkFrame(
            jog_btn_row,
            fg_color=BG_INPUT,
            corner_radius=8,
            width=140,
        )
        center_frame.pack(side="left", padx=6)
        center_frame.pack_propagate(False)

        self.jog_status = ctk.CTkLabel(
            center_frame,
            text="◉ PARADO",
            font=ctk.CTkFont("Consolas", 11, "bold"),
            text_color=TEXT_SECONDARY,
        )
        self.jog_status.pack(expand=True, pady=(6, 2))

        self.jog_paso_actual = ctk.CTkLabel(
            center_frame,
            text="1.0mm",
            font=ctk.CTkFont("Consolas", 11),
            text_color=ACCENT_YELLOW,
        )
        self.jog_paso_actual.pack(expand=True, pady=(0, 6))

        self.jog_right_btn = ctk.CTkButton(
            jog_btn_row,
            text="CONTINUO  ▶▶",
            fg_color="#1C3A5C",
            hover_color="#2A5580",
            text_color=ACCENT_BLUE,
            height=60,
            width=180,
            font=ctk.CTkFont("Consolas", 15, "bold"),
            corner_radius=8,
        )
        self.jog_right_btn.pack(side="left", padx=6)
        self.jog_right_btn.bind("<ButtonPress-1>", lambda e: self._handle_jog_right_press())
        self.jog_right_btn.bind("<ButtonRelease-1>", lambda e: self._handle_jog_right_release())

        self.jog_right_single = ctk.CTkButton(
            jog_btn_row,
            text="→  ▶",
            fg_color="#1C3A5C",
            hover_color="#2A5580",
            text_color=ACCENT_BLUE,
            height=60,
            width=130,
            font=ctk.CTkFont("Consolas", 16, "bold"),
            corner_radius=8,
            command=self._handle_jog_right_single,
        )
        self.jog_right_single.pack(side="left", padx=6)

        nota_frame = ctk.CTkFrame(jf, fg_color="transparent")
        nota_frame.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            nota_frame,
            text="◀▶ Pulso exacto    ◀◀▶▶ Continuo (mantener)",
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).pack(side="left")

        ctk.CTkButton(
            nota_frame,
            text="⌂ IR A CERO",
            command=self._handle_homing,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_SECONDARY,
            height=34,
            width=130,
            font=ctk.CTkFont(*F_SMALL),
        ).pack(side="right")
    
    def _build_metrics(self):
        mf = ctk.CTkFrame(self.tab, fg_color="transparent")
        mf.grid(row=1, column=0, columnspan=6, sticky="ew", padx=20)
        mf.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        self._metric(mf, "VUELTAS", self.esp_vueltas, ACCENT_GREEN, 0)
        self._metric(mf, "PROX PARADA", self.esp_meta, ACCENT_YELLOW, 1)
        self._metric(mf, "CAPA", self.esp_capa, ACCENT_ORANGE, 2)
        self._metric(mf, "RPM", self.esp_rpm, ACCENT_BLUE, 3)
        self._metric(mf, "SECCIÓN", self.esp_sec, ACCENT_PURPLE, 4)
        self._metric(mf, "TIPO", self.esp_tsec, ACCENT_ORANGE, 5)

    def _build_alert(self):
        self.alert_frame = ctk.CTkFrame(
            self.tab,
            fg_color=BG_CARD,
            corner_radius=10,
            height=60,
        )
        self.alert_frame.grid(
            row=2,
            column=0,
            columnspan=6,
            sticky="ew",
            padx=20,
            pady=8,
        )
        self.alert_frame.pack_propagate(False)

        self.alert_label = ctk.CTkLabel(
            self.alert_frame,
            text="Sistema listo — Conecte el controlador",
            font=ctk.CTkFont("Consolas", 15, "bold"),
            text_color=TEXT_SECONDARY,
        )
        self.alert_label.pack(expand=True)

    def _build_main_buttons(self):
        bf = ctk.CTkFrame(self.tab, fg_color="transparent")
        bf.grid(row=3, column=0, columnspan=6, pady=10)

        self._ctrl_btn(
            bf, "▶  START", ACCENT_GREEN, "#00CC6A",
            BG_INPUT, self._handle_start, 0
        )
        self._ctrl_btn(
            bf, "■  STOP", ACCENT_RED, "#CC2222",
            TEXT_PRIMARY, self._handle_stop, 1
        )
        self._ctrl_btn(
            bf, "↺  RESET", ACCENT_YELLOW, "#CC9200",
            BG_INPUT, self._handle_reset, 2
        )
        self._ctrl_btn(
            bf, "⌂  HOMING", ACCENT_BLUE, "#4080CC",
            TEXT_PRIMARY, self._handle_homing, 3
        )

    def _build_run_recipe(self):
        qf = ctk.CTkFrame(self.tab, fg_color=BG_CARD, corner_radius=8)
        qf.grid(row=6, column=0, columnspan=6, sticky="ew", padx=20, pady=(0, 14))

        ctk.CTkLabel(
            qf,
            text="EJECUTAR RECETA",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(12, 6))

        qr = ctk.CTkFrame(qf, fg_color="transparent")
        qr.pack(fill="x", padx=15, pady=(0, 12))

        self.run_combo = ctk.CTkComboBox(
            qr,
            variable=self.run_recipe_var,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=BG_CARD,
            dropdown_fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
            width=360,
        )
        self.run_combo.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            qr,
            text="⚡  CARGAR Y EJECUTAR",
            command=self._handle_run_recipe,
            fg_color=ACCENT_BLUE,
            hover_color="#4080CC",
            text_color=TEXT_PRIMARY,
            height=46,
            width=230,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left")

    def _metric(self, parent, label, var, color, col):
        c = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
        c.grid(row=0, column=col, padx=5, pady=8, sticky="nsew")

        ctk.CTkLabel(
            c,
            text=label,
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(12, 3))

        ctk.CTkLabel(
            c,
            textvariable=var,
            font=ctk.CTkFont("Consolas", 26, "bold"),
            text_color=color,
        ).pack(pady=(0, 12))

    def _ctrl_btn(self, parent, text, color, hover, tc, cmd, col):
        ctk.CTkButton(
            parent,
            text=text,
            command=cmd,
            fg_color=color,
            hover_color=hover,
            text_color=tc,
            height=80,
            width=190,
            font=ctk.CTkFont("Consolas", 18, "bold"),
            corner_radius=10,
        ).grid(row=0, column=col, padx=10, pady=10)


    def set_manual_mode_active(self, active: bool):
        if active:
            self.btn_manual.configure(
                text="⚙  DESACTIVAR MODO MANUAL",
                fg_color=ACCENT_RED,
                hover_color="#CC2222",
                text_color=TEXT_PRIMARY,
            )
        else:
            self.btn_manual.configure(
                text="⚙  ACTIVAR MODO MANUAL",
                fg_color=ACCENT_ORANGE,
                hover_color="#CC6633",
                text_color=BG_INPUT,
            )

    def set_jog_step(self, mm: float):
        self.jog_paso_var.set(mm)

        for m, btn in self.jog_paso_btns.items():
            if abs(m - mm) < 0.001:
                btn.configure(
                    fg_color=ACCENT_YELLOW,
                    text_color=BG_INPUT,
                )
            else:
                btn.configure(
                    fg_color=BG_CARD,
                    text_color=TEXT_SECONDARY,
                )

        lbl = (f"{mm:.1f}".rstrip("0").rstrip(".") or "0") + "mm"

        if self.jog_paso_actual:
            self.jog_paso_actual.configure(text=lbl)

        if self.jog_paso_entry:
            self.jog_paso_entry.delete(0, "end")
            self.jog_paso_entry.insert(0, str(mm))

    def get_jog_step(self) -> float:
        return self.jog_paso_var.get()

    def get_jog_step_entry_value(self) -> str:
        return self.jog_paso_entry.get().strip()

    def _apply_manual_jog_step_from_entry(self):
        try:
            mm = float(self.jog_paso_entry.get().strip())
            if mm <= 0 or mm > 200:
                raise ValueError("fuera de rango")
            self.set_jog_step(mm)
        except ValueError:
            # Aquí no abrimos messagebox todavía para no meter lógica de negocio/UI modal.
            # Eso lo puede validar el main si quieres endurecerlo después.
            pass

    def set_jog_position(self, text: str):
        self.jog_pos_label.configure(text=text)

    def set_jog_status(self, text: str, color=TEXT_SECONDARY):
        self.jog_status.configure(text=text, text_color=color)

    def set_jog_running(self, direction: str):
        if direction == "left":
            self.jog_left_btn.configure(
                fg_color=ACCENT_BLUE,
                text_color=BG_INPUT,
            )
            self.jog_right_btn.configure(
                fg_color="#1C3A5C",
                text_color=ACCENT_BLUE,
            )
            self.jog_status.configure(
                text="◀◀",
                text_color=ACCENT_BLUE,
            )
        else:
            self.jog_right_btn.configure(
                fg_color=ACCENT_BLUE,
                text_color=BG_INPUT,
            )
            self.jog_left_btn.configure(
                fg_color="#1C3A5C",
                text_color=ACCENT_BLUE,
            )
            self.jog_status.configure(
                text="▶▶",
                text_color=ACCENT_BLUE,
            )

    def set_jog_stopped(self):
        for btn in [self.jog_left_btn, self.jog_right_btn]:
            btn.configure(
                fg_color="#1C3A5C",
                text_color=ACCENT_BLUE,
            )

        self.jog_status.configure(
            text="◉ PARADO",
            text_color=TEXT_SECONDARY,
        )

    def _handle_start(self):
        if self.on_start:
            self.on_start()

    def _handle_stop(self):
        if self.on_stop:
            self.on_stop()

    def _handle_reset(self):
        if self.on_reset:
            self.on_reset()

    def _handle_homing(self):
        if self.on_homing:
            self.on_homing()

    def _handle_run_recipe(self):
        if self.on_run_recipe:
            self.on_run_recipe()

    def set_alert(self, text, color=TEXT_SECONDARY):
        self.alert_label.configure(text=text, text_color=color)

    def set_run_recipes(self, values):
        self.run_combo.configure(values=values)

    def set_selected_run_recipe(self, value):
        self.run_recipe_var.set(value)

    def get_selected_run_recipe(self):
        return self.run_recipe_var.get()

    def set_vueltas(self, value):
        self.esp_vueltas.set(value)

    def set_meta(self, value):
        self.esp_meta.set(value)

    def set_capa(self, value):
        self.esp_capa.set(value)

    def set_rpm(self, value):
        self.esp_rpm.set(value)

    def set_seccion(self, value):
        self.esp_sec.set(value)

    def set_tipo(self, value):
        self.esp_tsec.set(value)

    def _handle_manual_toggle(self):
        if self.on_manual_toggle:
            self.on_manual_toggle()

    def _handle_jog_left_single(self):
        if self.on_jog_left_single:
            self.on_jog_left_single()

    def _handle_jog_right_single(self):
        if self.on_jog_right_single:
            self.on_jog_right_single()

    def _handle_jog_left_press(self):
        self.set_jog_running("left")
        if self.on_jog_left_press:
            self.on_jog_left_press()

    def _handle_jog_left_release(self):
        self.set_jog_stopped()
        if self.on_jog_left_release:
            self.on_jog_left_release()

    def _handle_jog_right_press(self):
        self.set_jog_running("right")
        if self.on_jog_right_press:
            self.on_jog_right_press()

    def _handle_jog_right_release(self):
        self.set_jog_stopped()
        if self.on_jog_right_release:
            self.on_jog_right_release()