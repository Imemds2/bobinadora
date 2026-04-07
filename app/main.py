import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import time
import json
from datetime import datetime

from .serial_manager import SerialManager
from .recipe_manager import (
    validate_recipe,
    save_recipe,
    load_recipe,
    list_recipes,
    delete_recipe,
)
from .paths import CONFIG_FILE
from .protocol import parse_status_msg


# ── Paleta ────────────────────────────────────────────────────
BG_DARK        = "#0D1117"
BG_PANEL       = "#161B22"
BG_CARD        = "#1C2128"
BG_INPUT       = "#21262D"
ACCENT_GREEN   = "#00FF88"
ACCENT_RED     = "#FF3B3B"
ACCENT_YELLOW  = "#FFB800"
ACCENT_BLUE    = "#58A6FF"
ACCENT_ORANGE  = "#F78166"
ACCENT_PURPLE  = "#BC8CFF"
TEXT_PRIMARY   = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
BORDER_COLOR   = "#30363D"
DIR_FWD_COLOR  = "#00FF88"
DIR_REV_COLOR  = "#FF3B3B"

F_TITLE  = ("Consolas", 24, "bold")
F_HEAD   = ("Consolas", 16, "bold")
F_BODY   = ("Consolas", 14)
F_BODY_B = ("Consolas", 14, "bold")
F_BIG    = ("Consolas", 36, "bold")
F_SMALL  = ("Consolas", 12)

