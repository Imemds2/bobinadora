import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import time
from datetime import datetime
from app.ui.panels.sidebar_panel import SidebarPanel
from app.ui.panels.monitor_tab import MonitorTab
from app.ui.panels.control_tab import ControlTab
from app.ui.panels.position_tab import PositionTab
from app.ui.panels.config_tab import ConfigTab
from app.ui.panels.recipes_tab import RecipesTab
from app.controllers.machine.machine_factory import create_machine_controller
from app.state.app_state import AppState
from app.controllers.control_controller import ControlController, ControlUiHooks

from app.serial_manager import SerialManager
from app.recipe_manager import (
    validate_recipe,
    save_recipe,
    load_recipe,
    list_recipes,
    delete_recipe,
)
from app.protocol import parse_status_msg

from app.core.theme import (
    BG_DARK,
    BG_PANEL,
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
    F_BIG,
    F_SMALL,
    setup_theme,
)
from app.core.constants import ESTADOS
from app.core.config_store import cargar_config, guardar_config

from app.ui.dialogs.recipe_form import RecipeForm
from app.ui.panels.header_panel import HeaderPanel

class App(ctk.CTk):
    def __init__(self):
        setup_theme()
        super().__init__()
        self.title("BOBINADORA HMI  v5.3")
        self.geometry("1920x1080")
        self.minsize(1200, 750)
        self.configure(fg_color=BG_DARK)

        self.cfg = cargar_config()

        backend = str(self.cfg.get("machine_backend", "simulated")).strip().lower()
        self.use_simulator = backend == "simulated"
        self.machine = create_machine_controller(self.cfg)
        self.app_state = AppState()
        self.control_controller = None

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
        self._init_control_controller()
        self.after(100, self._machine_poll)

    def _machine_poll(self):
        try:
            if self.use_simulator:
                self.machine.update()
                snapshot = self.machine.get_snapshot()
                self._apply_machine_snapshot(snapshot)
        finally:
            self.after(100, self._machine_poll)
    
    def _apply_machine_snapshot(self, snapshot):
        self.connected = snapshot.connected
        self.app_state.connected = snapshot.connected

        self.esp_estado.set(snapshot.state)
        self.esp_rec.set(snapshot.recipe_name or "--")
        self.esp_sec.set("--")
        self.esp_tsec.set("--")
        self.esp_capa.set(str(snapshot.current_layer) if snapshot.current_layer else "--")
        self.esp_tcap.set("--")
        self.esp_meta.set(f"{snapshot.target_turns:.1f}" if snapshot.target_turns else "--")
        self.esp_vueltas.set(f"{snapshot.current_turns:.1f}")
        self.esp_rpm.set(f"{snapshot.rpm:.0f}")
        self.esp_pos.set(f"{snapshot.position_mm / 10.0:.2f}cm")

        self.esp_freno.set("--")
        self.esp_variador.set("⚡ MOTOR" if snapshot.is_running() else "⏹ parado")

        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_jog_position(f"Pos: {snapshot.position_mm / 10.0:.2f}cm")

        self._sync_manual_btn(snapshot.manual_mode)

        if snapshot.connected:
            self.conn_indicator.configure(
                text="● SIMULADOR",
                text_color=ACCENT_GREEN,
            )
            self.btn_connect.configure(
                text="DESCONECTAR",
                fg_color=ACCENT_RED,
                hover_color="#CC2222",
                text_color=TEXT_PRIMARY,
            )
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

        if snapshot.has_error():
            self._show_alert(
                snapshot.alarm_message or "Error de simulación",
                ACCENT_RED,
            )
        elif snapshot.state == "HOMING":
            self._show_alert(
                "⌂ HOMING en progreso...",
                ACCENT_ORANGE,
            )
        elif snapshot.state == "PAUSED":
            self._show_alert(
                "⏸ PAUSADO",
                ACCENT_YELLOW,
            )
        elif snapshot.state == "RUNNING":
            self._show_alert(
                "● SIMULANDO BOBINADO",
                ACCENT_GREEN,
            )
        elif snapshot.manual_mode:
            self._show_alert(
                "⚙ MODO MANUAL",
                ACCENT_ORANGE,
            )
        elif snapshot.connected:
            self._show_alert(
                "Sistema listo — Simulador activo",
                TEXT_SECONDARY,
            )
        else:
            self._show_alert(
                "Desconectado — Simulador inactivo",
                ACCENT_RED,
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
        self.header_panel = HeaderPanel(self)
        self.header_panel.build()

        self.conn_indicator = self.header_panel.conn_indicator
        self.clock_label = self.header_panel.clock_label

        self._update_clock()

    def _build_sidebar(self, parent):
        self.sidebar_panel = SidebarPanel(
            parent,
            cfg=self.cfg,
            on_refresh_ports=self._refresh_ports,
            on_toggle_connect=self._toggle_connect,
        )
        self.sidebar_panel.build()

        # Referencias puente para mantener compatibilidad
        self.port_var = self.sidebar_panel.port_var
        self.port_combo = self.sidebar_panel.port_combo
        self.btn_connect = self.sidebar_panel.btn_connect

        self.esp_estado = self.sidebar_panel.esp_estado
        self.esp_rec = self.sidebar_panel.esp_rec
        self.esp_sec = self.sidebar_panel.esp_sec
        self.esp_tsec = self.sidebar_panel.esp_tsec
        self.esp_capa = self.sidebar_panel.esp_capa
        self.esp_tcap = self.sidebar_panel.esp_tcap
        self.esp_meta = self.sidebar_panel.esp_meta
        self.esp_vueltas = self.sidebar_panel.esp_vueltas
        self.esp_rpm = self.sidebar_panel.esp_rpm
        self.esp_pos = self.sidebar_panel.esp_pos
        self.esp_freno = self.sidebar_panel.esp_freno
        self.esp_variador = self.sidebar_panel.esp_variador

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
        self.control_tab = ControlTab(
            self.tabview,
            metrics={
                "esp_vueltas": self.esp_vueltas,
                "esp_meta": self.esp_meta,
                "esp_capa": self.esp_capa,
                "esp_rpm": self.esp_rpm,
                "esp_sec": self.esp_sec,
                "esp_tsec": self.esp_tsec,
            },
            on_start=self._ctrl_cmd_start,
            on_stop=self._ctrl_cmd_stop,
            on_reset=self._ctrl_cmd_reset,
            on_homing=self._ctrl_cmd_homing,
            on_run_recipe=self._run_selected_recipe,
            on_manual_toggle=self._ctrl_cmd_manual_toggle,
            on_set_jog_step=self._set_jog_paso,
            on_set_jog_step_manual=self._set_jog_paso_manual,
            on_jog_left_single=lambda: self._ctrl_jog_pulse("left"),
            on_jog_right_single=lambda: self._ctrl_jog_pulse("right"),
            on_jog_left_press=self._ctrl_on_jog_left_press_ui,
            on_jog_left_release=self._ctrl_on_jog_left_release_ui,
            on_jog_right_press=self._ctrl_on_jog_right_press_ui,
            on_jog_right_release=self._ctrl_on_jog_right_release_ui,
        )
        self.control_tab.build()

        # Referencias puente para mantener compatibilidad temporal
        self.alert_label = self.control_tab.alert_label
        self.btn_manual = self.control_tab.btn_manual
        self.run_recipe_var = self.control_tab.run_recipe_var
        self.run_combo = self.control_tab.run_combo

        self.jog_left_single = self.control_tab.jog_left_single
        self.jog_left_btn = self.control_tab.jog_left_btn
        self.jog_right_btn = self.control_tab.jog_right_btn
        self.jog_right_single = self.control_tab.jog_right_single
        self.jog_status = self.control_tab.jog_status
        self.jog_paso_actual = self.control_tab.jog_paso_actual
        self.jog_pos_label = self.control_tab.jog_pos_label
        self.jog_paso_entry = self.control_tab.jog_paso_entry
        self.jog_paso_btns = self.control_tab.jog_paso_btns
        self.jog_paso_var = self.control_tab.jog_paso_var

    def _ctrl_cmd_start(self):
        self.control_controller.cmd_start()

    def _ctrl_cmd_stop(self):
        self.control_controller.cmd_stop()

    def _ctrl_cmd_reset(self):
        self.control_controller.cmd_reset()

    def _ctrl_cmd_homing(self):
        self.control_controller.cmd_homing()

    def _ctrl_cmd_manual_toggle(self):
        self.control_controller.cmd_manual_toggle()

    def _ctrl_jog_pulse(self, direction: str):
        self.control_controller.jog_pulse(direction)

    def _ctrl_on_jog_left_press_ui(self):
        self.control_controller.on_jog_left_press_ui()

    def _ctrl_on_jog_left_release_ui(self):
        self.control_controller.on_jog_left_release_ui()

    def _ctrl_on_jog_right_press_ui(self):
        self.control_controller.on_jog_right_press_ui()

    def _ctrl_on_jog_right_release_ui(self):
        self.control_controller.on_jog_right_release_ui()

    # ── TAB RECETAS ───────────────────────────────────────────
    def _build_recipes_tab(self):
        self.recipes_tab = RecipesTab(
            self.tabview,
            on_new_recipe=self._open_recipe_form,
            on_delete_recipe=self._delete_selected_recipe,
            on_send_to_controller=self._send_selected_to_esp,
            on_edit_recipe=self._edit_selected_recipe,
        )
        self.recipes_tab.build()

        # Referencias puente para mantener compatibilidad temporal
        self.recipe_list_frame = self.recipes_tab.recipe_list_frame
        self.recipe_detail = self.recipes_tab.recipe_detail
    # ── TAB POSICIÓN ──────────────────────────────────────────
    def _build_position_tab(self):
        self.position_tab = PositionTab(
            self.tabview,
            on_recipe_change=self._on_pos_recipe_change,
            on_section_change=lambda v=None: self._update_pos_info(),
            on_inc_vuelta=self._inc_pos,
            on_apply_position=self._apply_position,
        )
        self.position_tab.build()

        # Referencias puente para mantener compatibilidad temporal
        self.pos_recipe_var = self.position_tab.pos_recipe_var
        self.pos_recipe_combo = self.position_tab.pos_recipe_combo
        self.pos_sec_var = self.position_tab.pos_sec_var
        self.pos_sec_combo = self.position_tab.pos_sec_combo
        self.pos_sec_info = self.position_tab.pos_sec_info
        self.pos_capa_var = self.position_tab.pos_capa_var
        self.pos_capa_info = self.position_tab.pos_capa_info
        self.pos_vuelta_var = self.position_tab.pos_vuelta_var
        self.pos_summary = self.position_tab.pos_summary
    # ── TAB CONFIGURACIÓN ─────────────────────────────────────
    def _build_config_tab(self):
        self.config_tab = ConfigTab(
            self.tabview,
            cfg=self.cfg,
            on_save_local=self._guardar_config_local,
            on_send_config=self._enviar_config_esp,
        )
        self.config_tab.build()

        # Referencia puente para mantener compatibilidad temporal
        self.cfg_entries = self.config_tab.cfg_entries
    # ── TAB MONITOR ───────────────────────────────────────────
    def _build_monitor_tab(self):
        self.monitor_tab = MonitorTab(
            self.tabview,
            on_clear=self._clear_monitor,
        )
        self.monitor_tab.build()

        # Referencia puente para compatibilidad temporal
        self.monitor_box = self.monitor_tab.monitor_box

    def _init_control_controller(self):
        hooks = ControlUiHooks(
            show_error=lambda title, msg: messagebox.showerror(title, msg),
            show_warning=lambda title, msg: messagebox.showwarning(title, msg),
            confirm=lambda title, msg: messagebox.askyesno(title, msg),
            log=lambda msg, tag="normal": self.log(msg, tag),
            after=lambda ms, fn: self.after(ms, fn),

            get_loaded_recipe_name=lambda: self.esp_rec.get(),
            get_run_recipe_name=lambda: self.run_recipe_var.get(),
            get_jog_step_mm=lambda: self.jog_paso_var.get(),
            mm_to_steps=self._mm_a_pasos_jog,

            set_manual_mode_active=lambda active: self._sync_manual_btn(active),
            set_alert=lambda text, color=ACCENT_YELLOW: self._show_alert(text, color),
            set_jog_running=lambda direction: self.control_tab.set_jog_running(direction),
            set_jog_stopped=lambda: self.control_tab.set_jog_stopped(),
            set_jog_status=lambda text, color=TEXT_SECONDARY: self.control_tab.set_jog_status(text, color),
        )

        self.control_controller = ControlController(
            state=self.app_state,
            use_simulator=self.use_simulator,
            machine=self.machine,
            serial=self.serial,
            ui=hooks,
        )

    def _sync_manual_btn(self, es_manual: bool):
        self._manual_activo = es_manual
        self.app_state.manual_activo = es_manual

        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_manual_mode_active(es_manual)
            return

        if es_manual:
            self.btn_manual.configure(
                text="⚙  DESACTIVAR MANUAL",
                fg_color=ACCENT_RED,
                hover_color="#CC2222",
                text_color=TEXT_PRIMARY,
            )
        else:
            self.btn_manual.configure(
                text="⚙  ACTIVAR MODO MANUAL",
                fg_color=ACCENT_ORANGE,
                hover_color="#CC6633",
                text_color=BG_DARK,
            )

    # ── JOG ───────────────────────────────────────────────────
    def _set_jog_paso(self, mm: float):
        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_jog_step(mm)
            return

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
            if hasattr(self, "control_tab") and self.control_tab:
                mm = float(self.control_tab.get_jog_step_entry_value())
            else:
                mm = float(self.jog_paso_entry.get().strip())

            if mm <= 0 or mm > 200:
                raise ValueError("fuera de rango")

            self._set_jog_paso(mm)

        except ValueError as e:
            messagebox.showerror(
                "Error",
                f"Valor inválido: {e}\n"
                "Introduce un número entre 0.01 y 200"
            )

    def _mm_a_pasos_jog(self, mm: float) -> int:
        return max(1, int(round(mm * 160.0)))

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

        if hasattr(self, "config_tab") and self.config_tab and self.config_tab.backend_var:
            backend_label = self.config_tab.backend_var.get().strip().lower()
            cfg["machine_backend"] = "serial" if backend_label == "serial" else "simulated"

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
        if hasattr(self, "position_tab") and self.position_tab:
            self.position_tab.set_section_values(vals)
            if vals:
                self.position_tab.set_section(vals[0])
            self.position_tab.set_vuelta("0.0")
        else:
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

            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_section_info(f"{nom}  [{tipo}]")
            else:
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

            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_capa(str(capa_num))
            else:
                self.pos_capa_var.set(str(capa_num))
            capa_info_text = (
                f"Capa {capa_num} ({vueltas_capa:.0f}v)  {d}\n"
                f"Rango: 0 – {total_sec:.0f}v acum."
            )
            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_capa_info(capa_info_text)
            else:
                self.pos_capa_info.configure(text=capa_info_text)

        except (IndexError, ValueError):
            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_capa_info("")
            else:
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
                if hasattr(self, "position_tab") and self.position_tab:
                    self.position_tab.set_vuelta(str(v))
                else:
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
                lambda: (
                    self.position_tab.set_summary(f"✓ S{sec_num} C{capa_num} @{vuelta_acum}v")
                    if hasattr(self, "position_tab") and self.position_tab
                    else self.pos_summary.configure(text=f"✓ S{sec_num} C{capa_num} @{vuelta_acum}v")
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

    # ── Recetas ───────────────────────────────────────────────
    def _load_recipe_list(self):
        for w in self.recipe_list_frame.winfo_children():
            w.destroy()

        names = list_recipes()
        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_run_recipes(names)
        else:
            self.run_combo.configure(values=names)

        if hasattr(self, "position_tab") and self.position_tab:
            self.position_tab.set_recipe_values(names)
        elif hasattr(self, "pos_recipe_combo"):
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

        if hasattr(self, "recipes_tab") and self.recipes_tab:
            self.recipes_tab.set_recipe_detail(detail)
        else:
            self.recipe_detail.configure(state="normal")
            self.recipe_detail.delete("1.0", "end")
            self.recipe_detail.insert("1.0", detail)
            self.recipe_detail.configure(state="disabled")

        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_selected_run_recipe(name)
        else:
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

        if hasattr(self, "recipes_tab") and self.recipes_tab:
            self.recipes_tab.clear_recipe_detail()
        else:
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
            if hasattr(self, "monitor_tab") and self.monitor_tab:
                self.monitor_tab.append(txt, tag)
            else:
                self.monitor_box.configure(state="normal")
                self.monitor_box._textbox.insert("end", txt, tag)
                self.monitor_box._textbox.see("end")
                self.monitor_box.configure(state="disabled")

        self.after(0, _ins)

    def _clear_monitor(self):
        if hasattr(self, "monitor_tab") and self.monitor_tab:
            self.monitor_tab.clear()
            return

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
        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_alert(text, color)
            return

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
        if pos_val:
            if hasattr(self, "control_tab") and self.control_tab:
                self.after(
                    0,
                    lambda v=pos_val: self.control_tab.set_jog_position(f"Pos: {v}cm"),
                )
            elif hasattr(self, "jog_pos_label"):
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
            if hasattr(self, "control_tab") and self.control_tab:
                self.after(
                    0,
                    lambda n=rec_name: self.control_tab.set_selected_run_recipe(n)
                )
            else:
                self.after(0, lambda n=rec_name: self.run_recipe_var.set(n))

    def on_connection_change(self, connected, info):
        self.connected = connected
        self.app_state.connected = connected

        if self.control_controller:
            self.control_controller.sync_connection(connected)

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

                if not self.use_simulator:
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
                if hasattr(self, "control_tab") and self.control_tab:
                    self.control_tab.set_manual_mode_active(False)
                else:
                    self.btn_manual.configure(
                        text="⚙  ACTIVAR MODO MANUAL",
                        fg_color=ACCENT_ORANGE,
                        hover_color="#CC6633",
                        text_color=BG_DARK,
                    )

        self.after(0, _upd)

    def _toggle_connect(self):
        if self.use_simulator:
            if self.connected:
                self.machine.disconnect()
                self.on_connection_change(False, "Simulador")
            else:
                ok = self.machine.connect()
                if ok:
                    self.on_connection_change(True, "Simulador")
                else:
                    self.on_connection_change(False, "No se pudo iniciar el simulador")
            return

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