import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import subprocess
import sys
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
from app.services.status_service import StatusService
from app.services.recipe_service import RecipeService
from app.services.config_service import ConfigService
from app.services.log_service import LogService

from app.serial_manager import SerialManager
from app.recipe_manager import (
    load_recipe,
    list_recipes,
    delete_recipe,
)

from app.core.theme import (
    APP_BG,
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
    F_BODY,
    setup_theme,
    TEXT_ON_ACCENT,
    get_theme_mode_label,
    cycle_theme_mode,
)
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
        self.configure(fg_color=APP_BG)

        self.cfg = cargar_config()

        backend = str(self.cfg.get("machine_backend", "simulated")).strip().lower()
        self.use_simulator = backend == "simulated"
        self.machine = create_machine_controller(self.cfg)
        self.app_state = AppState()
        self.control_controller = None
        self.status_service = StatusService()
        self.recipe_service = RecipeService()
        self.config_service = ConfigService()
        self.log_service = LogService(
            app_name = "bobinadora",
            fsync_enabled = False,
        )

        self.connected            = False
        self.status_poll_job = None
        self.status_poll_busy = False
        self.status_poll_interval_ms = 500
        self.current_recipe       = None
        self.selected_recipe_name = None
        self.current_runtime_recipe = None
        self.current_runtime_recipe_name = ""
        self.current_runtime_section_index = 0
        self.current_runtime_vt_base_x100 = 0
        self.last_stm32_vt_x100 = 0
        self.current_runtime_events = []
        self.current_runtime_event_index = 0
        self.current_runtime_active_event = None
        self.current_runtime_waiting_pause = False
        self.current_runtime_completed = False
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
        if hasattr(self.machine, "attach_serial_manager"):
            self.machine.attach_serial_manager(self.serial)

        self._init_control_controller()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self.after(100, self._machine_poll)

        self.log_service.session_start(
            f"App iniciada | backend={backend} | puerto_cfg={self.cfg.get('puerto', '')}"
        )

        recent_error = self.log_service.get_last_relevant_event(["ERROR"])
        closed_cleanly = self.log_service.was_last_session_closed_cleanly()

        if recent_error:
            self.log(f"Último error registrado: {recent_error}", "info")

        if not closed_cleanly:
            self.log(
                "La sesión anterior no termino con cierre limpio",
                "warn",
            )

    def _machine_poll(self):
        try:
            self.control_controller.poll_machine()
        finally:
            self.after(100, self._machine_poll)
    
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
        self.header_panel = HeaderPanel(
            self,
            on_toggle_theme=self._toggle_theme_mode,
            theme_label=get_theme_mode_label(self.cfg.get("theme_mode", "light")),
        )
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
        self.btn_manual = self.control_tab.btn_manual
        self.run_recipe_var = self.control_tab.run_recipe_var
        self.run_combo = self.control_tab.run_combo

        self.jog_paso_actual = self.control_tab.jog_paso_actual
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
            get_selected_port=lambda: self.port_var.get(),
            mm_to_steps=self._mm_a_pasos_jog,
            save_selected_port=self._save_selected_port,

            set_manual_mode_active=lambda active: self._sync_manual_btn(active),
            set_alert=lambda text, color=ACCENT_YELLOW: self._show_alert(text, color),
            set_jog_running=lambda direction: self.control_tab.set_jog_running(direction),
            set_jog_stopped=lambda: self.control_tab.set_jog_stopped(),
            set_jog_status=lambda text, color=TEXT_SECONDARY: self.control_tab.set_jog_status(text, color),
            set_jog_position=lambda text: self.control_tab.set_jog_position(text),

            set_connection_indicator=lambda text, color: self.conn_indicator.configure(
                text=text,
                text_color=color,
            ),
            set_connect_button_state=lambda text, fg, hover, txt_color: self.btn_connect.configure(
                text=text,
                fg_color=fg,
                hover_color=hover,
                text_color=txt_color,
            ),

            set_machine_state=lambda value: self.esp_estado.set(value),
            set_recipe_name=lambda value: self.esp_rec.set(value),
            set_section=lambda value: self.esp_sec.set(value),
            set_total_sections=lambda value: self.esp_tsec.set(value),
            set_layer=lambda value: self.esp_capa.set(value),
            set_total_layers=lambda value: self.esp_tcap.set(value),
            set_target_turns=lambda value: self.esp_meta.set(value),
            set_current_turns=lambda value: self.esp_vueltas.set(value),
            set_rpm=lambda value: self.esp_rpm.set(value),
            set_position=lambda value: self.esp_pos.set(value),
            set_brake_status=lambda value: self.esp_freno.set(value),
            set_motor_status=lambda value: self.esp_variador.set(value),
            start_runtime_event=lambda: self._start_next_runtime_event(),
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
                text_color=TEXT_ON_ACCENT,
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
                    text_color=TEXT_ON_ACCENT,
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
        backend_label = None
        theme_label = None
        if hasattr(self, "config_tab") and self.config_tab and self.config_tab.backend_var:
            backend_label = self.config_tab.backend_var.get()
        if hasattr(self, "config_tab") and self.config_tab and self.config_tab.theme_var:
            theme_label = self.config_tab.theme_var.get()

        result = self.config_service.read_config_from_entries(
            current_config=self.cfg,
            cfg_entries=self.cfg_entries,
            backend_label=backend_label,
            theme_label=theme_label,
        )
        return result.config

    def _guardar_config_local(self):
        old_theme = str(self.cfg.get("theme_mode", "light")).strip().lower()
        cfg = self._leer_cfg_entries()
        cfg = self.config_service.apply_selected_port(cfg, self.port_var.get())
        self.cfg = cfg
        guardar_config(self.cfg)
        self._sync_theme_ui()
        self.log("Configuración guardada localmente", "ok")

        new_theme = str(self.cfg.get("theme_mode", "light")).strip().lower()
        if new_theme != old_theme:
            self._prompt_theme_restart(new_theme)

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
        comandos = self.config_service.build_stm32_config_commands(self.cfg)

        for cmd in comandos:
            resp = self.serial.send(cmd)

            tiene_error = bool(
                resp and any(
                    "ERR" in str(x) or "CMD?" in str(x)
                    for x in resp
                )
            )

            if resp:
                for line in resp:
                    if isinstance(line, str) and line.startswith("STATUS:"):
                        self.after(0, lambda m=line: self._parse_status(m))

            tag = "error" if tiene_error else "ok"
            self.log(f"CONFIG STM32 {cmd} → {resp}", tag)
        self.after(0, self._start_status_polling)

    # ── Posición ──────────────────────────────────────────────
    def _on_pos_recipe_change(self, name=None):
        name = name or self.pos_recipe_var.get()
        rec = load_recipe(name)
        if not rec:
            return

        vals = self.recipe_service.get_section_number_values(rec)

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
            sec_num = int(self.pos_sec_var.get())
            try:
                current_turns = float(self.pos_vuelta_var.get())
            except ValueError:
                self.pos_vuelta_var.set("0.0")
                current_turns = 0.0

            position_data = self.recipe_service.get_section_position_data(
                rec,
                sec_num,
                current_turns,
            )

            section_info_text = self.recipe_service.build_section_info_text(rec, sec_num)
            layer_info_text = self.recipe_service.build_layer_info_text(position_data)

            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_section_info(section_info_text)
                self.position_tab.set_capa(str(position_data.layer_number))
                self.position_tab.set_capa_info(layer_info_text)
            else:
                self.pos_sec_info.configure(text=section_info_text)
                self.pos_capa_var.set(str(position_data.layer_number))
                self.pos_capa_info.configure(text=layer_info_text)

        except ValueError:
            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_capa_info("")
            else:
                self.pos_capa_info.configure(text="")

    def _inc_pos(self, field, delta):
        if field != "vuelta":
            return

        try:
            rec = load_recipe(self.pos_recipe_var.get())
            if not rec:
                return

            sec_num = int(self.pos_sec_var.get())
            current_turns = float(self.pos_vuelta_var.get())

            new_value = self.recipe_service.increment_turn_value(
                rec,
                sec_num,
                current_turns,
                delta,
            )

            if hasattr(self, "position_tab") and self.position_tab:
                self.position_tab.set_vuelta(str(new_value))
            else:
                self.pos_vuelta_var.set(str(new_value))

            self._update_pos_info()

        except ValueError:
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
            current_turns = float(self.pos_vuelta_var.get())
        except ValueError:
            messagebox.showerror("Error", "Valores inválidos")
            return

        recipe = load_recipe(rec_name)
        if not recipe:
            messagebox.showerror("Error", f"'{rec_name}' no encontrada")
            return

        try:
            position_data = self.recipe_service.get_section_position_data(
                recipe,
                sec_num,
                current_turns,
            )
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        resumen = self.recipe_service.build_position_summary(
            rec_name,
            position_data,
        )

        if not messagebox.askyesno("Confirmar inicio", resumen):
            return

        def _thread():
            self.log(
                f"=== REANUDANDO S{sec_num} V_acum={current_turns} ===",
                "info",
            )

            self._send_recipe_thread(recipe)
            time.sleep(0.3)

            if position_data.pulses > 0:
                self.log(
                    "Reanudación desde vuelta distinta de 0 pendiente en STM32: "
                    "requiere comando SET_ENCODER_COUNT / SET_POS.",
                    "error",
                )
                self.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Pendiente STM32",
                        "La reanudación desde una vuelta acumulada distinta de 0 "
                        "todavía no está implementada en el firmware STM32.\n\n"
                        "Por ahora inicia desde vuelta 0 o ejecuta HOMING."
                    )
                )
                return

            self.log("Vuelta 0 — posición lógica en 0", "info")

            sec_idx = sec_num - 1
            commands = self.recipe_service.build_stm32_run_section_commands(recipe, sec_idx)

            has_error = False
            last_response = None

            for label, command in commands:
                resp = self.serial.send(command)
                self.log(f"RUN S{sec_num} STM32 {label}: {command} → {resp}", "ok")
                last_response = resp

                if resp and any("ERR" in str(x) or "CMD?" in str(x) for x in resp):
                    has_error = True

            if has_error:
                self.after(
                    0,
                    lambda r=last_response: messagebox.showerror(
                        "Error",
                        f"Controlador rechazó RUN S{sec_num} STM32:\n{r}",
                    )
                )
                return

            self.after(
                0,
                lambda: (
                    self.position_tab.set_summary(
                        f"✓ S{sec_num} C{position_data.layer_number} @{current_turns}v"
                    )
                    if hasattr(self, "position_tab") and self.position_tab
                    else self.pos_summary.configure(
                        text=f"✓ S{sec_num} C{position_data.layer_number} @{current_turns}v"
                    )
                )
            )
            self.after(
                0,
                lambda: self._show_alert(
                    f"Reanudando S{sec_num} C{position_data.layer_number} @{current_turns}v — Pise el PEDAL",
                    ACCENT_GREEN,
                )
            )

        threading.Thread(target=_thread, daemon=True).start()
    # ── Recetas ───────────────────────────────────────────────
    def _load_recipe_list(self):
        for w in self.recipe_list_frame.winfo_children():
            w.destroy()

        names = self.recipe_service.get_recipe_names(list_recipes())
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
        recipe = load_recipe(name)
        selected = self.recipe_service.build_selected_recipe_data(name, recipe)
        if not selected:
            return

        self.selected_recipe_name = selected.name
        self.current_recipe = selected.recipe

        if hasattr(self, "recipes_tab") and self.recipes_tab:
            self.recipes_tab.set_recipe_detail(selected.detail_text)
        else:
            self.recipe_detail.configure(state="normal")
            self.recipe_detail.delete("1.0", "end")
            self.recipe_detail.insert("1.0", selected.detail_text)
            self.recipe_detail.configure(state="disabled")

        run_name = self.recipe_service.get_recipe_run_name(selected.recipe)
        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_selected_run_recipe(run_name)
        else:
            self.run_recipe_var.set(run_name)

    def _delete_selected_recipe(self):
        ok, message = self.recipe_service.can_delete_recipe(self.selected_recipe_name)
        if not ok:
            messagebox.showwarning("Aviso", message)
            return

        name = self.selected_recipe_name

        if not messagebox.askyesno(
            "Confirmar",
            self.recipe_service.build_delete_confirmation_message(name),
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
        nombre = self.recipe_service.get_recipe_display_name(recipe)
        usa_husillo = self.recipe_service.recipe_uses_husillo(recipe)

        self.log(f"── Preparando '{nombre}' en STM32 ──", "info")
        self.log(
            "Modo receta: CON HUSILLO" if usa_husillo else "Modo receta: SOLO MANDRIL / SIN HUSILLO",
            "info",
        )

        commands = self.recipe_service.build_stm32_recipe_prepare_commands(recipe)

        has_error = False
        last_response = None

        for label, command in commands:
            response = self.serial.send(command)
            self.log(f"  {label}: {command} → {response}")
            last_response = response

            if response and any("ERR" in str(x) or "CMD?" in str(x) for x in response):
                has_error = True

        if has_error:
            self.log(
                f"✗ STM32 rechazó configuración de receta: {last_response}",
                "error",
            )
            return False
        else:
            self.after(
                0,
                lambda r=recipe, n=nombre: self._prepare_runtime_plan(r, n),
            )

            self.log(
                f"✓ '{nombre}' preparada en STM32",
                "ok",
            )
            return True

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
            f"¿Cargar y preparar '{name}'?\n\n"
            f"Secciones : {self.recipe_service.get_section_count(recipe)}\n"
            f"Espesor   : {recipe.get('espesorX10', 10) / 10:.1f}mm\n\n"
            f"START preparará el siguiente evento de receta.\n"
            f"El movimiento real del mandril quedará para el PEDAL."
        ):
            return

        def _thread():
            self.log(f"=== CARGANDO '{name}' ===", "info")

            ok = self._send_recipe_thread(recipe)
            if ok is False:
                return

            # Damos un pequeño margen para que _prepare_runtime_plan()
            # se ejecute en el hilo de UI mediante self.after().
            self.after(
                300,
                self._start_next_runtime_event,
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
        result = self.recipe_service.save_recipe_flow(recipe)

        if not result.ok:
            if result.error_message.startswith("Error de validación:"):
                messagebox.showerror("Error de validación", result.error_message.replace("Error de validación: ", "", 1))
            else:
                messagebox.showerror("Error al guardar", result.error_message)
            return

        self._load_recipe_list()
        self.log(f"✓ Receta '{result.recipe_name}' guardada", "ok")

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
        msg = str(msg)
        try:
            persisted_line = self.log_service.log(msg, tag=tag)
        except Exception as e:
            persisted_line = None
            print(f"[LogService] Error al escribir log: {e}")
        
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
        return persisted_line

    def _clear_monitor(self):
        if hasattr(self, "monitor_tab") and self.monitor_tab:
            self.monitor_tab.clear()
            return

        self.monitor_box.configure(state="normal")
        self.monitor_box.delete("1.0", "end")
        self.monitor_box.configure(state="disabled")

    def _on_app_close(self):
        try:
            self.log_service.session_end("Cierre solicitado por usuario")
        except Exception as e:
            print(f"[LogService] Error al registrar cierre de sesión: {e}")

        try:
            if hasattr(self, "serial") and self.serial:
                if hasattr(self.serial, "disconnect"):
                    self.serial.disconnect()
        except Exception as e:
            print(f"[App] Error al cerrar serial: {e}")

        try:
            self.log_service.close()
        except Exception as e:
            print(f"[LogService] Error al cerrar archivo de log: {e}")

        self.destroy()

    # ── Callbacks serial ──────────────────────────────────────

    def on_serial_message(self, msg):
        if msg.startswith("STATUS:"):
            self._parse_status(msg)
            return

        effect = self.status_service.get_ui_effect(msg)
        self.log(msg, effect.log_tag)

        if effect.alert_text and effect.alert_color:
            self.after(
                0,
                lambda t=effect.alert_text, c=effect.alert_color: self._show_alert(t, c),
            )

    def _show_alert(self, text, color=ACCENT_YELLOW):
        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_alert(text, color)
            return

        self.alert_label.configure(
            text=text,
            text_color=color,
        )

    def _safe_int_value(self, value, default=0):
        try:
            if value in ("", None, "--"):
                return default
            return int(float(value))
        except Exception:
            return default

    def _set_runtime_recipe(
        self,
        recipe,
        name: str | None = None,
        section_index: int = 0,
        reset_baseline: bool = False,
    ):
        if not recipe:
            return

        clean_name = name or self.recipe_service.get_recipe_display_name(recipe)

        self.current_runtime_recipe = recipe
        self.current_runtime_recipe_name = clean_name
        self.current_runtime_section_index = max(0, int(section_index or 0))

        if reset_baseline:
            self.current_runtime_vt_base_x100 = self.last_stm32_vt_x100

        secciones = recipe.get("secciones", [])
        total_sections = len(secciones)

        self.esp_rec.set(clean_name or "--")
        self.esp_sec.set(str(self.current_runtime_section_index + 1) if total_sections else "--")
        self.esp_tsec.set(str(total_sections) if total_sections else "--")

        if hasattr(self.machine, "snapshot"):
            self.machine.snapshot.recipe_name = clean_name
            self.machine.snapshot.current_layer = 1
            self.machine.snapshot.target_turns = 0.0

    def _prepare_runtime_plan(self, recipe, name: str):
        events = self.recipe_service.build_runtime_plan(recipe)

        self.current_runtime_events = events
        self.current_runtime_event_index = 0
        self.current_runtime_active_event = None
        self.current_runtime_waiting_pause = False
        self.current_runtime_completed = False

        self._set_runtime_recipe(
            recipe,
            name,
            section_index=0,
            reset_baseline=True,
        )

        self.log(f"Plan de receta generado: {len(events)} eventos", "info")

        if events:
            first = events[0]
            self.log(f"Siguiente evento: {first.label}", "info")
            self._show_alert(
                f"Receta lista — START prepara: {first.label}",
                ACCENT_BLUE,
            )
        else:
            self._show_alert(
                "Receta sin eventos ejecutables",
                ACCENT_YELLOW,
            )

        return bool(events)

    def _build_runtime_event_commands(self, event):
        commands = []

        idx = self.current_runtime_event_index
        events = self.current_runtime_events

        previous_event = events[idx - 1] if idx > 0 else None
        new_section = previous_event is None or previous_event.section_index != event.section_index

        # Si no es el primer evento, venimos de una pausa.
        if idx > 0:
            commands.append(("ACK PAUSA", "ACK_PAUSE"))

        # Inicio real de receta: reseteo completo.
        if idx == 0:
            commands.append(("RESET RECETA", "SYNC_RESET"))

        # Nueva sección: resetear solo vueltas, no posición de husillo.
        elif new_section:
            commands.append(("RESET VUELTAS SECCIÓN", "VT_RESET"))

        # Mantener espesor actualizado por seguridad.
        esp_x100 = self.recipe_service.get_espesor_x100(self.current_runtime_recipe)
        commands.append(("ESPESOR", f"SET_ESP_X100:{esp_x100}"))

        if event.uses_husillo:
            commands.append(("DIRECCIÓN", f"SET_SYNC_DIR:{event.direction}"))

        commands.append(("MOTIVO", f"SET_TARGET_REASON:{event.event_type}"))
        commands.append(("OBJETIVO", f"SET_TARGET_VT_X100:{event.vt_x100}"))
        commands.append(("TARGET", "TARGET_ON"))

        if event.uses_husillo:
            commands.append(("SYNC", "SYNC_ON"))
        else:
            commands.append(("SYNC", "SYNC_OFF"))

        return commands

    def _start_next_runtime_event(self) -> bool:
        if not self.connected:
            messagebox.showerror("Error", "No hay conexión con el controlador")
            return True

        if not self.current_runtime_recipe or not self.current_runtime_events:
            return False

        if self.current_runtime_waiting_pause:
            self._show_alert(
                "Evento en curso — espere la pausa por objetivo",
                ACCENT_YELLOW,
            )
            return True

        if self.current_runtime_event_index >= len(self.current_runtime_events):
            self._show_alert(
                "✓ Receta completa — no hay más eventos",
                ACCENT_GREEN,
            )
            self.log("START ignorado: receta completa", "ok")
            return True

        event = self.current_runtime_events[self.current_runtime_event_index]

        def _worker():
            self.log(
                f"=== EVENTO {self.current_runtime_event_index + 1}/"
                f"{len(self.current_runtime_events)} ===",
                "info",
            )
            self.log(event.label, "info")

            commands = self._build_runtime_event_commands(event)

            has_error = False
            last_response = None

            pause_reached_immediately = False

            for label, command in commands:
                resp = self.serial.send(command)
                self.log(f"  {label}: {command} → {resp}", "ok")
                last_response = resp

                if resp and any("PAUSE_TARGET" in str(x) for x in resp):
                    pause_reached_immediately = True
                    break

                if resp and any("ERR" in str(x) or "CMD?" in str(x) for x in resp):
                    has_error = True
                    break

            if has_error:
                self.after(
                    0,
                    lambda r=last_response: messagebox.showerror(
                        "Error",
                        f"STM32 rechazó evento de receta:\n{r}",
                    )
                )
                self.after(
                    0,
                    lambda: self._show_alert(
                        "Error al preparar evento de receta",
                        ACCENT_RED,
                    )
                )
                return
            
            if pause_reached_immediately:
                def _mark_immediate_pause():
                    self.current_runtime_active_event = event
                    self.current_runtime_waiting_pause = True
                    self.current_runtime_section_index = event.section_index

                    self.esp_sec.set(str(event.section_number))
                    self.esp_capa.set(str(event.layer_number) if event.layer_number else "--")
                    self.esp_meta.set(f"{event.turns:.2f}")

                    self._complete_runtime_event(event)

                self.after(0, _mark_immediate_pause)
                return

            def _mark_started():
                self.current_runtime_active_event = event
                self.current_runtime_waiting_pause = True
                self.current_runtime_section_index = event.section_index

                self.esp_sec.set(str(event.section_number))
                self.esp_capa.set(str(event.layer_number) if event.layer_number else "--")
                self.esp_meta.set(f"{event.turns:.2f}")

                if event.uses_husillo:
                    modo = f"HUSILLO {event.direction}"
                else:
                    modo = "SIN HUSILLO"

                self._show_alert(
                    f"▶ Evento armado: {event.label} — {modo}",
                    ACCENT_GREEN,
                )

            self.after(0, _mark_started)

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def _mark_runtime_event_paused(self, status):
        if not self.current_runtime_waiting_pause:
            return

        if not getattr(status, "is_paused_target", False):
            return

        event = self.current_runtime_active_event
        self._complete_runtime_event(event)

    def _finish_runtime_recipe(self):
        recipe_name = self.current_runtime_recipe_name or self.run_recipe_var.get() or "Receta"

        self.current_runtime_waiting_pause = False
        self.current_runtime_active_event = None
        self.current_runtime_completed = True

        self.log(f"✓ RECETA COMPLETA: {recipe_name}", "ok")

        self.esp_estado.set("Receta completa")
        self.esp_meta.set("--")
        self.esp_variador.set("Ciclo terminado")

        self._show_alert(
            f"✓ RECETA COMPLETA — {recipe_name}",
            ACCENT_GREEN,
        )

        if hasattr(self, "control_tab") and self.control_tab:
            self.control_tab.set_alert(
                f"✓ RECETA COMPLETA — {recipe_name}",
                ACCENT_GREEN,
            )

    def _complete_runtime_event(self, event):
        self.current_runtime_waiting_pause = False
        self.current_runtime_active_event = None
        self.current_runtime_event_index += 1

        if event:
            self.log(f"✓ Evento completado: {event.label}", "ok")

        if self.current_runtime_event_index >= len(self.current_runtime_events):
            self._finish_runtime_recipe()
            return

        next_event = self.current_runtime_events[self.current_runtime_event_index]
        self._show_alert(
            f"⏸ Pausa por objetivo — START prepara: {next_event.label}",
            ACCENT_YELLOW,
        )
        self.log(f"Siguiente evento: {next_event.label}", "info")

    def _get_runtime_layer_info(self, turns: float) -> dict:
        recipe = self.current_runtime_recipe
        if not recipe:
            return {}

        secciones = recipe.get("secciones", [])
        if not secciones:
            return {}

        sec_idx = self.current_runtime_section_index
        if sec_idx < 0 or sec_idx >= len(secciones):
            sec_idx = 0

        sec = secciones[sec_idx]
        capas = sec.get("capas", [])

        if not capas:
            return {
                "section": str(sec_idx + 1),
                "total_sections": str(len(secciones)),
                "layer": "--",
                "total_layers": "--",
                "target": "--",
                "turns": f"{turns:.2f}",
            }

        layer_idx = 0
        for idx, meta in enumerate(capas):
            if turns <= float(meta):
                layer_idx = idx
                break
        else:
            layer_idx = len(capas) - 1

        target = float(capas[layer_idx])

        return {
            "section": str(sec_idx + 1),
            "total_sections": str(len(secciones)),
            "layer": str(layer_idx + 1),
            "total_layers": str(len(capas)),
            "target": f"{target:.1f}",
            "turns": f"{turns:.2f}",
            "section_name": sec.get("nombre", ""),
            "section_type": sec.get("tipo", "BOB"),
        }

    def _apply_runtime_recipe_display(self, status):
        """
        Combina:
        - receta local Python
        - VT_ABS_x100 de STM32

        para pintar panel izquierdo como antes.
        """
        raw_vt_abs_x100 = self._safe_int_value(
            getattr(status, "vt_abs_x100", "") or getattr(status, "turns_x100", "0"),
            0,
        )

        self.last_stm32_vt_x100 = raw_vt_abs_x100

        if not self.current_runtime_recipe:
            return False

        turns = abs(raw_vt_abs_x100) / 100.0

        info = self._get_runtime_layer_info(turns)
        if not info:
            return False

        recipe_name = self.current_runtime_recipe_name or "--"

        active_event = self.current_runtime_active_event
        target_text = info.get("target", "--")

        if active_event is not None:
            target_text = f"{active_event.turns:.2f}"

        self.esp_rec.set(recipe_name)
        self.esp_sec.set(info.get("section", "--"))
        self.esp_tsec.set(info.get("total_sections", "--"))
        self.esp_capa.set(info.get("layer", "--"))
        self.esp_tcap.set(info.get("total_layers", "--"))
        self.esp_meta.set(target_text)
        self.esp_vueltas.set(info.get("turns", "0.00"))

        if hasattr(self.machine, "snapshot"):
            snap = self.machine.snapshot
            snap.recipe_name = recipe_name
            snap.current_turns = turns
            snap.current_layer = self._safe_int_value(info.get("layer", "0"), 0)

            try:
                snap.target_turns = float(str(target_text).replace("--", "0"))
            except Exception:
                snap.target_turns = 0.0

        return True

    def _parse_status(self, msg):
        status = self.status_service.parse_status_ui_data(msg)
        if not status:
            return

        if hasattr(self.machine, "apply_status_ui_data"):
            self.machine.apply_status_ui_data(status)

        # Estado máquina siempre viene de STM32.
        self.after(0, lambda s=status.estado_texto: self.esp_estado.set(s))

        # Datos base STM32.
        if status.current_turns and not self.current_runtime_recipe:
            self.after(0, lambda v=status.current_turns: self.esp_vueltas.set(v))

        if status.rpm:
            self.after(0, lambda v=status.rpm: self.esp_rpm.set(v))

        if status.position_cm:
            self.after(0, lambda v=status.position_cm: self.esp_pos.set(v))

        self.after(0, lambda v=status.brake_text: self.esp_freno.set(v))
        self.after(0, lambda v=status.motor_text: self.esp_variador.set(v))
        self.after(0, lambda m=status.is_manual: self._sync_manual_btn(m))

        if status.position_label:
            if hasattr(self, "control_tab") and self.control_tab:
                self.after(
                    0,
                    lambda v=status.position_label: self.control_tab.set_jog_position(v),
                )
            elif hasattr(self, "jog_pos_label"):
                self.after(
                    0,
                    lambda v=status.position_label: self.jog_pos_label.configure(text=v),
                )

        # Si hay receta local activa, ella manda sobre REC/SEC/CAPA/META.
        runtime_applied = self._apply_runtime_recipe_display(status)

        if not runtime_applied:
            # Solo usamos datos del STATUS si no son genéricos STM32.
            recipe_name = str(status.recipe_name or "").strip()

            if recipe_name and recipe_name.lower() not in ("stm32", "ninguna", "none"):
                self.after(0, lambda v=recipe_name: self.esp_rec.set(v))

                if hasattr(self, "control_tab") and self.control_tab:
                    self.after(
                        0,
                        lambda n=recipe_name: self.control_tab.set_selected_run_recipe(n),
                    )
                else:
                    self.after(0, lambda n=recipe_name: self.run_recipe_var.set(n))

            if status.section:
                self.after(0, lambda v=status.section: self.esp_sec.set(v))
            if status.total_sections:
                self.after(0, lambda v=status.total_sections: self.esp_tsec.set(v))
            if status.total_layers:
                self.after(0, lambda v=status.total_layers: self.esp_tcap.set(v))
            if status.target_turns:
                self.after(0, lambda v=status.target_turns: self.esp_meta.set(v))

            self.after(0, lambda v=status.layer_display: self.esp_capa.set(v))

        allow_status_alert = True

        if getattr(self, "current_runtime_completed", False):
            if getattr(status, "state_machine", "") in ("PAUSED_TARGET", "IDLE", "STOPPED"):
                allow_status_alert = False

        if status.alert_text and status.alert_color and allow_status_alert:
            self.after(
                0,
                lambda t=status.alert_text, c=status.alert_color: self._show_alert(t, c),
            )
        if getattr(status, "is_paused_target", False):
            self.after(0, lambda s=status: self._mark_runtime_event_paused(s))

    def _start_status_polling(self):
        if self.use_simulator:
            return

        self._stop_status_polling()
        self.status_poll_job = self.after(
            self.status_poll_interval_ms,
            self._poll_status_once,
        )

    def _stop_status_polling(self):
        if self.status_poll_job is not None:
            try:
                self.after_cancel(self.status_poll_job)
            except Exception:
                pass

        self.status_poll_job = None
        self.status_poll_busy = False

    def _poll_status_once(self):
        if not self.connected or self.use_simulator:
            self.status_poll_job = None
            self.status_poll_busy = False
            return

        if self.status_poll_busy:
            self.status_poll_job = self.after(
                self.status_poll_interval_ms,
                self._poll_status_once,
            )
            return

        self.status_poll_busy = True

        def _worker():
            try:
                resp = self.serial.send("STATUS", timeout_ms=250)

                if resp:
                    for line in resp:
                        if isinstance(line, str) and line.startswith("STATUS:"):
                            self.after(0, lambda m=line: self._parse_status(m))

            except Exception as e:
                self.after(0, lambda: self.log(f"STATUS polling error: {e}", "error"))

            finally:
                def _schedule_next():
                    self.status_poll_busy = False

                    if self.connected and not self.use_simulator:
                        self.status_poll_job = self.after(
                            self.status_poll_interval_ms,
                            self._poll_status_once,
                        )

                self.after(0, _schedule_next)

        threading.Thread(target=_worker, daemon=True).start()

    def on_connection_change(self, connected, info):
        already_connected = self.connected and connected

        self.connected = connected
        self.app_state.connected = connected

        if already_connected:
            return

        if not connected:
            self._stop_status_polling()

            if hasattr(self.machine, "mark_disconnected"):
                self.machine.mark_disconnected()

            if hasattr(self, "control_controller"):
                self.control_controller.sync_connection(connected, info)

            return

        if hasattr(self, "control_controller"):
            self.control_controller.sync_connection(connected, info)

        if connected and not self.use_simulator:
            self._stop_status_polling()
            self._enviar_config_esp()

    def _toggle_connect(self):
        self.control_controller.toggle_connect()

    def _refresh_ports(self):
        ports = self.serial.get_ports() if hasattr(self, "serial") else []
        self.port_combo.configure(values=ports)

        saved = self.cfg.get("puerto", "")
        if saved and saved in ports:
            self.port_var.set(saved)
        elif ports:
            self.port_var.set(ports[0])

    def _save_selected_port(self, port: str):
        self.cfg["puerto"] = port
        guardar_config(self.cfg)

    def _update_clock(self):
        self.clock_label.configure(
            text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        )
        self.after(1000, self._update_clock)

    def _sync_theme_ui(self):
        theme_label = get_theme_mode_label(self.cfg.get("theme_mode", "light"))

        if hasattr(self, "header_panel") and self.header_panel:
            self.header_panel.set_theme_label(theme_label)

        if hasattr(self, "config_tab") and self.config_tab:
            self.config_tab.set_theme_label(theme_label)

    def _toggle_theme_mode(self):
        current_mode = str(self.cfg.get("theme_mode", "light")).strip().lower()
        next_mode = cycle_theme_mode(current_mode)
        self.cfg["theme_mode"] = next_mode
        guardar_config(self.cfg)
        self._sync_theme_ui()
        self.log(
            f"Tema cambiado a {get_theme_mode_label(next_mode)}. Reinicie para aplicarlo.",
            "info",
        )
        self._prompt_theme_restart(next_mode)

    def _prompt_theme_restart(self, theme_mode: str):
        theme_label = get_theme_mode_label(theme_mode)
        restart_now = messagebox.askyesno(
            "Aplicar tema",
            f"El tema quedó en modo {theme_label}.\n\n"
            "Para aplicar todos los colores hace falta reiniciar la app.\n\n"
            "¿Reiniciar ahora?",
        )

        if restart_now:
            self._restart_app()

    def _restart_app(self):
        project_root = Path(__file__).resolve().parents[1]
        run_script = project_root / "run.py"
        python_executable = Path(sys.executable)

        try:
            self.log_service.session_end("Reinicio solicitado por cambio de tema")
        except Exception as e:
            print(f"[LogService] Error al registrar reinicio: {e}")

        try:
            if hasattr(self, "serial") and self.serial and hasattr(self.serial, "disconnect"):
                self.serial.disconnect()
        except Exception as e:
            print(f"[App] Error al cerrar serial antes de reinicio: {e}")

        try:
            self.log_service.close()
        except Exception as e:
            print(f"[LogService] Error al cerrar log antes de reinicio: {e}")

        try:
            subprocess.Popen(
                [str(python_executable), str(run_script)],
                cwd=str(project_root),
            )
        except Exception as e:
            messagebox.showerror(
                "Error",
                "No se pudo reiniciar la aplicación.\n\n"
                f"Detalle: {e}",
            )
            return

        self.destroy()