ESTADOS = {
    "0":  "IDLE",
    "1":  "BOBINANDO",
    "2":  "PREFRENO",
    "3":  "PAUSA CAPA",
    "4":  "DESBLOQ",
    "5":  "PAUSA DER",
    "6":  "DER DESBL",
    "7":  "ENTRE SEC",
    "8":  "TERMINADO",
    "9":  "JOG",
    "10": "BARRERA",
    "11": "PAUS BARR",
    "12": "HOMING",
    "13": "MANUAL",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def cargar_config() -> dict:
    defaults = {
        "espesor_mm": 1.0,
        "retardo_freno": 1.5,
        "freno_no": True,
        "dir_inicial": True,
        "vueltas_prefreno": 5,
        "puerto": "",
        "baudrate": 115200,
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
        except Exception:
            pass

    return defaults


def guardar_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BOBINADORA HMI  v5.3")
        self.geometry("1920x1080")
        self.minsize(1200, 750)
        self.configure(fg_color=BG_DARK)

        self.cfg = cargar_config()

        self.connected            = False
        self.current_recipe       = None
        self.selected_recipe_name = None
        self._jog_active          = False
        self._jog_direction       = "right"
        self._manual_activo       = False

        self.esp_estado   = tk.StringVar(value="IDLE")
        self.esp_rec      = tk.StringVar(value="--")
        self.esp_sec      = tk.StringVar(value="--")
        self.esp_tsec     = tk.StringVar(value="--")
        self.esp_capa     = tk.StringVar(value="--")
        self.esp_tcap     = tk.StringVar(value="--")
        self.esp_meta     = tk.StringVar(value="--")
        self.esp_vueltas  = tk.StringVar(value="0.0")
        self.esp_rpm      = tk.StringVar(value="0")
        self.esp_pos      = tk.StringVar(value="0.00cm")
        self.esp_freno    = tk.StringVar(value="--")
        self.esp_variador = tk.StringVar(value="--")

        # ── Primero construir UI ──────────────────────────────
        self._build_ui()
        self._refresh_ports()
        self._load_recipe_list()

        # ── Después crear serial (necesita UI lista) ──────────
        self.serial = SerialManager(
            on_message=lambda msg: self.after(
                0, lambda m=msg: self.on_serial_message(m)
            ),
            on_status_change=lambda ok, info: self.after(
                0, lambda o=ok, i=info: self.on_connection_change(o, i)
            ),
        )

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_sidebar(main)

        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_tabs(content)

    def _build_header(self):
        hdr = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            height=68,
            corner_radius=0,
        )
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="⚙  BOBINADORA HMI",
            font=ctk.CTkFont(*F_TITLE),
            text_color=ACCENT_GREEN,
        ).pack(side="left", padx=24)

        self.conn_indicator = ctk.CTkLabel(
            hdr,
            text="● DESCONECTADO",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=ACCENT_RED,
        )
        self.conn_indicator.pack(side="right", padx=24)

        self.clock_label = ctk.CTkLabel(
            hdr,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
        )
        self.clock_label.pack(side="right", padx=24)

        self._update_clock()

    def _build_sidebar(self, parent):
        sb = ctk.CTkFrame(
            parent,
            fg_color=BG_PANEL,
            width=270,
            corner_radius=8,
        )
        sb.grid(row=0, column=0, sticky="nsew")
        sb.pack_propagate(False)

        ctk.CTkLabel(
            sb,
            text="CONEXIÓN SERIAL",
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(18, 4), padx=15, anchor="w")

        self.port_var = tk.StringVar(value=self.cfg.get("puerto", ""))

        self.port_combo = ctk.CTkComboBox(
            sb,
            variable=self.port_var,
            width=240,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=BG_CARD,
            dropdown_fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
        )
        self.port_combo.pack(padx=15, pady=4)

        ctk.CTkButton(
            sb,
            text="⟳  ACTUALIZAR",
            command=self._refresh_ports,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_SECONDARY,
            height=36,
            font=ctk.CTkFont(*F_SMALL),
        ).pack(padx=15, pady=3, fill="x")

        self.btn_connect = ctk.CTkButton(
            sb,
            text="CONECTAR",
            command=self._toggle_connect,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_DARK,
            height=44,
            font=ctk.CTkFont(*F_BODY_B),
        )
        self.btn_connect.pack(padx=15, pady=(4, 12), fill="x")

        ctk.CTkFrame(
            sb,
            height=1,
            fg_color=BORDER_COLOR,
        ).pack(fill="x", padx=15)

        ctk.CTkLabel(
            sb,
            text="ESTADO CONTROLADOR",
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(10, 4), padx=15, anchor="w")

        self._ind(sb, "ESTADO",   self.esp_estado,   ACCENT_BLUE)
        self._ind(sb, "RECETA",   self.esp_rec,      ACCENT_YELLOW)
        self._ind(sb, "SECCIÓN",  self.esp_sec,      ACCENT_PURPLE)
        self._ind(sb, "TIPO",     self.esp_tsec,     ACCENT_ORANGE)
        self._ind(sb, "CAPA",     self.esp_capa,     ACCENT_YELLOW)
        self._ind(sb, "TOTAL C.", self.esp_tcap,     TEXT_SECONDARY)
        self._ind(sb, "PROX PAR", self.esp_meta,     ACCENT_GREEN)
        self._ind(sb, "VUELTAS",  self.esp_vueltas,  ACCENT_GREEN)
        self._ind(sb, "RPM",      self.esp_rpm,      ACCENT_ORANGE)
        self._ind(sb, "POSICIÓN", self.esp_pos,      ACCENT_BLUE)

        ctk.CTkFrame(
            sb,
            height=1,
            fg_color=BORDER_COLOR,
        ).pack(fill="x", padx=15, pady=6)

        fv = ctk.CTkFrame(sb, fg_color=BG_CARD, corner_radius=6)
        fv.pack(padx=15, fill="x")

        ctk.CTkLabel(
            fv,
            textvariable=self.esp_freno,
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=10, pady=8)

        ctk.CTkLabel(
            fv,
            textvariable=self.esp_variador,
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(side="right", padx=10, pady=8)

    def _ind(self, parent, label, var, color):
        f = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=6)
        f.pack(padx=15, pady=2, fill="x")

        ctk.CTkLabel(
            f,
            text=label,
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
            width=80,
        ).pack(side="left", padx=8, pady=5)

        ctk.CTkLabel(
            f,
            textvariable=var,
            font=ctk.CTkFont("Consolas", 13, "bold"),
            text_color=color,
        ).pack(side="right", padx=8)

    def _build_tabs(self, parent):
        self.tabview = ctk.CTkTabview(
            parent,
            fg_color=BG_PANEL,
            segmented_button_fg_color=BG_CARD,
            segmented_button_selected_color=ACCENT_GREEN,
            segmented_button_selected_hover_color="#00CC6A",
            segmented_button_unselected_color=BG_CARD,
            segmented_button_unselected_hover_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
        )
        self.tabview.pack(fill="both", expand=True)

        for t in [
            "  CONTROL  ",
            "  RECETAS  ",
            "  POSICIÓN  ",
            "  CONFIGURACIÓN  ",
            "  MONITOR  ",
        ]:
            self.tabview.add(t)

        self._build_control_tab()
        self._build_recipes_tab()
        self._build_position_tab()
        self._build_config_tab()
        self._build_monitor_tab()

    # ── TAB CONTROL ───────────────────────────────────────────
    def _build_control_tab(self):
        tab = self.tabview.tab("  CONTROL  ")
        tab.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        ctk.CTkLabel(
            tab,
            text="PANEL DE CONTROL",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=6, pady=(15, 10))

        mf = ctk.CTkFrame(tab, fg_color="transparent")
        mf.grid(row=1, column=0, columnspan=6, sticky="ew", padx=20)
        mf.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        self._metric(mf, "VUELTAS", self.esp_vueltas, ACCENT_GREEN, 0)
        self._metric(mf, "PROX PARADA", self.esp_meta, ACCENT_YELLOW, 1)
        self._metric(mf, "CAPA", self.esp_capa, ACCENT_ORANGE, 2)
        self._metric(mf, "RPM", self.esp_rpm, ACCENT_BLUE, 3)
        self._metric(mf, "SECCIÓN", self.esp_sec, ACCENT_PURPLE, 4)
        self._metric(mf, "TIPO", self.esp_tsec, ACCENT_ORANGE, 5)

        self.alert_frame = ctk.CTkFrame(
            tab,
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

        bf = ctk.CTkFrame(tab, fg_color="transparent")
        bf.grid(row=3, column=0, columnspan=6, pady=10)

        self._ctrl_btn(
            bf, "▶  START", ACCENT_GREEN, "#00CC6A",
            BG_DARK, self._cmd_start, 0
        )
        self._ctrl_btn(
            bf, "■  STOP", ACCENT_RED, "#CC2222",
            TEXT_PRIMARY, self._cmd_stop, 1
        )
        self._ctrl_btn(
            bf, "↺  RESET", ACCENT_YELLOW, "#CC9200",
            BG_DARK, self._cmd_reset, 2
        )
        self._ctrl_btn(
            bf, "⌂  HOMING", ACCENT_BLUE, "#4080CC",
            TEXT_PRIMARY, self._cmd_homing, 3
        )

        # ── Modo Manual ───────────────────────────────────────
        mf2 = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=8)
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
            command=self._cmd_manual_toggle,
            fg_color=ACCENT_ORANGE,
            hover_color="#CC6633",
            text_color=BG_DARK,
            height=44,
            width=260,
            font=ctk.CTkFont(*F_BODY_B),
        )
        self.btn_manual.pack(side="right", padx=16, pady=10)

        # ── Panel JOG ─────────────────────────────────────────
        jf = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
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

        self.jog_paso_var = tk.DoubleVar(value=1.0)
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
                command=lambda m=mm: self._set_jog_paso(m),
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
            text_color=BG_DARK,
            font=ctk.CTkFont("Consolas", 14, "bold"),
            command=self._set_jog_paso_manual,
        ).pack(side="left", padx=(2, 10), pady=8)

        self._set_jog_paso(1.0)

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
            command=lambda: self._jog_pulso("left"),
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
        self.jog_left_btn.bind(
            "<ButtonPress-1>",
            lambda e: self._jog_start("left")
        )
        self.jog_left_btn.bind(
            "<ButtonRelease-1>",
            lambda e: self._jog_stop()
        )

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
        self.jog_right_btn.bind(
            "<ButtonPress-1>",
            lambda e: self._jog_start("right")
        )
        self.jog_right_btn.bind(
            "<ButtonRelease-1>",
            lambda e: self._jog_stop()
        )

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
            command=lambda: self._jog_pulso("right"),
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
            command=self._cmd_homing,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_SECONDARY,
            height=34,
            width=130,
            font=ctk.CTkFont(*F_SMALL),
        ).pack(side="right")

        # Ejecutar receta
        qf = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=8)
        qf.grid(row=6, column=0, columnspan=6, sticky="ew", padx=20, pady=(0, 14))

        ctk.CTkLabel(
            qf,
            text="EJECUTAR RECETA",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(12, 6))

        qr = ctk.CTkFrame(qf, fg_color="transparent")
        qr.pack(fill="x", padx=15, pady=(0, 12))

        self.run_recipe_var = tk.StringVar()
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
            command=self._run_selected_recipe,
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

    # ── TAB RECETAS ───────────────────────────────────────────
    def _build_recipes_tab(self):
        tab = self.tabview.tab("  RECETAS  ")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="GESTIÓN DE RECETAS",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, pady=(15, 10))

        left = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=8)
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
            command=self._open_recipe_form,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_DARK,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            br,
            text="🗑 BORRAR",
            command=self._delete_selected_recipe,
            fg_color=ACCENT_RED,
            hover_color="#CC2222",
            text_color=TEXT_PRIMARY,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

        right = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=8)
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
            command=self._send_selected_to_esp,
            fg_color=ACCENT_BLUE,
            hover_color="#4080CC",
            text_color=TEXT_PRIMARY,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            br2,
            text="✏ EDITAR",
            command=self._edit_selected_recipe,
            fg_color=ACCENT_YELLOW,
            hover_color="#CC9200",
            text_color=BG_DARK,
            height=46,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="left", expand=True, fill="x", padx=3)

    # ── TAB POSICIÓN ──────────────────────────────────────────
    def _build_position_tab(self):
        tab = self.tabview.tab("  POSICIÓN  ")
        tab.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="REANUDAR DESDE POSICIÓN",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            tab,
            text=(
                "Introduce la vuelta acumulada desde el inicio de la sección. "
                "La capa se detecta automáticamente."
            ),
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
            wraplength=900,
        ).pack(pady=(0, 12))

        card = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
        card.pack(fill="x", padx=40, pady=10)
        card.columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            card,
            text="Receta:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.pos_recipe_var = tk.StringVar()
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
            command=self._on_pos_recipe_change,
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

        self.pos_sec_var = tk.StringVar(value="1")
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
            command=lambda v: self._update_pos_info(),
        )
        self.pos_sec_combo.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.pos_sec_info = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=ACCENT_PURPLE,
        )
        self.pos_sec_info.grid(row=1, column=2, padx=10, pady=10, sticky="w", columnspan=2)

        ctk.CTkLabel(
            card,
            text="Capa detectada:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=2, column=0, padx=20, pady=10, sticky="w")

        self.pos_capa_var = tk.StringVar(value="--")
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
        self.pos_capa_info.grid(row=2, column=2, padx=20, pady=10, sticky="w", columnspan=2)

        ctk.CTkLabel(
            card,
            text="Vuelta acumulada:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).grid(row=3, column=0, padx=20, pady=10, sticky="w")

        self.pos_vuelta_var = tk.StringVar(value="0.0")
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
                command=lambda d=delta: self._inc_pos("vuelta", d),
            ).pack(side="left", padx=3)

        ctk.CTkLabel(
            card,
            text="Vueltas acumuladas desde inicio de sección — ej: S4 C5 = 461v",
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
        ).grid(row=4, column=0, columnspan=4, padx=20, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            tab,
            text="▶  INICIAR DESDE ESTA POSICIÓN",
            command=self._apply_position,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_DARK,
            height=62,
            width=500,
            font=ctk.CTkFont("Consolas", 18, "bold"),
        ).pack(pady=18)

        self.pos_summary = ctk.CTkLabel(
            tab,
            text="",
            font=ctk.CTkFont(*F_BODY),
            text_color=ACCENT_YELLOW,
        )
        self.pos_summary.pack()

    # ── TAB CONFIGURACIÓN ─────────────────────────────────────
    def _build_config_tab(self):
        tab = self.tabview.tab("  CONFIGURACIÓN  ")
        tab.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="CONFIGURACIÓN DEL SISTEMA",
            font=ctk.CTkFont(*F_TITLE),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(20, 10))

        card = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
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
            command=self._guardar_config_local,
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
            command=self._enviar_config_esp,
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

    # ── TAB MONITOR ───────────────────────────────────────────
    def _build_monitor_tab(self):
        tab = self.tabview.tab("  MONITOR  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(tab, fg_color="transparent")
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
            command=self._clear_monitor,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_SECONDARY,
            height=40,
            width=130,
            font=ctk.CTkFont(*F_BODY),
        ).pack(side="right")

        self.monitor_box = ctk.CTkTextbox(
            tab,
            fg_color=BG_CARD,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont("Consolas", 14),
            border_color=BORDER_COLOR,
            border_width=1,
            state="disabled",
        )
        self.monitor_box.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        tb = self.monitor_box._textbox
        tb.tag_config("error", foreground=ACCENT_RED)
        tb.tag_config("pause", foreground=ACCENT_YELLOW)
        tb.tag_config("ok", foreground=ACCENT_GREEN)
        tb.tag_config("info", foreground=ACCENT_BLUE)
        tb.tag_config("barrera", foreground=ACCENT_PURPLE)
        tb.tag_config("manual", foreground=ACCENT_ORANGE)
        tb.tag_config("normal", foreground=TEXT_PRIMARY)
    
    # ── Modo Manual ───────────────────────────────────────────
    def _cmd_manual_toggle(self):
        if not self.connected:
            messagebox.showerror("Error", "No hay conexión")
            return

        if not self._manual_activo:
            rec = self.esp_rec.get()
            if rec not in ("--", "ninguna", ""):
                messagebox.showwarning(
                    "Modo Manual",
                    "No se puede activar el modo manual\n"
                    "con una receta cargada.\n\n"
                    "Detenga la receta primero."
                )
                return

            if not messagebox.askyesno(
                "Activar Modo Manual",
                "¿Activar modo manual?\n\n"
                "El motor arrancará y parará con el PEDAL.\n"
                "El husillo se sincroniza con el encoder.\n\n"
                "Solo disponible sin receta cargada."
            ):
                return

            resp = self.serial.send("MANUAL_ON")
            self.log(f"MANUAL ON → {resp}", "manual")
            self._manual_activo = True
            self.btn_manual.configure(
                text="⚙  DESACTIVAR MANUAL",
                fg_color=ACCENT_RED,
                hover_color="#CC2222",
                text_color=TEXT_PRIMARY,
            )
            self._show_alert(
                "⚙ MODO MANUAL — Pise el PEDAL para girar",
                ACCENT_ORANGE,
            )
        else:
            resp = self.serial.send("MANUAL_OFF")
            self.log(f"MANUAL OFF → {resp}", "manual")
            self._manual_activo = False
            self.btn_manual.configure(
                text="⚙  ACTIVAR MODO MANUAL",
                fg_color=ACCENT_ORANGE,
                hover_color="#CC6633",
                text_color=BG_DARK,
            )
            self._show_alert(
                "Sistema listo — Cargue una receta",
                TEXT_SECONDARY,
            )

    def _sync_manual_btn(self, es_manual: bool):
        if es_manual and not self._manual_activo:
            self._manual_activo = True
            self.btn_manual.configure(
                text="⚙  DESACTIVAR MANUAL",
                fg_color=ACCENT_RED,
                hover_color="#CC2222",
                text_color=TEXT_PRIMARY,
            )
        elif not es_manual and self._manual_activo:
            self._manual_activo = False
            self.btn_manual.configure(
                text="⚙  ACTIVAR MODO MANUAL",
                fg_color=ACCENT_ORANGE,
                hover_color="#CC6633",
                text_color=BG_DARK,
            )

    # ── JOG ───────────────────────────────────────────────────
    def _set_jog_paso(self, mm: float):
        self.jog_paso_var.set(mm)
        for m, btn in self.jog_paso_btns.items():
            if abs(m - mm) < 0.001:
                btn.configure(
                    fg_color=ACCENT_YELLOW,
                    text_color=BG_DARK,
                )
            else:
                btn.configure(
                    fg_color=BG_CARD,
                    text_color=TEXT_SECONDARY,
                )

        lbl = (f"{mm:.1f}".rstrip("0").rstrip(".") or "0") + "mm"

        if hasattr(self, "jog_paso_actual"):
            self.jog_paso_actual.configure(text=lbl)

        if hasattr(self, "jog_paso_entry"):
            self.jog_paso_entry.delete(0, "end")
            self.jog_paso_entry.insert(0, str(mm))

    def _set_jog_paso_manual(self):
        try:
            mm = float(self.jog_paso_entry.get().strip())
            if mm <= 0 or mm > 200:
                raise ValueError("fuera de rango")

            for btn in self.jog_paso_btns.values():
                btn.configure(
                    fg_color=BG_CARD,
                    text_color=TEXT_SECONDARY,
                )

            self.jog_paso_var.set(mm)
            self.jog_paso_actual.configure(text=f"{mm:.2f}mm")
        except ValueError as e:
            messagebox.showerror(
                "Error",
                f"Valor inválido: {e}\n"
                "Introduce un número entre 0.01 y 200"
            )

    def _mm_a_pasos_jog(self, mm: float) -> int:
        return max(1, int(round(mm * 160.0)))

    def _jog_pulso(self, direction: str):
        if not self.connected:
            messagebox.showerror("Error", "No hay conexión")
            return

        mm = self.jog_paso_var.get()
        pasos = self._mm_a_pasos_jog(mm)
        cmd = f"JOGMM:{direction.upper()}:{pasos}"
        lbl = (f"{mm:.1f}".rstrip("0").rstrip(".") or "0") + "mm"
        sym = "◀" if direction == "left" else "▶"

        self.jog_status.configure(
            text=f"{sym} {lbl}",
            text_color=ACCENT_YELLOW,
        )

        def _t():
            resp = self.serial.send(cmd)
            self.log(
                f"JOG {direction} {lbl} ({pasos}p): {resp}",
                "info",
            )
            if resp and any("ERR" in x for x in resp):
                self.after(
                    0,
                    lambda r=resp: self.jog_status.configure(
                        text=f"✗ {r[0][:20]}",
                        text_color=ACCENT_RED,
                    )
                )
            else:
                self.after(
                    0,
                    lambda: self.jog_status.configure(
                        text="◉ PARADO",
                        text_color=TEXT_SECONDARY,
                    )
                )

        threading.Thread(target=_t, daemon=True).start()

    def _jog_start(self, direction: str):
        if not self.connected:
            messagebox.showerror("Error", "No hay conexión")
            return

        self._jog_active = True
        self._jog_direction = direction

        if direction == "left":
            self.jog_left_btn.configure(
                fg_color=ACCENT_BLUE,
                text_color=BG_DARK,
            )
        else:
            self.jog_right_btn.configure(
                fg_color=ACCENT_BLUE,
                text_color=BG_DARK,
            )

        self.jog_status.configure(
            text=f"{'◀◀' if direction == 'left' else '▶▶'}",
            text_color=ACCENT_BLUE,
        )

        self.serial.send("JOG:LEFT" if direction == "left" else "JOG:RIGHT")
        threading.Thread(target=self._jog_loop, daemon=True).start()

    def _jog_loop(self):
        while self._jog_active:
            cmd = "JOG:LEFT" if self._jog_direction == "left" else "JOG:RIGHT"
            self.serial.send(cmd)
            time.sleep(0.1)

    def _jog_stop(self):
        self._jog_active = False
        for btn in [self.jog_left_btn, self.jog_right_btn]:
            btn.configure(
                fg_color="#1C3A5C",
                text_color=ACCENT_BLUE,
            )

        self.jog_status.configure(
            text="◉ PARADO",
            text_color=TEXT_SECONDARY,
        )
        self.serial.send("JOG:STOP")

    # ── Configuración ─────────────────────────────────────────
    def _leer_cfg_entries(self) -> dict:
        cfg = dict(self.cfg)
        for key, (entry, tipo) in self.cfg_entries.items():
            try:
                v = entry.get().strip()
                if tipo == "float":
                    cfg[key] = float(v)
                elif tipo == "int":
                    cfg[key] = int(v)
                elif tipo == "bool":
                    cfg[key] = v in ("1", "true", "True")
            except ValueError:
                pass
        return cfg

    def _guardar_config_local(self):
        self.cfg = self._leer_cfg_entries()
        self.cfg["puerto"] = self.port_var.get()
        guardar_config(self.cfg)
        self.log("Configuración guardada localmente", "ok")

    def _enviar_config_esp(self):
        self._guardar_config_local()
        if not self.connected:
            messagebox.showerror(
                "Error",
                "No hay conexión con el controlador",
            )
            return

        threading.Thread(
            target=self._send_config_to_esp,
            daemon=True,
        ).start()

    def _send_config_to_esp(self):
        cfg = self.cfg
        esp_x10 = int(round(cfg.get("espesor_mm", 1.0) * 10))
        retf = cfg.get("retardo_freno", 1.5)
        freno = 1 if cfg.get("freno_no", True) else 0
        dirinit = 1 if cfg.get("dir_inicial", True) else 0
        vpre = int(cfg.get("vueltas_prefreno", 5))

        cmd = (
            f"CONFIG:esp={esp_x10},retf={retf},"
            f"frenoNO={freno},dirinit={dirinit},vpre={vpre}"
        )
        resp = self.serial.send(cmd)
        self.log(f"CONFIG enviada: {resp}", "ok")

    # ── Posición ──────────────────────────────────────────────
    def _on_pos_recipe_change(self, name=None):
        name = name or self.pos_recipe_var.get()
        rec = load_recipe(name)
        if not rec:
            return

        n = len(rec.get("secciones", []))
        vals = [str(i + 1) for i in range(n)]
        self.pos_sec_combo.configure(values=vals)

        if vals:
            self.pos_sec_var.set(vals[0])

        self.pos_vuelta_var.set("0.0")
        self._update_pos_info()

    def _update_pos_info(self):
        rec = load_recipe(self.pos_recipe_var.get())
        if not rec:
            return

        try:
            si = int(self.pos_sec_var.get()) - 1
            sec = rec["secciones"][si]
            tipo = sec.get("tipo", "BOB")
            nom = sec.get("nombre", "")
            capas = sec.get("capas", [])

            self.pos_sec_info.configure(text=f"{nom}  [{tipo}]")

            if not capas:
                self.pos_capa_info.configure(text="")
                return

            total_sec = capas[-1]

            try:
                v_actual = float(self.pos_vuelta_var.get())
                if v_actual > total_sec:
                    self.pos_vuelta_var.set(str(total_sec))
                    v_actual = total_sec
                if v_actual < 0:
                    self.pos_vuelta_var.set("0.0")
                    v_actual = 0.0
            except ValueError:
                self.pos_vuelta_var.set("0.0")
                v_actual = 0.0

            capa_idx = 0
            for c in range(len(capas)):
                if v_actual <= capas[c]:
                    capa_idx = c
                    break
                capa_idx = c

            capa_num = capa_idx + 1
            ant = capas[capa_idx - 1] if capa_idx > 0 else 0.0
            meta = capas[capa_idx]
            vueltas_capa = round(meta - ant, 1)
            d = "->" if sec["dirs"][capa_idx] else "<-"

            self.pos_capa_var.set(str(capa_num))
            self.pos_capa_info.configure(
                text=(
                    f"Capa {capa_num} ({vueltas_capa:.0f}v)  {d}\n"
                    f"Rango: 0 – {total_sec:.0f}v acum."
                )
            )

        except (IndexError, ValueError):
            self.pos_capa_info.configure(text="")

    def _inc_pos(self, field, delta):
        if field == "vuelta":
            try:
                rec = load_recipe(self.pos_recipe_var.get())
                if not rec:
                    return

                si = int(self.pos_sec_var.get()) - 1
                sec = rec["secciones"][si]
                capas = sec.get("capas", [])
                total = capas[-1] if capas else 0.0

                v = round(float(self.pos_vuelta_var.get()) + delta, 1)
                v = max(0.0, min(v, total))
                self.pos_vuelta_var.set(str(v))
                self._update_pos_info()
            except (ValueError, IndexError):
                pass

    def _apply_position(self):
        if not self.connected:
            messagebox.showerror("Error", "No hay conexión")
            return

        rec_name = self.pos_recipe_var.get()
        if not rec_name:
            messagebox.showwarning("Aviso", "Selecciona una receta")
            return

        try:
            sec_num = int(self.pos_sec_var.get())
            vuelta_acum = float(self.pos_vuelta_var.get())
        except ValueError:
            messagebox.showerror("Error", "Valores inválidos")
            return

        recipe = load_recipe(rec_name)
        if not recipe:
            messagebox.showerror("Error", f"'{rec_name}' no encontrada")
            return

        secciones = recipe.get("secciones", [])
        if sec_num < 1 or sec_num > len(secciones):
            messagebox.showerror("Error", f"Sección {sec_num} no existe")
            return

        sec = secciones[sec_num - 1]
        sec_tipo = sec.get("tipo", "BOB")
        capas = sec.get("capas", [])

        if not capas:
            messagebox.showerror("Error", f"S{sec_num} sin capas")
            return

        total_sec = capas[-1]

        if vuelta_acum < 0 or vuelta_acum > total_sec:
            messagebox.showerror(
                "Error",
                f"Vuelta {vuelta_acum} fuera de rango.\n"
                f"S{sec_num} acepta: 0 – {total_sec:.1f}v acumuladas."
            )
            return

        capa_idx = 0
        for c in range(len(capas)):
            if vuelta_acum <= capas[c]:
                capa_idx = c
                break
            capa_idx = c

        capa_num = capa_idx + 1
        ant = capas[capa_idx - 1] if capa_idx > 0 else 0.0
        vuelta_en_capa = round(vuelta_acum - ant, 1)

        prox_der = ""
        for der in sec.get("derivaciones", []):
            if der["vuelta"] > vuelta_acum:
                prox_der = (
                    f"\n  Próx. parada : "
                    f"[{der['etiqueta']}] @{der['vuelta']}v"
                )
                break

        pulsos = int(round(vuelta_acum * 200))

        resumen = (
            f"Receta   : {rec_name}\n"
            f"Sección  : {sec_num} — {sec.get('nombre', '')} [{sec_tipo}]\n"
            f"─────────────────────────────\n"
            f"Vuelta acum. : {vuelta_acum:.1f}v (de {total_sec:.1f}v totales)\n"
            f"Capa detect. : {capa_num}/{len(capas)} ({vuelta_en_capa:.1f}v dentro de capa)\n"
            f"Encoder      : {pulsos} pulsos"
            f"{prox_der}\n"
            f"─────────────────────────────\n"
            f"El controlador iniciará en S{sec_num} con encoder={pulsos}."
        )

        if not messagebox.askyesno("Confirmar inicio", resumen):
            return

        def _thread():
            self.log(
                f"=== REANUDANDO S{sec_num} V_acum={vuelta_acum} ===",
                "info",
            )

            self._send_recipe_thread(recipe)
            time.sleep(0.3)

            if pulsos > 0:
                resp = self.serial.send(f"SETENC:{pulsos}")
                self.log(
                    f"SETENC {pulsos} pulsos ({vuelta_acum:.1f}v): {resp}",
                    "info",
                )
                time.sleep(0.15)
            else:
                self.log("Vuelta 0 — encoder en 0", "info")

            sec_idx = sec_num - 1
            run_cmd = f"RUN:{rec_name}:SEC:{sec_idx}"
            resp = self.serial.send(run_cmd)
            self.log(f"RUN S{sec_num}: {resp}", "ok")

            if resp and any("ERR" in x for x in resp):
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error",
                        f"Controlador rechazó RUN:\n{resp}",
                    )
                )
                return

            self.after(
                0,
                lambda: self.pos_summary.configure(
                    text=f"✓ S{sec_num} C{capa_num} @{vuelta_acum}v"
                )
            )
            self.after(
                0,
                lambda: self._show_alert(
                    f"Reanudando S{sec_num} C{capa_num} @{vuelta_acum}v — Pise el PEDAL",
                    ACCENT_GREEN,
                )
            )

        threading.Thread(target=_thread, daemon=True).start()

    # ── Comandos control ──────────────────────────────────────
    def _cmd_start(self):
        if not self.connected:
            messagebox.showerror("Error", "No conectado")
            return
        resp = self.serial.send("STARTMAQ")
        self.log(f"START → {resp}", "ok")

    def _cmd_stop(self):
        if not self.connected:
            messagebox.showerror("Error", "No conectado")
            return
        resp = self.serial.send("STOPMAQ")
        self.log(f"STOP → {resp}", "error")

    def _cmd_reset(self):
        if not self.connected:
            messagebox.showerror("Error", "No conectado")
            return
        if messagebox.askyesno(
            "Confirmar",
            "¿Resetear contador de vueltas?"
        ):
            resp = self.serial.send("RESET")
            self.log(f"RESET → {resp}", "ok")

    def _cmd_homing(self):
        if not self.connected:
            messagebox.showerror("Error", "No conectado")
            return
        if messagebox.askyesno(
            "Confirmar Homing",
            "¿Ejecutar homing?\n"
            "El husillo buscará el punto cero."
        ):
            resp = self.serial.send("HOMING")
            self.log(f"HOMING → {resp}", "info")

    # ── Recetas ───────────────────────────────────────────────
    def _load_recipe_list(self):
        for w in self.recipe_list_frame.winfo_children():
            w.destroy()

        names = list_recipes()
        self.run_combo.configure(values=names)

        if hasattr(self, "pos_recipe_combo"):
            self.pos_recipe_combo.configure(values=names)

        for name in names:
            ctk.CTkButton(
                self.recipe_list_frame,
                text=f"  {name}",
                anchor="w",
                command=lambda n=name: self._select_recipe(n),
                fg_color="transparent",
                hover_color=BG_INPUT,
                text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(*F_BODY),
                height=46,
                corner_radius=4,
            ).pack(fill="x", pady=2)

    def _select_recipe(self, name):
        self.selected_recipe_name = name
        recipe = load_recipe(name)
        if not recipe:
            return

        self.current_recipe = recipe
        detail = self._recipe_summary(recipe)

        self.recipe_detail.configure(state="normal")
        self.recipe_detail.delete("1.0", "end")
        self.recipe_detail.insert("1.0", detail)
        self.recipe_detail.configure(state="disabled")

        self.run_recipe_var.set(name)

    def _recipe_summary(self, recipe):
        lines = [
            f"NOMBRE   : {recipe['nombre']}",
            f"ESPESOR  : {recipe.get('espesorX10', 10) / 10:.1f} mm",
            f"SECCIONES: {len(recipe.get('secciones', []))}",
            "",
        ]

        for i, sec in enumerate(recipe.get("secciones", [])):
            tipo = sec.get("tipo", "BOB")
            nom = sec.get("nombre", "")
            ic = "⚙" if tipo == "BOB" else "📄"
            lines.append(f"{ic} S{i+1}: {nom} [{tipo}]")

            capas = sec.get("capas", [])
            dirs = sec.get("dirs", [True] * len(capas))
            ant = 0

            for c, (meta, d) in enumerate(zip(capas, dirs)):
                v = round(meta - ant, 1)
                ds = "→MAX" if d else "←MIN"
                lines.append(
                    f"  Capa {c+1:2d}: {v:6.1f}v "
                    f"(acum:{meta:7.1f})  {ds}"
                )
                ant = meta

            for der in sec.get("derivaciones", []):
                m = der.get("mensaje", "")
                lines.append(
                    f"    ⚡ [{der['etiqueta']}] @{der['vuelta']}v"
                    + (f" → {m}" if m else "")
                )

            lines.append("")

        return "\n".join(lines)

    def _delete_selected_recipe(self):
        name = self.selected_recipe_name
        if not name:
            messagebox.showwarning(
                "Aviso",
                "Selecciona una receta primero",
            )
            return

        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar '{name}' del sistema local?"
        ):
            return

        delete_recipe(name)
        self.selected_recipe_name = None
        self.current_recipe = None

        self.recipe_detail.configure(state="normal")
        self.recipe_detail.delete("1.0", "end")
        self.recipe_detail.configure(state="disabled")

        self._load_recipe_list()
        self.log(f"Receta '{name}' eliminada", "ok")

    def _send_selected_to_esp(self):
        if not self.current_recipe:
            messagebox.showwarning(
                "Aviso",
                "Selecciona una receta primero",
            )
            return

        if not self.connected:
            messagebox.showerror(
                "Error",
                "No hay conexión con el controlador",
            )
            return

        threading.Thread(
            target=self._send_recipe_thread,
            args=(self.current_recipe,),
            daemon=True,
        ).start()

    def _send_recipe_thread(self, recipe):
        nombre = recipe["nombre"]
        self.log(f"── Enviando '{nombre}' ──", "info")

        self.serial.send("STATUSPAUSE")
        time.sleep(0.1)

        r = self.serial.send(f"NEW:{nombre}")
        self.log(f"  NEW: {r}")

        r = self.serial.send(f"ESP:{recipe.get('espesorX10', 10)}")
        self.log(f"  ESP: {r}")

        for i, sec in enumerate(recipe.get("secciones", [])):
            tipo = sec.get("tipo", "BOB")
            r = self.serial.send(f"S{i+1}:TIPO:{tipo}")
            self.log(f"  S{i+1} TIPO: {r}")

            nom = sec.get("nombre", "")
            if nom:
                r = self.serial.send(f"S{i+1}:NOMBRE:{nom}")
                self.log(f"  S{i+1} NOMBRE: {r}")

            capas_str = ",".join(str(c) for c in sec["capas"])
            r = self.serial.send(f"S{i+1}:C:{capas_str}")
            self.log(f"  S{i+1} CAPAS: {r}")

            if "dirs" in sec:
                dirs_str = "".join(">" if d else "<" for d in sec["dirs"])
                r = self.serial.send(f"S{i+1}:DIR:{dirs_str}")
                self.log(f"  S{i+1} DIR: {r}")

            if sec.get("derivaciones"):
                der_str = ",".join(
                    f"{d['vuelta']}:{d['etiqueta']}:{d.get('mensaje', '')}"
                    for d in sec["derivaciones"]
                )
                r = self.serial.send(f"S{i+1}:D:{der_str}")
                self.log(f"  S{i+1} DER: {r}")

        r = self.serial.send("END")
        self.log(f"  END: {r}")
        self.serial.send("STATUSRESUME")

        if r and any("ERR" in x for x in r):
            self.log(
                f"✗ El controlador rechazó la receta: {r}",
                "error",
            )
        else:
            self.log(
                f"✓ '{nombre}' cargada en controlador",
                "ok",
            )

    def _run_selected_recipe(self):
        name = self.run_recipe_var.get()
        if not name:
            messagebox.showwarning("Aviso", "Selecciona una receta")
            return

        if not self.connected:
            messagebox.showerror("Error", "No hay conexión")
            return

        recipe = load_recipe(name)
        if not recipe:
            messagebox.showerror("Error", f"'{name}' no encontrada")
            return

        if not messagebox.askyesno(
            "Confirmar ejecución",
            f"¿Cargar y ejecutar '{name}'?\n\n"
            f"Secciones : {len(recipe.get('secciones', []))}\n"
            f"Espesor   : {recipe.get('espesorX10', 10) / 10:.1f}mm\n\n"
            f"El motor arrancará al pisar el PEDAL."
        ):
            return

        def _thread():
            self.log(f"=== CARGANDO '{name}' ===", "info")
            self._send_recipe_thread(recipe)
            time.sleep(0.3)

            resp = self.serial.send(f"RUN:{name}")
            self.log(f"RUN '{name}': {resp}", "ok")

            if resp and any("ERR" in x for x in resp):
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error",
                        f"Controlador rechazó RUN:\n{resp}",
                    )
                )
                return

            self.after(
                0,
                lambda: self._show_alert(
                    f"'{name}' cargada — Pise el PEDAL para arrancar",
                    ACCENT_GREEN,
                )
            )

        threading.Thread(target=_thread, daemon=True).start()

    def _edit_selected_recipe(self):
        if not self.selected_recipe_name:
            messagebox.showwarning(
                "Aviso",
                "Selecciona una receta primero",
            )
            return

        recipe = load_recipe(self.selected_recipe_name)
        self._open_recipe_form(recipe)

    def _open_recipe_form(self, recipe=None):
        RecipeForm(self, recipe, self._on_recipe_saved)

    def _on_recipe_saved(self, recipe):
        ok, motivo = validate_recipe(recipe)
        if not ok:
            messagebox.showerror("Error de validación", motivo)
            return

        resultado = save_recipe(recipe)
        if not resultado:
            messagebox.showerror(
                "Error al guardar",
                "No se pudo guardar la receta.\n\n"
                "Verifica que existe la carpeta de recetas en data/recetas.",
            )
            return

        self._load_recipe_list()
        self.log(f"✓ Receta '{recipe['nombre']}' guardada", "ok")

        if self.connected and messagebox.askyesno(
            "Enviar al controlador",
            "¿Enviar la receta al controlador ahora?"
        ):
            threading.Thread(
                target=self._send_recipe_thread,
                args=(recipe,),
                daemon=True,
            ).start()

    # ── Monitor ───────────────────────────────────────────────
    def log(self, msg, tag="normal"):
        ts = datetime.now().strftime("%H:%M:%S")
        txt = f"[{ts}] {msg}\n"

        def _ins():
            self.monitor_box.configure(state="normal")
            self.monitor_box._textbox.insert("end", txt, tag)
            self.monitor_box._textbox.see("end")
            self.monitor_box.configure(state="disabled")

        self.after(0, _ins)

    def _clear_monitor(self):
        self.monitor_box.configure(state="normal")
        self.monitor_box.delete("1.0", "end")
        self.monitor_box.configure(state="disabled")

    # ── Callbacks serial ──────────────────────────────────────
    def on_serial_message(self, msg):
        if msg.startswith("STATUS:"):
            self._parse_status(msg)
            return

        tag = "normal"
        if "PAUSA:CAPA" in msg:
            tag = "pause"
        elif "PAUSA:DER" in msg:
            tag = "pause"
        elif "PAUSA:BARRERA" in msg:
            tag = "barrera"
        elif "TERMINADA" in msg:
            tag = "ok"
        elif "ERR" in msg:
            tag = "error"
        elif "OK" in msg:
            tag = "ok"
        elif "SECCION" in msg:
            tag = "info"
        elif "MANUAL" in msg:
            tag = "manual"

        self.log(msg, tag)

        if ("PAUSA:DER" in msg or "PAUSA:BARRERA" in msg):
            parts = msg.split(":")
            alert = ""

            for i, p in enumerate(parts):
                if p == "MSG" and i + 1 < len(parts):
                    alert = parts[i + 1]
                    break

            if not alert:
                for i, p in enumerate(parts):
                    if p in ("DER", "BARRERA") and i + 1 < len(parts):
                        alert = f"⚡ {parts[i + 1]}"
                        break

            self.after(
                0,
                lambda a=alert: self._show_alert(a, ACCENT_YELLOW),
            )

        elif ("PAUSA:CAPA" in msg or "PAUSA:CAPA_BARRERA" in msg):
            parts = msg.split(":")
            cn = parts[2] if len(parts) > 2 else "?"
            self.after(
                0,
                lambda c=cn: self._show_alert(
                    f"FIN CAPA {c} — Presione ▶ START",
                    ACCENT_YELLOW,
                )
            )

        elif "SECCION_FIN" in msg:
            parts = msg.split(":")
            nxt = ""
            for i, p in enumerate(parts):
                if p == "NEXT_NOMBRE" and i + 1 < len(parts):
                    nxt = parts[i + 1]
                    break

            self.after(
                0,
                lambda n=nxt: self._show_alert(
                    f"FIN SECCIÓN → Siguiente: {n} — Presione ▶ START",
                    ACCENT_BLUE,
                )
            )

        elif "BOBINA_TERMINADA" in msg:
            self.after(
                0,
                lambda: self._show_alert(
                    "✓ BOBINA COMPLETA — Presione ▶ START",
                    ACCENT_GREEN,
                )
            )

    def _show_alert(self, text, color=ACCENT_YELLOW):
        self.alert_label.configure(
            text=text,
            text_color=color,
        )

    def _parse_status(self, msg):
        d = parse_status_msg(msg)
        if not d:
            return

        estado_num = d.get("_estado", "0")
        estado_str = ESTADOS.get(estado_num, f"EST_{estado_num}")
        self.after(0, lambda s=estado_str: self.esp_estado.set(s))

        def upd(var, key, fmt=None):
            val = d.get(key, "")
            if val:
                v = fmt(val) if fmt else val
                self.after(0, lambda x=v, vr=var: vr.set(x))

        upd(self.esp_rec, "REC")
        upd(self.esp_sec, "SEC")
        upd(self.esp_tsec, "TSEC")
        upd(self.esp_tcap, "TCAP")
        upd(self.esp_meta, "META")
        upd(self.esp_vueltas, "VT")
        upd(self.esp_rpm, "RPM")
        upd(self.esp_pos, "POS", lambda v: f"{v}cm")

        pos_val = d.get("POS", "")
        if pos_val and hasattr(self, "jog_pos_label"):
            self.after(
                0,
                lambda v=pos_val: self.jog_pos_label.configure(text=f"Pos: {v}cm"),
            )

        capa = d.get("CAPA", "--")
        dcapa = d.get("DCAPA", "0")
        cdisp = dcapa if dcapa not in ("0", "") else capa
        self.after(0, lambda v=cdisp: self.esp_capa.set(v))

        freno = d.get("FRENO", "0")
        var = d.get("VAR", "0")
        f_txt = "🔒 FRENO" if freno == "1" else "🔓 libre"
        v_txt = "⚡ MOTOR" if var == "1" else "⏹ parado"

        self.after(0, lambda f=f_txt: self.esp_freno.set(f))
        self.after(0, lambda v=v_txt: self.esp_variador.set(v))

        es_manual = (estado_num == "13")
        self.after(0, lambda m=es_manual: self._sync_manual_btn(m))

        alertas = {
            "0":  ("Sistema listo — Cargue una receta", TEXT_SECONDARY),
            "1":  ("● BOBINANDO — Pise pedal para parar", ACCENT_GREEN),
            "2":  ("◐ PREFRENO — Reduciendo velocidad...", ACCENT_YELLOW),
            "3":  ("⏸ FIN DE CAPA — Presione ▶ START", ACCENT_YELLOW),
            "4":  ("▶ DESBLOQUEADO — Pise el PEDAL", ACCENT_BLUE),
            "5":  ("⚡ PAUSA DER — Presione ▶ START", ACCENT_RED),
            "6":  ("▶ DER DESBLOQUEADA — Pise el PEDAL", ACCENT_BLUE),
            "7":  ("⏭ FIN SECCIÓN — Presione ▶ START", ACCENT_BLUE),
            "8":  ("✓ BOBINA COMPLETA — Presione ▶ START", ACCENT_GREEN),
            "9":  ("🔧 JOG — Mueva el husillo", ACCENT_BLUE),
            "10": ("📄 BARRERA — Pise el pedal para girar", ACCENT_PURPLE),
            "11": ("📄 PAUSA BARRERA — Presione ▶ START", ACCENT_PURPLE),
            "12": ("⌂ HOMING en progreso...", ACCENT_ORANGE),
            "13": ("⚙ MODO MANUAL — Pise PEDAL para girar", ACCENT_ORANGE),
        }

        if estado_num in alertas:
            txt, color = alertas[estado_num]
            self.after(0, lambda t=txt, c=color: self._show_alert(t, c))

        rec_name = d.get("REC", "")
        if rec_name and rec_name != "ninguna":
            self.after(0, lambda n=rec_name: self.run_recipe_var.set(n))

    def on_connection_change(self, connected, info):
        self.connected = connected

        def _upd():
            if connected:
                self.conn_indicator.configure(
                    text=f"● {info}",
                    text_color=ACCENT_GREEN,
                )
                self.btn_connect.configure(
                    text="DESCONECTAR",
                    fg_color=ACCENT_RED,
                    hover_color="#CC2222",
                    text_color=TEXT_PRIMARY,
                )
                self.log(f"Conectado a {info}", "ok")

                threading.Thread(
                    target=lambda: (
                        time.sleep(1.5),
                        self._send_config_to_esp(),
                    ),
                    daemon=True,
                ).start()
            else:
                self.conn_indicator.configure(
                    text="● DESCONECTADO",
                    text_color=ACCENT_RED,
                )
                self.btn_connect.configure(
                    text="CONECTAR",
                    fg_color=ACCENT_GREEN,
                    hover_color="#00CC6A",
                    text_color=BG_DARK,
                )
                self.log(f"Desconectado: {info}", "error")
                self._show_alert(
                    "Desconectado — Reconecte el controlador",
                    ACCENT_RED,
                )

                self._manual_activo = False
                self.btn_manual.configure(
                    text="⚙  ACTIVAR MODO MANUAL",
                    fg_color=ACCENT_ORANGE,
                    hover_color="#CC6633",
                    text_color=BG_DARK,
                )

        self.after(0, _upd)

    def _toggle_connect(self):
        if self.connected:
            self.serial.disconnect()
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showwarning("Aviso", "Selecciona un puerto")
                return

            self.cfg["puerto"] = port
            guardar_config(self.cfg)

            threading.Thread(
                target=self.serial.connect,
                args=(port,),
                daemon=True,
            ).start()

    def _refresh_ports(self):
        ports = self.serial.get_ports() if hasattr(self, "serial") else []
        self.port_combo.configure(values=ports)

        saved = self.cfg.get("puerto", "")
        if saved and saved in ports:
            self.port_var.set(saved)
        elif ports:
            self.port_var.set(ports[0])

    def _update_clock(self):
        self.clock_label.configure(
            text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        )
        self.after(1000, self._update_clock)
    # ══════════════════════════════════════════════════════════════
