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
    position_steps: int = 0
    encoder_count: int = 0

    manual_mode: bool = False
    sync_enabled: bool = False

    esp_mm: float = 1.0
    gear: int = 6250
    jog_delay_us: int = 600

    limit_min: bool = False
    limit_max: bool = False
    can_move_left: bool = True
    can_move_right: bool = True
    block_reason: int = 0

    alarm_message: str = ""

    def is_running(self) -> bool:
        return self.state in ("RUNNING", "RUN", "BOBINANDO", "SYNC")

    def has_error(self) -> bool:
        return bool(self.alarm_message)


class SerialMachineController:
    """
    Adaptador para trabajar con el controlador real vía SerialManager.

    Protocolo STM32 validado:
    - PING
    - STATUS
    - LIMITS
    - HOMING
    - SET_ESP_X100:<valor>
    - SET_JOG_DELAY_US:<valor>
    - JOGMM_X100:RIGHT:<mm_x100>
    - JOGMM_X100:LEFT:<mm_x100>
    - SYNC_ON
    - SYNC_OFF
    - STOP

    Importante:
    - El modo con husillo usa SYNC_ON.
    - El modo solo mandril NO usa SYNC_ON, por lo que no mueve el husillo.
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
    # Sync desde STATUS procesado por StatusService
    # ---------------------------------------------------------
    def apply_status_ui_data(self, status) -> None:
        if status is None:
            return

        self.snapshot.connected = True

        self.snapshot.recipe_name = status.recipe_name or self.snapshot.recipe_name
        self.snapshot.manual_mode = bool(status.is_manual)

        self.snapshot.current_layer = self._safe_int(status.layer_display, default=0)
        self.snapshot.target_turns = self._safe_float(status.target_turns, default=0.0)
        self.snapshot.current_turns = self._safe_float(
            getattr(status, "turns_display", None) or status.current_turns,
            default=0.0,
        )
        self.snapshot.rpm = self._safe_float(status.rpm, default=0.0)

        self.snapshot.position_mm = self._status_position_to_mm(status)
        self.snapshot.position_steps = self._safe_int(
            getattr(status, "position_steps", ""),
            default=self.snapshot.position_steps,
        )
        self.snapshot.encoder_count = self._safe_int(
            getattr(status, "encoder_count", ""),
            default=self.snapshot.encoder_count,
        )

        self.snapshot.sync_enabled = str(getattr(status, "sync", "0")) == "1"
        self.snapshot.esp_mm = self._safe_float(
            getattr(status, "esp_mm", ""),
            default=self.snapshot.esp_mm,
        )
        self.snapshot.gear = self._safe_int(
            getattr(status, "gear", ""),
            default=self.snapshot.gear,
        )
        self.snapshot.jog_delay_us = self._safe_int(
            getattr(status, "jog_delay_us", ""),
            default=self.snapshot.jog_delay_us,
        )

        self.snapshot.limit_min = str(getattr(status, "lim_min", "0")) == "1"
        self.snapshot.limit_max = str(getattr(status, "lim_max", "0")) == "1"
        self.snapshot.can_move_left = str(getattr(status, "can_left", "1")) == "1"
        self.snapshot.can_move_right = str(getattr(status, "can_right", "1")) == "1"
        self.snapshot.block_reason = self._safe_int(
            getattr(status, "block", "0"),
            default=0,
        )

        self.snapshot.state = self._map_state_from_status(status)

        if self.snapshot.state not in ("JOG", "JOG_LEFT", "JOG_RIGHT"):
            self._jogging_direction = None

        self.snapshot.alarm_message = self._map_alarm_message(status)

    def mark_disconnected(self) -> None:
        self.snapshot.connected = False
        self.snapshot.manual_mode = False
        self.snapshot.sync_enabled = False
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
            items = response
            return any(("ERR" in str(x) or "CMD?" in str(x)) for x in items)
        except TypeError:
            text = str(response)
            return "ERR" in text or "CMD?" in text

    def _response_contains(self, response, text: str) -> bool:
        if not response:
            return False

        try:
            return any(text in str(x) for x in response)
        except TypeError:
            return text in str(response)

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

    def _mm_to_x100(self, mm: float) -> int:
        return max(1, int(round(float(mm) * 100.0)))

    def _status_position_to_mm(self, status) -> float:
        # Nuevo formato STM32
        pos_mm = getattr(status, "position_mm", "")
        if pos_mm not in ("", None, "--"):
            return self._safe_float(pos_mm, default=self.snapshot.position_mm)

        pos_mm_x100 = getattr(status, "position_mm_x100", "")
        if pos_mm_x100 not in ("", None, "--"):
            return self._safe_float(pos_mm_x100, default=0.0) / 100.0

        # Fallback legacy
        return self._position_text_to_mm(getattr(status, "position_cm", ""))

    def _position_text_to_mm(self, value) -> float:
        if value in ("", None, "--"):
            return 0.0

        raw = str(value).strip().lower()

        try:
            if raw.endswith("mm"):
                return float(raw.replace("mm", "").strip())

            if raw.endswith("cm"):
                return float(raw.replace("cm", "").strip()) * 10.0

            return float(raw)
        except ValueError:
            return 0.0

    def _map_state_from_status(self, status) -> str:
        estado_num = str(getattr(status, "estado_num", "") or "")
        estado_texto = str(getattr(status, "estado_texto", "") or "").upper()
        machine_state = str(getattr(status, "state_machine", "") or "").upper()

        # Nuevo formato STM32
        stm32_states = {
            "IDLE": "IDLE",
            "MANUAL": "MANUAL",
            "JOG_LEFT": "JOG_LEFT",
            "JOG_RIGHT": "JOG_RIGHT",
            "STOPPED": "STOPPED",
            "SYNC": "SYNC",
            "LIMIT_BLOCKED": "LIMIT_BLOCKED",
            "HOMING": "HOMING",
            "HOME_OK": "HOME_OK",
            "HOMING_ERROR": "ERROR",
            "UNKNOWN": "IDLE",
        }

        if machine_state in stm32_states:
            return stm32_states[machine_state]

        if estado_num in stm32_states:
            return stm32_states[estado_num]

        # Formato legacy
        state_by_num = {
            "0": "IDLE",
            "1": "RUNNING",
            "2": "RUNNING",
            "3": "PAUSED",
            "4": "IDLE",
            "5": "PAUSED",
            "6": "IDLE",
            "7": "PAUSED",
            "8": "IDLE",
            "9": "JOG",
            "10": "RUNNING",
            "11": "PAUSED",
            "12": "HOMING",
            "13": "MANUAL",
        }

        if estado_num in state_by_num:
            return state_by_num[estado_num]

        if "HOME OK" in estado_texto:
            return "HOME_OK"
        if "HOMING" in estado_texto:
            return "HOMING"
        if "MANUAL" in estado_texto:
            return "MANUAL"
        if "JOG" in estado_texto:
            return "JOG"
        if "SYNC" in estado_texto:
            return "SYNC"
        if "BLOQUEADO" in estado_texto or "LIMIT" in estado_texto:
            return "LIMIT_BLOCKED"
        if "RUN" in estado_texto or "BOBIN" in estado_texto:
            return "RUNNING"
        if "PAUS" in estado_texto or "FIN" in estado_texto:
            return "PAUSED"

        return "IDLE"

    def _map_alarm_message(self, status) -> str:
        state = str(getattr(status, "state_machine", "") or "").upper()
        estado_num = str(getattr(status, "estado_num", "") or "")
        alert_text = str(getattr(status, "alert_text", "") or "").strip()
        block = str(getattr(status, "block", "0") or "0")

        if state == "HOMING_ERROR":
            return alert_text or "Error durante homing"

        if state == "LIMIT_BLOCKED" or block in ("1", "2"):
            return alert_text or "Movimiento bloqueado por límite"

        # Estados legacy que no son error
        non_error_states = {
            "0", "1", "2", "3", "4", "6", "7", "8",
            "9", "10", "11", "12", "13",
        }
        if estado_num in non_error_states:
            return ""

        if alert_text and estado_num not in {"5"}:
            return alert_text

        return ""

    def _execute_ok(self, cmd: str, error_state: Optional[str] = None):
        response = self._send(cmd)

        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            if error_state:
                self.snapshot.state = error_state
            return False, response

        self.snapshot.alarm_message = ""
        return True, response

    # ---------------------------------------------------------
    # Comandos de diagnóstico / estado
    # ---------------------------------------------------------
    def ping(self) -> bool:
        response = self._send("PING")
        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            return False

        self.snapshot.connected = True
        return True

    def request_status(self):
        return self._send("STATUS")

    def request_limits(self):
        return self._send("LIMITS")

    # Alias cortos por comodidad
    def status(self):
        return self.request_status()

    def limits(self):
        return self.request_limits()

    # ---------------------------------------------------------
    # Control principal
    # ---------------------------------------------------------
    def start_job(
        self,
        target_turns: float = 0.0,
        recipe_name: str = "",
        use_husillo: bool = False,
        esp_mm: Optional[float] = None,
        esp_x100: Optional[int] = None,
    ) -> bool:
        """
        No fuerza el uso del husillo.

        use_husillo=False:
            modo solo mandril / proceso sin avance automático.
            Se asegura SYNC_OFF.

        use_husillo=True:
            configura espesor si se proporciona y activa SYNC_ON.
        """
        self.snapshot.target_turns = float(target_turns or 0.0)
        self.snapshot.recipe_name = recipe_name or self.snapshot.recipe_name

        if use_husillo:
            if esp_x100 is not None:
                if not self.set_esp_x100(esp_x100):
                    return False
            elif esp_mm is not None:
                if not self.set_esp_mm(esp_mm):
                    return False

            return self.sync_on()

        ok, _ = self._execute_ok("SYNC_OFF")
        if not ok:
            return False

        self.snapshot.sync_enabled = False
        self.snapshot.state = "RUNNING"
        return True

    def stop(self) -> bool:
        ok, _ = self._execute_ok("STOP")
        if not ok:
            return False

        self.snapshot.state = "STOPPED"
        self.snapshot.sync_enabled = False
        self._jogging_direction = None
        return True

    def reset(self) -> bool:
        ok, _ = self._execute_ok("SYNC_RESET")
        if not ok:
            return False

        self.snapshot.current_turns = 0.0
        self.snapshot.target_turns = 0.0
        self.snapshot.current_layer = 0
        self.snapshot.position_mm = 0.0
        self.snapshot.position_steps = 0
        self.snapshot.encoder_count = 0
        self.snapshot.state = "IDLE"
        self.snapshot.sync_enabled = False
        return True

    def home(self) -> bool:
        response = self._send("HOMING")

        if self._response_has_error(response):
            self.snapshot.alarm_message = str(response)
            self.snapshot.state = "ERROR"
            return False

        if self._response_contains(response, "OK:HOMING:DONE"):
            self.snapshot.state = "HOME_OK"
            self.snapshot.position_mm = 0.0
            self.snapshot.position_steps = 0
            self.snapshot.encoder_count = 0
        else:
            self.snapshot.state = "HOMING"

        self.snapshot.alarm_message = ""
        return True

    # ---------------------------------------------------------
    # Configuración STM32
    # ---------------------------------------------------------
    def set_esp_x100(self, esp_x100: int) -> bool:
        esp_x100 = int(esp_x100)
        ok, _ = self._execute_ok(f"SET_ESP_X100:{esp_x100}")
        if not ok:
            return False

        self.snapshot.esp_mm = esp_x100 / 100.0
        return True

    def set_esp_mm(self, esp_mm: float) -> bool:
        return self.set_esp_x100(self._mm_to_x100(esp_mm))

    def set_jog_delay_us(self, delay_us: int) -> bool:
        delay_us = int(delay_us)
        ok, _ = self._execute_ok(f"SET_JOG_DELAY_US:{delay_us}")
        if not ok:
            return False

        self.snapshot.jog_delay_us = delay_us
        return True

    def set_gear(self, gear: int) -> bool:
        gear = int(gear)
        ok, _ = self._execute_ok(f"SET_GEAR:{gear}")
        if not ok:
            return False

        self.snapshot.gear = gear
        return True

    def set_husillo_x100(self, husillo_x100: int) -> bool:
        husillo_x100 = int(husillo_x100)
        ok, _ = self._execute_ok(f"SET_HUSILLO_X100:{husillo_x100}")
        return ok

    def set_steps_rev(self, steps_rev: int) -> bool:
        steps_rev = int(steps_rev)
        ok, _ = self._execute_ok(f"SET_STEPS_REV:{steps_rev}")
        return ok

    # ---------------------------------------------------------
    # SYNC encoder -> husillo
    # ---------------------------------------------------------
    def sync_on(self) -> bool:
        ok, _ = self._execute_ok("SYNC_ON")
        if not ok:
            return False

        self.snapshot.sync_enabled = True
        self.snapshot.state = "SYNC"
        return True

    def sync_off(self) -> bool:
        ok, _ = self._execute_ok("SYNC_OFF")
        if not ok:
            return False

        self.snapshot.sync_enabled = False
        self.snapshot.state = "IDLE"
        return True

    # ---------------------------------------------------------
    # Manual
    # ---------------------------------------------------------
    def set_manual_mode(self, enabled: bool) -> bool:
        cmd = "MANUAL_ON" if enabled else "MANUAL_OFF"
        ok, _ = self._execute_ok(cmd)
        if not ok:
            return False

        self.snapshot.manual_mode = enabled
        self.snapshot.state = "MANUAL" if enabled else "IDLE"
        return True

    # ---------------------------------------------------------
    # JOG fijo STM32
    # ---------------------------------------------------------
    def jog_left(self) -> bool:
        ok, _ = self._execute_ok("JOG_LEFT")
        if not ok:
            return False

        self._jogging_direction = "left"
        self.snapshot.state = "JOG_LEFT"
        return True

    def jog_right(self) -> bool:
        ok, _ = self._execute_ok("JOG_RIGHT")
        if not ok:
            return False

        self._jogging_direction = "right"
        self.snapshot.state = "JOG_RIGHT"
        return True

    def stop_jog(self) -> bool:
        ok, _ = self._execute_ok("STOP")
        if not ok:
            return False

        self._jogging_direction = None
        self.snapshot.state = "MANUAL" if self.snapshot.manual_mode else "STOPPED"
        self.snapshot.sync_enabled = False
        return True

    # ---------------------------------------------------------
    # JOG por milímetros
    # ---------------------------------------------------------
    def jog_step(self, direction: str, mm: float) -> bool:
        """
        Compatibilidad con la UI existente.

        Antes:
            Python calculaba pasos y mandaba JOGMM:RIGHT:<pasos>.

        Ahora:
            Python manda milímetros x100.
            STM32 calcula pasos.
        """
        direction = (direction or "").strip().upper()
        if direction in ("L", "LEFT", "IZQ", "IZQUIERDA"):
            return self.jog_mm_left(mm)

        if direction in ("R", "RIGHT", "DER", "DERECHA"):
            return self.jog_mm_right(mm)

        self.snapshot.alarm_message = f"Dirección inválida: {direction}"
        return False

    def jog_mm_right(self, mm: float) -> bool:
        mm_x100 = self._mm_to_x100(mm)
        return self.jog_mm_x100_right(mm_x100)

    def jog_mm_left(self, mm: float) -> bool:
        mm_x100 = self._mm_to_x100(mm)
        return self.jog_mm_x100_left(mm_x100)

    def jog_mm_x100_right(self, mm_x100: int) -> bool:
        mm_x100 = int(mm_x100)

        ok, _ = self._execute_ok(f"JOGMM_X100:RIGHT:{mm_x100}")
        if not ok:
            return False

        self.snapshot.state = "JOG_RIGHT"
        self._jogging_direction = "right"
        return True

    def jog_mm_x100_left(self, mm_x100: int) -> bool:
        mm_x100 = int(mm_x100)

        ok, _ = self._execute_ok(f"JOGMM_X100:LEFT:{mm_x100}")
        if not ok:
            return False

        self.snapshot.state = "JOG_LEFT"
        self._jogging_direction = "left"
        return True