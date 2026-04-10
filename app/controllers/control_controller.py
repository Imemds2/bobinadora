from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from app.state.app_state import AppState
from app.core.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_RED,
    ACCENT_YELLOW,
    BG_DARK,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


@dataclass
class ControlUiHooks:
    show_error: Callable[[str, str], None]
    show_warning: Callable[[str, str], None]
    confirm: Callable[[str, str], bool]
    log: Callable[[str, str], None]
    after: Callable[[int, Callable], None]

    get_loaded_recipe_name: Callable[[], str]
    get_run_recipe_name: Callable[[], str]
    get_jog_step_mm: Callable[[], float]
    get_selected_port: Callable[[], str]
    mm_to_steps: Callable[[float], int]
    save_selected_port: Callable[[str], None]

    set_manual_mode_active: Callable[[bool], None]
    set_alert: Callable[[str, str], None]
    set_jog_running: Callable[[str], None]
    set_jog_stopped: Callable[[], None]
    set_jog_status: Callable[[str, str], None]
    set_jog_position: Callable[[str], None]

    set_connection_indicator: Callable[[str, str], None]
    set_connect_button_state: Callable[[str, str, str, str], None]

    set_machine_state: Callable[[str], None]
    set_recipe_name: Callable[[str], None]
    set_section: Callable[[str], None]
    set_total_sections: Callable[[str], None]
    set_layer: Callable[[str], None]
    set_total_layers: Callable[[str], None]
    set_target_turns: Callable[[str], None]
    set_current_turns: Callable[[str], None]
    set_rpm: Callable[[str], None]
    set_position: Callable[[str], None]
    set_brake_status: Callable[[str], None]
    set_motor_status: Callable[[str], None]