class RecipeForm(ctk.CTkToplevel):
    def __init__(self, parent, recipe=None, on_save=None):
        super().__init__(parent)
        self.title("Editor de Receta — Bobinadora HMI v5.3")
        self.geometry("1060x820")
        self.configure(fg_color=BG_DARK)
        self.grab_set()
        self.resizable(True, True)
        self.lift()
        self.focus_force()

        self.on_save = on_save
        self.editing = recipe is not None
        self.sec_layers = [[] for _ in range(8)]
        self.sec_der = [[] for _ in range(8)]
        self.sec_frames = [None] * 8
        self.sec_tipo = [tk.StringVar(value="BOB") for _ in range(8)]
        self.sec_nombre = [tk.StringVar() for _ in range(8)]
        self.num_secs = 0

        self._build(recipe)

    def _build(self, recipe):
        hdr = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=0,
            height=60,
        )
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="CREAR RECETA" if not self.editing else "EDITAR RECETA",
            font=ctk.CTkFont(*F_TITLE),
            text_color=ACCENT_GREEN,
        ).pack(side="left", padx=20, pady=10)

        footer = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=0,
            height=70,
        )
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer,
            text="✓  GUARDAR RECETA",
            command=self._save,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_DARK,
            height=50,
            width=380,
            font=ctk.CTkFont("Consolas", 16, "bold"),
        ).pack(side="left", padx=(20, 8), pady=10)

        ctk.CTkButton(
            footer,
            text="✗  CANCELAR",
            command=self.destroy,
            fg_color=ACCENT_RED,
            hover_color="#CC2222",
            text_color=TEXT_PRIMARY,
            height=50,
            width=220,
            font=ctk.CTkFont("Consolas", 16, "bold"),
        ).pack(side="left", pady=10)

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_DARK,
            corner_radius=0,
        )
        self.scroll.pack(fill="both", expand=True, side="top")

        self._build_basic(recipe)
        self._build_add_section_btn()

        if recipe:
            for sec in recipe.get("secciones", []):
                self._add_section(recipe=sec)
        else:
            self._add_section()

    def _build_basic(self, recipe):
        f = ctk.CTkFrame(self.scroll, fg_color=BG_CARD, corner_radius=8)
        f.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            f,
            text="DATOS BÁSICOS",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(
            row,
            text="Nombre:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        self.name_entry = ctk.CTkEntry(
            row,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(*F_BODY),
            width=300,
            placeholder_text="ej: TRAFO_100KVA_AT",
        )
        self.name_entry.pack(side="left", padx=(0, 30))

        ctk.CTkLabel(
            row,
            text="Espesor alambre (mm):",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        self.esp_entry = ctk.CTkEntry(
            row,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(*F_BODY),
            width=120,
            placeholder_text="ej: 1.5",
        )
        self.esp_entry.pack(side="left")

        if recipe:
            self.name_entry.insert(0, recipe.get("nombre", ""))
            self.esp_entry.insert(0, str(recipe.get("espesorX10", 10) / 10))

    def _build_add_section_btn(self):
        self.add_sec_btn = ctk.CTkButton(
            self.scroll,
            text="＋  AGREGAR NUEVA SECCIÓN",
            command=self._add_section,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=ACCENT_BLUE,
            border_width=2,
            text_color=ACCENT_BLUE,
            height=48,
            font=ctk.CTkFont(*F_BODY_B),
        )
        self.add_sec_btn.pack(fill="x", padx=16, pady=6)

    def _add_section(self, recipe=None):
        if self.num_secs >= 8:
            messagebox.showwarning("Aviso", "Máximo 8 secciones")
            return

        sec_idx = self.num_secs
        self.num_secs += 1
        self.add_sec_btn.pack_forget()

        colors = [
            ACCENT_BLUE,
            ACCENT_GREEN,
            ACCENT_ORANGE,
            ACCENT_PURPLE,
            ACCENT_YELLOW,
            ACCENT_RED,
            "#00CCFF",
            "#FF88CC",
        ]
        color = colors[sec_idx % len(colors)]

        frame = ctk.CTkFrame(self.scroll, fg_color=BG_CARD, corner_radius=10)
        frame.pack(fill="x", padx=16, pady=6)
        self.sec_frames[sec_idx] = frame

        hdr = ctk.CTkFrame(frame, fg_color=BG_INPUT, corner_radius=8)
        hdr.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            hdr,
            text=f"  SECCIÓN {sec_idx + 1}",
            font=ctk.CTkFont(*F_HEAD),
            text_color=color,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            hdr,
            text="＋ AGREGAR CAPA",
            command=lambda s=sec_idx: self._add_layer(s),
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_DARK,
            height=38,
            width=180,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="right", padx=10, pady=10)

        tipo_row = ctk.CTkFrame(frame, fg_color="transparent")
        tipo_row.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            tipo_row,
            text="Tipo:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(4, 10))

        tipo_var = self.sec_tipo[sec_idx]
        if recipe:
            tipo_var.set(recipe.get("tipo", "BOB"))

        bob_btn = ctk.CTkButton(
            tipo_row,
            text="⚙  BOBINADO",
            width=160,
            height=40,
            font=ctk.CTkFont(*F_BODY_B),
            fg_color=ACCENT_BLUE,
            hover_color="#4080CC",
            text_color=TEXT_PRIMARY,
        )
        bob_btn.pack(side="left", padx=4)

        bar_btn = ctk.CTkButton(
            tipo_row,
            text="📄  BARRERA",
            width=160,
            height=40,
            font=ctk.CTkFont(*F_BODY_B),
            fg_color=BG_INPUT,
            hover_color="#8060CC",
            text_color=TEXT_SECONDARY,
        )
        bar_btn.pack(side="left", padx=4)

        def _set_bob():
            tipo_var.set("BOB")
            bob_btn.configure(
                fg_color=ACCENT_BLUE,
                text_color=TEXT_PRIMARY,
            )
            bar_btn.configure(
                fg_color=BG_INPUT,
                text_color=TEXT_SECONDARY,
            )

        def _set_bar():
            tipo_var.set("BAR")
            bob_btn.configure(
                fg_color=BG_INPUT,
                text_color=TEXT_SECONDARY,
            )
            bar_btn.configure(
                fg_color=ACCENT_PURPLE,
                text_color=TEXT_PRIMARY,
            )

        bob_btn.configure(command=_set_bob)
        bar_btn.configure(command=_set_bar)

        if tipo_var.get() == "BAR":
            _set_bar()

        ctk.CTkLabel(
            tipo_row,
            text="  Nombre:",
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(20, 6))

        nom_e = ctk.CTkEntry(
            tipo_row,
            textvariable=self.sec_nombre[sec_idx],
            placeholder_text="ej: Alta Tension",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
            width=240,
        )
        nom_e.pack(side="left", padx=6)

        if recipe and recipe.get("nombre"):
            self.sec_nombre[sec_idx].set(recipe["nombre"])

        col_hdr = ctk.CTkFrame(frame, fg_color=BG_INPUT, corner_radius=6)
        col_hdr.pack(fill="x", padx=12, pady=(8, 2))

        for txt, w in [
            ("N°", 60),
            ("VUELTAS ACUMULADAS", 200),
            ("DIRECCIÓN", 190),
            ("✕", 60),
        ]:
            ctk.CTkLabel(
                col_hdr,
                text=txt,
                width=w,
                font=ctk.CTkFont(*F_SMALL, "bold"),
                text_color=TEXT_SECONDARY,
            ).pack(side="left", padx=8, pady=7)

        rows_frame = ctk.CTkFrame(frame, fg_color="transparent")
        rows_frame.pack(fill="x", padx=12, pady=(0, 4))
        frame._rows_frame = rows_frame

        if recipe:
            capas = recipe.get("capas", [])
            dirs = recipe.get("dirs", [True] * len(capas))
            for meta, d in zip(capas, dirs):
                self._add_layer(sec_idx, meta, d)
        else:
            self._add_layer(sec_idx)

        self._build_derivaciones(frame, sec_idx, recipe)
        self._build_add_section_btn()

    def _add_layer(self, sec_idx, meta=None, direction=None):
        rows_frame = self.sec_frames[sec_idx]._rows_frame
        num = len(self.sec_layers[sec_idx]) + 1

        if direction is None:
            direction = (num % 2 == 1)

        row = LayerRow(
            rows_frame,
            num,
            meta,
            direction,
            on_delete=lambda r, s=sec_idx: self._del_layer(s, r),
        )
        row.pack(fill="x", pady=2)
        self.sec_layers[sec_idx].append(row)

    def _del_layer(self, sec_idx, row):
        self.sec_layers[sec_idx].remove(row)
        row.destroy()
        for i, r in enumerate(self.sec_layers[sec_idx]):
            r.update_num(i + 1)

    def _build_derivaciones(self, parent, sec_idx, recipe=None):
        f = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=8)
        f.pack(fill="x", padx=12, pady=(4, 14))

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            hdr,
            text="⚡  DERIVACIONES — paradas con mensaje",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=ACCENT_YELLOW,
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="＋ AGREGAR",
            command=lambda s=sec_idx: self._add_derivacion(s),
            fg_color=ACCENT_YELLOW,
            hover_color="#CC9200",
            text_color=BG_DARK,
            height=36,
            width=160,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="right")

        der_frame = ctk.CTkFrame(f, fg_color="transparent")
        der_frame.pack(fill="x", padx=10, pady=(0, 10))
        f._der_frame = der_frame
        self.sec_frames[sec_idx]._der_section = f

        if recipe:
            for d in recipe.get("derivaciones", []):
                self._add_derivacion(
                    sec_idx,
                    d.get("vuelta"),
                    d.get("etiqueta"),
                    d.get("mensaje", ""),
                )

    def _add_derivacion(self, sec_idx, vuelta=None, etiqueta=None, mensaje=None):
        der_frame = self.sec_frames[sec_idx]._der_section._der_frame
        row = DerivacionRow(
            der_frame,
            vuelta,
            etiqueta,
            mensaje,
            on_delete=lambda r, s=sec_idx: self._del_der(s, r),
        )
        row.pack(fill="x", pady=3)
        self.sec_der[sec_idx].append(row)

    def _del_der(self, sec_idx, row):
        self.sec_der[sec_idx].remove(row)
        row.destroy()

    def _save(self):
        nombre = self.name_entry.get().strip().replace(" ", "_")
        if not nombre:
            messagebox.showerror("Error", "El nombre no puede estar vacío")
            return

        try:
            esp_mm = float(self.esp_entry.get())
            esp_x10 = int(round(esp_mm * 10))
        except ValueError:
            messagebox.showerror("Error", "Espesor inválido")
            return

        secciones = []
        for sec_idx in range(self.num_secs):
            layers = self.sec_layers[sec_idx]
            if not layers:
                continue

            capas, dirs = [], []
            for row in layers:
                try:
                    meta = float(row.get_meta())
                    if meta <= 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror(
                        "Error",
                        f"S{sec_idx+1} Capa {row.num}: valor inválido",
                    )
                    return

                capas.append(meta)
                dirs.append(row.get_direction())

            for c in range(1, len(capas)):
                if capas[c] <= capas[c - 1]:
                    messagebox.showerror(
                        "Error",
                        f"S{sec_idx+1}: Capa {c+1} ({capas[c]}) debe ser mayor "
                        f"que Capa {c} ({capas[c-1]})",
                    )
                    return

            ders = []
            total = capas[-1]
            for row in self.sec_der[sec_idx]:
                try:
                    v = float(row.get_vuelta())
                    e = row.get_etiqueta()
                    m = row.get_mensaje()

                    if not e:
                        raise ValueError("etiqueta vacía")
                    if v <= 0 or v > total:
                        raise ValueError(f"vuelta {v} fuera de rango 0–{total}")

                    ders.append({
                        "vuelta": v,
                        "etiqueta": e,
                        "mensaje": m,
                    })
                except ValueError as err:
                    messagebox.showerror(
                        "Error",
                        f"S{sec_idx+1}: Derivación inválida — {err}",
                    )
                    return

            ders.sort(key=lambda d: d["vuelta"])

            secciones.append({
                "tipo": self.sec_tipo[sec_idx].get(),
                "nombre": self.sec_nombre[sec_idx].get(),
                "capas": capas,
                "dirs": dirs,
                "derivaciones": ders,
            })

        if not secciones:
            messagebox.showerror("Error", "Agrega al menos una sección")
            return

        recipe = {
            "nombre": nombre,
            "espesorX10": esp_x10,
            "secciones": secciones,
        }

        if self.on_save:
            self.on_save(recipe)

        self.destroy()


# ══════════════════════════════════════════════════════════════
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
            text_color=BG_DARK if self._direction else TEXT_PRIMARY,
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
            text_color=BG_DARK if self._direction else TEXT_PRIMARY,
        )

    def update_num(self, n):
        self.num = n
        self.num_label.configure(text=f"{n:2d}")

    def get_meta(self):
        return self.meta_entry.get().strip()

    def get_direction(self):
        return self._direction


# ══════════════════════════════════════════════════════════════
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