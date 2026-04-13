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

    Segunda versión:
    - envía comandos básicos
    - mantiene snapshot local
    - puede sincronizarse desde STATUS procesado por la app
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
        """
        En serial real no hacemos polling activo aquí.
        El estado llega por callbacks externos.
        """
        return

    def get_snapshot(self) -> SerialMachineSnapshot:
        return self.snapshot

    # ---------------------------------------------------------
    # Sync desde STATUS
    # ---------------------------------------------------------
    def apply_status_ui_data(self, status) -> None:
        """
        Recibe el objeto producido por StatusService.parse_status_ui_data(...)
        y actualiza el snapshot local del backend serial.
        """
        if status is None:
            return

        self.snapshot.connected = True

        self.snapshot.state = self._normalize_state(status.estado_texto)
        self.snapshot.recipe_name = status.recipe_name or self.snapshot.recipe_name
        self.snapshot.manual_mode = bool(status.is_manual)

        self.snapshot.current_layer = self._safe_int(status.layer_display, default=0)
        self.snapshot.target_turns = self._safe_float(status.target_turns, default=0.0)
        self.snapshot.current_turns = self._safe_float(status.current_turns, default=0.0)
        self.snapshot.rpm = self._safe_float(status.rpm, default=0.0)
        self.snapshot.position_mm = self._position_cm_text_to_mm(status.position_cm)

        if status.alert_color:
            if "ERR" in self.snapshot.state.upper() or "ERROR" in self.snapshot.state.upper():
                self.snapshot.alarm_message = status.alert_text or self.snapshot.alarm_message
            elif status.estado_num in ("5",):
                # pausa por derivación / rojo, no necesariamente error fatal
                self.snapshot.alarm_message = ""
            else:
                self.snapshot.alarm_message = ""

        if status.estado_num in ("13",):
            self.snapshot.state = "MANUAL"
        elif status.estado_num in ("12",):
            self.snapshot.state = "HOMING"
        elif status.estado_num in ("9",):
            self.snapshot.state = "JOG"
        elif status.estado_num in ("1",):
            self.snapshot.state = "RUNNING"
        elif status.estado_num in ("3", "5", "7", "11"):
            self.snapshot.state = "PAUSED"
        elif status.estado_num in ("0", "4", "6", "8", "10"):
            if not self.snapshot.manual_mode:
                self.snapshot.state = "IDLE"

        if self.snapshot.manual_mode:
            self._jogging_direction = None

    def mark_disconnected(self) -> None:
        self.snapshot.connected = False
        self.snapshot.manual_mode = False
        self.snapshot.state = "IDLE"
        self.snapshot.rpm = 0.0
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

        # La conexión real la maneja SerialManager externamente.
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

    def _normalize_state(self, state_text: str) -> str:
        text = str(state_text or "").strip().upper()

        mapping = {
            "IDLE": "IDLE",
            "RUNNING": "RUNNING",
            "HOMING": "HOMING",
            "MANUAL": "MANUAL",
            "JOG": "JOG",
            "PAUSED": "PAUSED",
        }

        if text in mapping:
            return mapping[text]

        if "HOMING" in text:
            return "HOMING"
        if "MANUAL" in text:
            return "MANUAL"
        if "JOG" in text:
            return "JOG"
        if "RUN" in text or "BOBIN" in text:
            return "RUNNING"
        if "PAUS" in text or "FIN" in text:
            return "PAUSED"
        if not text:
            return "IDLE"
        return text

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