class ControlController:
    """
    Orquesta acciones de control y ciclo de vida de máquina
    sin depender directamente de widgets concretos de Tk.
    """

    def __init__(
        self,
        *,
        state: AppState,
        use_simulator: bool,
        machine,
        serial,
        ui: ControlUiHooks,
    ):
        self.state = state
        self.use_simulator = use_simulator
        self.machine = machine
        self.serial = serial
        self.ui = ui

    # ---------------------------------------------------------
    # Helpers internos
    # ---------------------------------------------------------
    def _ensure_connected(self, message: str = "No conectado") -> bool:
        if not self.state.connected:
            self.ui.show_error("Error", message)
            return False
        return True

    def _recipe_loaded_for_manual(self) -> bool:
        rec = (self.ui.get_loaded_recipe_name() or "").strip()
        return rec not in ("", "--", "ninguna")

    def _manual_activation_confirmed(self) -> bool:
        return self.ui.confirm(
            "Activar Modo Manual",
            "¿Activar modo manual?\n\n"
            "El motor arrancará y parará con el PEDAL.\n"
            "El husillo se sincroniza con el encoder.\n\n"
            "Solo disponible sin receta cargada."
        )

    def _reject_manual_by_recipe(self) -> None:
        self.ui.show_warning(
            "Modo Manual",
            "No se puede activar el modo manual\n"
            "con una receta cargada.\n\n"
            "Detenga la receta primero."
        )

    def _reject_jog(self) -> None:
        self.ui.show_warning(
            "JOG",
            "El simulador no aceptó el movimiento en el estado actual.\n"
            "Verifica que el modo manual esté activo."
        )

    def _reject_jog_pulse(self) -> None:
        self.ui.show_warning(
            "JOG",
            "El simulador no aceptó el pulso.\n"
            "Verifica que el modo manual esté activo y la máquina esté en reposo."
        )

    # ---------------------------------------------------------
    # Conexión / desconexión
    # ---------------------------------------------------------
    def toggle_connect(self) -> None:
        if self.use_simulator:
            self._toggle_connect_simulator()
            return

        self._toggle_connect_serial()

    def _toggle_connect_simulator(self) -> None:
        if self.state.connected:
            self.machine.disconnect()
            self.sync_connection(False, "Simulador")
            return

        ok = self.machine.connect()
        if ok:
            self.sync_connection(True, "Simulador")
        else:
            self.sync_connection(False, "No se pudo iniciar el simulador")

    def _toggle_connect_serial(self) -> None:
        if self.state.connected:
            self.serial.disconnect()
            return

        port = (self.ui.get_selected_port() or "").strip()
        if not port:
            self.ui.show_warning("Aviso", "Selecciona un puerto")
            return

        self.ui.save_selected_port(port)

        threading.Thread(
            target=self.serial.connect,
            args=(port,),
            daemon=True,
        ).start()

    def sync_connection(self, connected: bool, info: str | None = None) -> None:
        self.state.connected = connected

        if not connected:
            self.state.manual_activo = False
            self.state.jog_active = False
            self.ui.set_manual_mode_active(False)
            self.ui.set_jog_stopped()
            self.ui.set_jog_status("◉ PARADO", TEXT_SECONDARY)

            self.ui.set_connection_indicator("● DESCONECTADO", ACCENT_RED)
            self.ui.set_connect_button_state(
                "CONECTAR",
                ACCENT_GREEN,
                "#00CC6A",
                BG_DARK,
            )
            self.ui.set_alert(
                "Desconectado — Reconecte el controlador"
                if not self.use_simulator
                else "Desconectado — Simulador inactivo",
                ACCENT_RED,
            )
            self.ui.log(f"Desconectado: {info or 'sin detalle'}", "error")
            return

        label = f"● {info}" if info else ("● SIMULADOR" if self.use_simulator else "● CONECTADO")
        self.ui.set_connection_indicator(label, ACCENT_GREEN)
        self.ui.set_connect_button_state(
            "DESCONECTAR",
            ACCENT_RED,
            "#CC2222",
            TEXT_PRIMARY,
        )
        self.ui.log(f"Conectado a {info or 'controlador'}", "ok")

    # ---------------------------------------------------------
    # Polling simulador
    # ---------------------------------------------------------
    def poll_machine(self) -> None:
        if not self.use_simulator:
            return

        self.machine.update()
        snapshot = self.machine.get_snapshot()
        self.apply_machine_snapshot(snapshot)

    def apply_machine_snapshot(self, snapshot) -> None:
        self.state.connected = snapshot.connected

        self.ui.set_machine_state(snapshot.state)
        self.ui.set_recipe_name(snapshot.recipe_name or "--")
        self.ui.set_section("--")
        self.ui.set_total_sections("--")
        self.ui.set_layer(str(snapshot.current_layer) if snapshot.current_layer else "--")
        self.ui.set_total_layers("--")
        self.ui.set_target_turns(f"{snapshot.target_turns:.1f}" if snapshot.target_turns else "--")
        self.ui.set_current_turns(f"{snapshot.current_turns:.1f}")
        self.ui.set_rpm(f"{snapshot.rpm:.0f}")
        self.ui.set_position(f"{snapshot.position_mm / 10.0:.2f}cm")
        self.ui.set_brake_status("--")
        self.ui.set_motor_status("⚡ MOTOR" if snapshot.is_running() else "⏹ parado")
        self.ui.set_jog_position(f"Pos: {snapshot.position_mm / 10.0:.2f}cm")

        self.sync_manual_from_backend(snapshot.manual_mode)

        if snapshot.connected:
            self.ui.set_connection_indicator("● SIMULADOR", ACCENT_GREEN)
            self.ui.set_connect_button_state(
                "DESCONECTAR",
                ACCENT_RED,
                "#CC2222",
                TEXT_PRIMARY,
            )
        else:
            self.ui.set_connection_indicator("● DESCONECTADO", ACCENT_RED)
            self.ui.set_connect_button_state(
                "CONECTAR",
                ACCENT_GREEN,
                "#00CC6A",
                BG_DARK,
            )

        if snapshot.has_error():
            self.ui.set_alert(
                snapshot.alarm_message or "Error de simulación",
                ACCENT_RED,
            )
        elif snapshot.state == "HOMING":
            self.ui.set_alert("⌂ HOMING en progreso...", ACCENT_ORANGE)
        elif snapshot.state == "PAUSED":
            self.ui.set_alert("⏸ PAUSADO", ACCENT_YELLOW)
        elif snapshot.state == "RUNNING":
            self.ui.set_alert("● SIMULANDO BOBINADO", ACCENT_GREEN)
        elif snapshot.manual_mode:
            self.ui.set_alert("⚙ MODO MANUAL", ACCENT_ORANGE)
        elif snapshot.connected:
            self.ui.set_alert("Sistema listo — Simulador activo", TEXT_SECONDARY)
        else:
            self.ui.set_alert("Desconectado — Simulador inactivo", ACCENT_RED)

    # ---------------------------------------------------------
    # Comandos principales
    # ---------------------------------------------------------
    def cmd_start(self) -> None:
        if not self._ensure_connected():
            return

        if self.use_simulator:
            target_turns = 10.0
            recipe_name = self.ui.get_run_recipe_name().strip() or "RECETA_SIMULADA"

            ok = self.machine.start_job(
                target_turns=target_turns,
                recipe_name=recipe_name,
            )

            if ok:
                self.ui.log(
                    f"START(sim) → receta={recipe_name}, meta={target_turns}",
                    "ok",
                )
            else:
                self.ui.log("START(sim) rechazado", "error")
                self.ui.show_warning(
                    "Aviso",
                    "El simulador no aceptó START en el estado actual.",
                )
            return

        resp = self.serial.send("STARTMAQ")
        self.ui.log(f"START → {resp}", "ok")

    def cmd_stop(self) -> None:
        if not self._ensure_connected():
            return

        if self.use_simulator:
            ok = self.machine.stop()
            if ok:
                self.ui.log("STOP(sim) → OK", "error")
            else:
                self.ui.log("STOP(sim) rechazado", "error")
                self.ui.show_warning(
                    "Aviso",
                    "El simulador no aceptó STOP en el estado actual.",
                )
            return

        resp = self.serial.send("STOPMAQ")
        self.ui.log(f"STOP → {resp}", "error")

    def cmd_reset(self) -> None:
        if not self._ensure_connected():
            return

        if not self.ui.confirm("Confirmar", "¿Resetear contador de vueltas?"):
            return

        if self.use_simulator:
            ok = self.machine.reset()
            if ok:
                self.ui.log("RESET(sim) → OK", "ok")
            else:
                self.ui.log("RESET(sim) rechazado", "error")
                self.ui.show_warning(
                    "Aviso",
                    "El simulador no aceptó RESET en el estado actual.",
                )
            return

        resp = self.serial.send("RESET")
        self.ui.log(f"RESET → {resp}", "ok")

    def cmd_homing(self) -> None:
        if not self._ensure_connected():
            return

        if not self.ui.confirm(
            "Confirmar Homing",
            "¿Ejecutar homing?\n"
            "El husillo buscará el punto cero."
        ):
            return

        if self.use_simulator:
            ok = self.machine.home()
            if ok:
                self.ui.log("HOMING(sim) → OK", "info")
            else:
                self.ui.log("HOMING(sim) rechazado", "error")
                self.ui.show_warning(
                    "Aviso",
                    "El simulador no aceptó HOMING en el estado actual.",
                )
            return

        resp = self.serial.send("HOMING")
        self.ui.log(f"HOMING → {resp}", "info")

    # ---------------------------------------------------------
    # Modo manual
    # ---------------------------------------------------------
    def cmd_manual_toggle(self) -> None:
        if not self._ensure_connected("No hay conexión"):
            return

        if not self.state.manual_activo:
            if self._recipe_loaded_for_manual():
                self._reject_manual_by_recipe()
                return

            if not self._manual_activation_confirmed():
                return

        if self.use_simulator:
            self._cmd_manual_toggle_simulator()
            return

        self._cmd_manual_toggle_serial()

    def _cmd_manual_toggle_simulator(self) -> None:
        if not self.state.manual_activo:
            ok = self.machine.set_manual_mode(True)
            if ok:
                self.state.manual_activo = True
                self.ui.log("MANUAL ON(sim) → OK", "manual")
                self.ui.set_manual_mode_active(True)
                self.ui.set_alert(
                    "⚙ MODO MANUAL — Simulador activo",
                    ACCENT_ORANGE,
                )
            else:
                self.ui.log("MANUAL ON(sim) rechazado", "error")
                self.ui.show_warning(
                    "Modo Manual",
                    "El simulador no aceptó activar modo manual en el estado actual."
                )
            return

        ok = self.machine.set_manual_mode(False)
        if ok:
            self.state.manual_activo = False
            self.ui.log("MANUAL OFF(sim) → OK", "manual")
            self.ui.set_manual_mode_active(False)
            self.ui.set_alert(
                "Sistema listo — Simulador activo",
                TEXT_SECONDARY,
            )
        else:
            self.ui.log("MANUAL OFF(sim) rechazado", "error")
            self.ui.show_warning(
                "Modo Manual",
                "El simulador no aceptó desactivar modo manual en el estado actual."
            )

    def _cmd_manual_toggle_serial(self) -> None:
        if not self.state.manual_activo:
            resp = self.serial.send("MANUAL_ON")
            self.ui.log(f"MANUAL ON → {resp}", "manual")
            self.state.manual_activo = True
            self.ui.set_manual_mode_active(True)
            self.ui.set_alert(
                "⚙ MODO MANUAL — Pise el PEDAL para girar",
                ACCENT_ORANGE,
            )
            return

        resp = self.serial.send("MANUAL_OFF")
        self.ui.log(f"MANUAL OFF → {resp}", "manual")
        self.state.manual_activo = False
        self.ui.set_manual_mode_active(False)
        self.ui.set_alert(
            "Sistema listo — Cargue una receta",
            TEXT_SECONDARY,
        )

    # ---------------------------------------------------------
    # JOG por pulso
    # ---------------------------------------------------------
    def jog_pulse(self, direction: str) -> None:
        if not self._ensure_connected("No hay conexión"):
            return

        mm = self.ui.get_jog_step_mm()
        pasos = self.ui.mm_to_steps(mm)
        lbl = (f"{mm:.1f}".rstrip("0").rstrip(".") or "0") + "mm"
        sym = "◀" if direction == "left" else "▶"

        self.ui.set_jog_status(f"{sym} {lbl}", ACCENT_YELLOW)

        if self.use_simulator:
            ok = self.machine.jog_step(direction, mm)

            if ok:
                self.ui.log(
                    f"JOG(sim) {direction} {lbl} ({pasos}p) → OK",
                    "info",
                )
                self.ui.after(
                    150,
                    lambda: self.ui.set_jog_status("◉ PARADO", TEXT_SECONDARY),
                )
            else:
                self.ui.log(
                    f"JOG(sim) {direction} {lbl} ({pasos}p) rechazado",
                    "error",
                )
                self.ui.set_jog_status("✗ RECHAZADO", ACCENT_RED)
                self._reject_jog_pulse()
                self.ui.after(
                    500,
                    lambda: self.ui.set_jog_status("◉ PARADO", TEXT_SECONDARY),
                )
            return

        cmd = f"JOGMM:{direction.upper()}:{pasos}"

        def _worker():
            resp = self.serial.send(cmd)
            self.ui.log(
                f"JOG {direction} {lbl} ({pasos}p): {resp}",
                "info",
            )
            if resp and any("ERR" in x for x in resp):
                self.ui.after(
                    0,
                    lambda r=resp: self.ui.set_jog_status(
                        f"✗ {r[0][:20]}",
                        ACCENT_RED,
                    ),
                )
            else:
                self.ui.after(
                    0,
                    lambda: self.ui.set_jog_status("◉ PARADO", TEXT_SECONDARY),
                )

        threading.Thread(target=_worker, daemon=True).start()

    # ---------------------------------------------------------
    # JOG continuo
    # ---------------------------------------------------------
    def on_jog_left_press_ui(self) -> None:
        if not self._ensure_connected("No hay conexión"):
            return

        self.ui.set_jog_running("left")
        self.jog_start("left")

    def on_jog_left_release_ui(self) -> None:
        self.ui.set_jog_stopped()
        self.jog_stop()

    def on_jog_right_press_ui(self) -> None:
        if not self._ensure_connected("No hay conexión"):
            return

        self.ui.set_jog_running("right")
        self.jog_start("right")

    def on_jog_right_release_ui(self) -> None:
        self.ui.set_jog_stopped()
        self.jog_stop()

    def jog_start(self, direction: str) -> None:
        if not self._ensure_connected("No hay conexión"):
            return

        self.state.jog_active = True
        self.state.jog_direction = direction

        self.ui.set_jog_running(direction)
        self.ui.set_jog_status("◀◀" if direction == "left" else "▶▶", ACCENT_BLUE)

        if self.use_simulator:
            ok = self.machine.jog_left() if direction == "left" else self.machine.jog_right()

            if not ok:
                self.state.jog_active = False
                self.ui.set_jog_stopped()
                self.ui.set_jog_status("◉ PARADO", TEXT_SECONDARY)
                self.ui.log(f"JOG(sim) {direction} rechazado", "error")
                self._reject_jog()
            else:
                self.ui.log(f"JOG(sim) {direction} → OK", "info")
            return

        self.serial.send("JOG:LEFT" if direction == "left" else "JOG:RIGHT")
        threading.Thread(target=self._jog_loop, daemon=True).start()

    def _jog_loop(self) -> None:
        while self.state.jog_active:
            cmd = "JOG:LEFT" if self.state.jog_direction == "left" else "JOG:RIGHT"
            self.serial.send(cmd)
            time.sleep(0.1)

    def jog_stop(self) -> None:
        self.state.jog_active = False
        self.ui.set_jog_stopped()
        self.ui.set_jog_status("◉ PARADO", TEXT_SECONDARY)

        if self.use_simulator:
            ok = self.machine.stop_jog()
            if ok:
                self.ui.log("JOG(sim) STOP → OK", "info")
            else:
                self.ui.log("JOG(sim) STOP rechazado", "error")
            return

        self.serial.send("JOG:STOP")

    # ---------------------------------------------------------
    # Soporte para sync externo
    # ---------------------------------------------------------
    def sync_manual_from_backend(self, is_manual: bool) -> None:
        self.state.manual_activo = is_manual
        self.ui.set_manual_mode_active(is_manual)