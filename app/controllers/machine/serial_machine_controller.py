from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SerialMachineSnapshot:
    connected: bool = False
    state: str = "IDLE"
    recipe_name: str = ""
    current_layer: int = 0
    target_turns: float = 0.0
    current_turns: float = 0.0
    rpm: float = 0.0
    position_mm: float = 0.0
    manual_mode: bool = False
    alarm_message: str = ""

    def is_running(self) -> bool:
        return self.state in ("RUNNING", "RUN", "BOBINANDO")

    def has_error(self) -> bool:
        return bool(self.alarm_message)


class SerialMachineController:
    """
    Adaptador para trabajar con el controlador real vía SerialManager.

    Esta versión:
    - envía comandos básicos
    - mantiene snapshot local
    - sincroniza mejor el snapshot desde STATUS procesado por la app
    """

    def __init__(self, cfg: dict, serial_manager=None):
        self.cfg = cfg
        self.serial = serial_manager
        self.snapshot = SerialMachineSnapshot()
        self._jogging_direction: Optional[str] = None

    # ---------------------------------------------------------
    # Infra básica
    # ---------------------------------------------------------
    def attach_serial_manager(self, serial_manager) -> None:
        self.serial = serial_manager

    def update(self) -> None:
        return

    def get_snapshot(self) -> SerialMachineSnapshot:
        return self.snapshot

    # ---------------------------------------------------------
    # Sync desde STATUS
    # ---------------------------------------------------------
    def apply_status_ui_data(self, status) -> None:
        if status is None:
            return

        self.snapshot.connected = True

        # Datos base
        self.snapshot.recipe_name = status.recipe_name or self.snapshot.recipe_name
        self.snapshot.manual_mode = bool(status.is_manual)
        self.snapshot.current_layer = self._safe_int(status.layer_display, default=0)
        self.snapshot.target_turns = self._safe_float(status.target_turns, default=0.0)
        self.snapshot.current_turns = self._safe_float(status.current_turns, default=0.0)
        self.snapshot.rpm = self._safe_float(status.rpm, default=0.0)
        self.snapshot.position_mm = self._position_cm_text_to_mm(status.position_cm)

        # Estado principal guiado por el código de estado del protocolo
        self.snapshot.state = self._map_state_from_status(status)

        # Dirección de jog: si ya no está en JOG, la limpiamos
        if self.snapshot.state != "JOG":
            self._jogging_direction = None

        # Gestión de alarmas
        self.snapshot.alarm_message = self._map_alarm_message(status)

    def mark_disconnected(self) -> None:
        self.snapshot.connected = False
        self.snapshot.manual_mode = False
        self.snapshot.state = "IDLE"
        self.snapshot.rpm = 0.0
        self.snapshot.alarm_message = ""
        self._jogging_direction = None

    # ---------------------------------------------------------
    # Conexión
    # ---------------------------------------------------------
    def connect(self, port: str | None = None) -> bool:
        if self.serial is None:
            return False

        selected_port = (port or self.cfg.get("puerto") or "").strip()
        if not selected_port:
            self.snapshot.connected = False
            self.snapshot.alarm_message = "Puerto no especificado"
            return False

        self.snapshot.connected = True
        self.snapshot.alarm_message = ""
        return True

    def disconnect(self) -> bool:
        self.mark_disconnected()
        return True

    # ---------------------------------------------------------
    # Helpers internos
    # ---------------------------------------------------------
    def _send(self, cmd: str):
        if self.serial is None:
            self.snapshot.alarm_message = "SerialManager no disponible"
            return None
        return self.serial.send(cmd)

    def _response_has_error(self, response) -> bool:
        if not response:
            return False
        try:
            return any("ERR" in str(x) for x in response)
        except TypeError:
            return "ERR" in str(response)

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            if value in ("", None, "--"):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default: int = 0) -> int:
        try:
            if value in ("", None, "--"):
                return default
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _position_cm_text_to_mm(self, value) -> float:
        if value in ("", None, "--"):
            return 0.0

        raw = str(value).strip().lower().replace("cm", "").strip()
        try:
            return float(raw) * 10.0
        except ValueError:
            return 0.0

    def _map_state_from_status(self, status) -> str:
        estado_num = str(getattr(status, "estado_num", "") or "")
        estado_texto = str(getattr(status, "estado_texto", "") or "").upper()

        state_by_num = {
            "0": "IDLE",
            "1": "RUNNING",
            "2": "RUNNING",   # prefreno, sigue en trabajo
            "3": "PAUSED",
            "4": "IDLE",      # desbloqueado esperando pedal
            "5": "PAUSED",
            "6": "IDLE",
            "7": "PAUSED",
            "8": "IDLE",      # bobina completa
            "9": "JOG",
            "10": "RUNNING",  # barrera con pedal
            "11": "PAUSED",
            "12": "HOMING",
            "13": "MANUAL",
        }

        if estado_num in state_by_num:
            return state_by_num[estado_num]

        # Fallback por texto, por si cambia algo del protocolo
        if "HOMING" in estado_texto:
            return "HOMING"
        if "MANUAL" in estado_texto:
            return "MANUAL"
        if "JOG" in estado_texto:
            return "JOG"
        if "RUN" in estado_texto or "BOBIN" in estado_texto:
            return "RUNNING"
        if "PAUS" in estado_texto or "FIN" in estado_texto:
            return "PAUSED"

        return "IDLE"

    def _map_alarm_message(self, status) -> str:
        estado_num = str(getattr(status, "estado_num", "") or "")
        alert_text = str(getattr(status, "alert_text", "") or "").strip()

        # Estados que no consideramos error, aunque muestren alerta visual
        non_error_states = {"0", "1", "2", "3", "4", "6", "7", "8", "9", "10", "11", "12", "13"}
        if estado_num in non_error_states:
            return ""

        # Si en algún momento llegaran estados realmente anómalos,
        # podemos conservar la alerta como mensaje de alarma.
        if alert_text and estado_num not in {"5"}:
            return alert_text

        return ""

    # ---------------------------------------------------------
    # Control principal
    # ---------------------------------------------------------
    def start_job(self, target_turns: float = 0.0, recipe_name: str = "") -> bool:
        response = self._send("STARTMAQ")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.state = "RUNNING"
        self.snapshot.target_turns = float(target_turns or 0.0)
        self.snapshot.recipe_name = recipe_name or self.snapshot.recipe_name
        self.snapshot.alarm_message = ""
        return True

    def stop(self) -> bool:
        response = self._send("STOPMAQ")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.state = "PAUSED"
        self._jogging_direction = None
        self.snapshot.alarm_message = ""
        return True

    def reset(self) -> bool:
        response = self._send("RESET")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.current_turns = 0.0
        self.snapshot.target_turns = 0.0
        self.snapshot.current_layer = 0
        self.snapshot.position_mm = 0.0
        self.snapshot.state = "IDLE"
        self.snapshot.alarm_message = ""
        return True

    def home(self) -> bool:
        response = self._send("HOMING")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.state = "HOMING"
        self.snapshot.alarm_message = ""
        return True

    # ---------------------------------------------------------
    # Manual
    # ---------------------------------------------------------
    def set_manual_mode(self, enabled: bool) -> bool:
        cmd = "MANUAL_ON" if enabled else "MANUAL_OFF"
        response = self._send(cmd)

        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.manual_mode = enabled
        self.snapshot.state = "MANUAL" if enabled else "IDLE"
        self.snapshot.alarm_message = ""
        return True

    # ---------------------------------------------------------
    # JOG continuo
    # ---------------------------------------------------------
    def jog_left(self) -> bool:
        response = self._send("JOG:LEFT")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self._jogging_direction = "left"
        self.snapshot.state = "JOG"
        self.snapshot.alarm_message = ""
        return True

    def jog_right(self) -> bool:
        response = self._send("JOG:RIGHT")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self._jogging_direction = "right"
        self.snapshot.state = "JOG"
        self.snapshot.alarm_message = ""
        return True

    def stop_jog(self) -> bool:
        response = self._send("JOG:STOP")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self._jogging_direction = None
        self.snapshot.state = "MANUAL" if self.snapshot.manual_mode else "IDLE"
        self.snapshot.alarm_message = ""
        return True

    # ---------------------------------------------------------
    # JOG por pulso
    # ---------------------------------------------------------
    def jog_step(self, direction: str, mm: float) -> bool:
        pasos = max(1, int(round(float(mm) * 160.0)))
        cmd = f"JOGMM:{direction.upper()}:{pasos}"
        response = self._send(cmd)

        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.state = "JOG"
        self.snapshot.alarm_message = ""
        return True