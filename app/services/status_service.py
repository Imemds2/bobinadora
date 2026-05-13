from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.constants import ESTADOS
from app.core.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    ACCENT_RED,
    ACCENT_YELLOW,
    TEXT_SECONDARY,
)
from app.protocol import parse_status_msg


@dataclass
class MessageUiEffect:
    log_tag: str = "normal"
    alert_text: Optional[str] = None
    alert_color: Optional[str] = None


@dataclass
class StatusUiData:
    raw: dict
    estado_num: str
    estado_texto: str

    recipe_name: str
    section: str
    total_sections: str
    layer_display: str
    total_layers: str
    target_turns: str
    current_turns: str
    rpm: str
    position_cm: str
    position_label: str
    brake_text: str
    motor_text: str

    is_manual: bool
    alert_text: Optional[str] = None
    alert_color: Optional[str] = None

    # Campos nuevos para STM32
    state_machine: str = ""
    sync: str = "0"
    encoder_count: str = ""
    turns_x100: str = ""
    turns_display: str = ""
    position_steps: str = ""
    position_mm_x100: str = ""
    position_mm: str = ""
    esp_mm_x100: str = ""
    esp_mm: str = ""
    gear: str = ""
    jog_delay_us: str = ""
    lim_min: str = "0"
    lim_max: str = "0"
    can_left: str = "1"
    can_right: str = "1"
    block: str = "0"
    is_home_ok: bool = False
    is_limit_blocked: bool = False


class StatusService:
    """
    Servicio para interpretar mensajes del controlador y traducirlos
    a efectos de UI simples, sin depender de Tkinter.

    Soporta:
    - STATUS legacy tipo ESP32 / app anterior.
    - STATUS STM32 nuevo:
      STATUS:STATE:HOME_OK:SYNC:0:ENC:0:VT_x100:0:POS:0:POS_MM_x100:0...
    """

    def classify_message_tag(self, msg: str) -> str:
        if not msg:
            return "normal"

        if "ERR" in msg:
            return "error"

        if "LIMIT_BLOCKED" in msg:
            return "error"

        if "HOMING" in msg:
            return "info"

        if "HOME_OK" in msg:
            return "ok"

        if "JOG" in msg:
            return "manual"

        if "SYNC" in msg:
            return "info"

        if "PAUSA:CAPA" in msg:
            return "pause"

        if "PAUSA:DER" in msg:
            return "pause"

        if "PAUSA:BARRERA" in msg:
            return "barrera"

        if "TERMINADA" in msg:
            return "ok"

        if "OK" in msg:
            return "ok"

        if "SECCION" in msg:
            return "info"

        if "MANUAL" in msg:
            return "manual"

        return "normal"

    def get_ui_effect(self, msg: str) -> MessageUiEffect:
        """
        Devuelve:
        - tag de monitor
        - alerta opcional para mostrar en la UI
        """
        tag = self.classify_message_tag(msg)

        if "ERR" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text=msg,
                alert_color=ACCENT_RED,
            )

        if "OK:HOMING:DONE" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text="⌂ HOMING terminado — HOME OK",
                alert_color=ACCENT_GREEN,
            )

        if "OK:HOMING:START" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text="⌂ HOMING en progreso...",
                alert_color=ACCENT_ORANGE,
            )

        if "OK:JOGMM_RIGHT" in msg or "OK:JOGMM_LEFT" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text="🔧 Movimiento manual por milímetros ejecutado",
                alert_color=ACCENT_BLUE,
            )

        if "OK:SET_ESP_X100" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text="✓ Espesor configurado",
                alert_color=ACCENT_GREEN,
            )

        if "OK:SET_JOG_DELAY_US" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text="✓ Velocidad de JOG actualizada",
                alert_color=ACCENT_GREEN,
            )

        if "PAUSA:DER" in msg or "PAUSA:BARRERA" in msg:
            alert = self._extract_der_or_barrier_alert(msg)
            return MessageUiEffect(
                log_tag=tag,
                alert_text=alert,
                alert_color=ACCENT_YELLOW,
            )

        if "PAUSA:CAPA" in msg or "PAUSA:CAPA_BARRERA" in msg:
            cn = self._extract_layer_pause_number(msg)
            return MessageUiEffect(
                log_tag=tag,
                alert_text=f"FIN CAPA {cn} — Presione ▶ START",
                alert_color=ACCENT_YELLOW,
            )

        if "SECCION_FIN" in msg:
            nxt = self._extract_next_section_name(msg)
            return MessageUiEffect(
                log_tag=tag,
                alert_text=f"FIN SECCIÓN → Siguiente: {nxt} — Presione ▶ START",
                alert_color=ACCENT_BLUE,
            )

        if "BOBINA_TERMINADA" in msg:
            return MessageUiEffect(
                log_tag=tag,
                alert_text="✓ BOBINA COMPLETA — Presione ▶ START",
                alert_color=ACCENT_GREEN,
            )

        return MessageUiEffect(log_tag=tag)

    def parse_status_ui_data(self, msg: str) -> Optional[StatusUiData]:
        """
        Traduce un STATUS:... a datos listos para pintar en la UI.
        """
        data = parse_status_msg(msg)
        if not data:
            return None

        formato = data.get("_formato", "legacy")

        if formato == "stm32_mm":
            return self._parse_stm32_status(data)

        return self._parse_legacy_status(data)

    # ---------------------------------------------------------
    # Parsers por formato
    # ---------------------------------------------------------

    def _parse_stm32_status(self, data: dict) -> StatusUiData:
        state = data.get("STATE", data.get("_estado", "UNKNOWN"))
        estado_texto = self._machine_state_text(state)

        sync = data.get("SYNC", "0")
        enc = data.get("ENC", "0")
        vt_x100 = data.get("VT_x100", "0")
        turns_display = self._fmt_x100(vt_x100)

        pos_steps = data.get("POS", "0")
        pos_mm_x100 = data.get("POS_MM_x100", "0")
        pos_mm = self._fmt_x100(pos_mm_x100)

        esp_x100 = data.get("ESP_MM_x100", "")
        esp_mm = self._fmt_x100(esp_x100) if esp_x100 != "" else ""

        gear = data.get("GEAR", "")
        jog_delay = data.get("JOG_DELAY_US", "")
        lim_min = data.get("LIM_MIN", "0")
        lim_max = data.get("LIM_MAX", "0")
        can_left = data.get("CAN_LEFT", "1")
        can_right = data.get("CAN_RIGHT", "1")
        block = data.get("BLOCK", "0")

        alert_text, alert_color = self._status_alert_for_machine_state(data)

        is_manual = state in ("MANUAL", "JOG_LEFT", "JOG_RIGHT")
        is_home_ok = state == "HOME_OK"
        is_limit_blocked = state == "LIMIT_BLOCKED" or block in ("1", "2")

        if block == "1":
            brake_text = "⛔ Bloqueado por HOME/MIN"
        elif block == "2":
            brake_text = "⛔ Bloqueado por FINAL/MAX"
        else:
            brake_text = "✓ Límites OK"

        motor_text = "SYNC activo" if sync == "1" else "SYNC apagado"

        return StatusUiData(
            raw=data,
            estado_num=state,
            estado_texto=estado_texto,

            recipe_name=data.get("REC", "STM32"),
            section=data.get("SEC", ""),
            total_sections=data.get("TSEC", ""),
            layer_display=data.get("CAPA", "--"),
            total_layers=data.get("TCAP", ""),
            target_turns=data.get("META", ""),
            current_turns=turns_display,
            rpm=data.get("RPM", ""),
            position_cm=f"{pos_mm} mm",
            position_label=f"Pos: {pos_mm} mm",
            brake_text=brake_text,
            motor_text=motor_text,

            is_manual=is_manual,
            alert_text=alert_text,
            alert_color=alert_color,

            state_machine=state,
            sync=sync,
            encoder_count=enc,
            turns_x100=vt_x100,
            turns_display=turns_display,
            position_steps=pos_steps,
            position_mm_x100=pos_mm_x100,
            position_mm=pos_mm,
            esp_mm_x100=esp_x100,
            esp_mm=esp_mm,
            gear=gear,
            jog_delay_us=jog_delay,
            lim_min=lim_min,
            lim_max=lim_max,
            can_left=can_left,
            can_right=can_right,
            block=block,
            is_home_ok=is_home_ok,
            is_limit_blocked=is_limit_blocked,
        )

    def _parse_legacy_status(self, data: dict) -> StatusUiData:
        estado_num = data.get("_estado", "0")
        estado_texto = ESTADOS.get(estado_num, f"EST_{estado_num}")

        recipe_name = data.get("REC", "")
        section = data.get("SEC", "")
        total_sections = data.get("TSEC", "")
        total_layers = data.get("TCAP", "")
        target_turns = data.get("META", "")
        current_turns = data.get("VT", "")
        rpm = data.get("RPM", "")

        pos_val = data.get("POS", "")
        position_cm = f"{pos_val}cm" if pos_val else ""
        position_label = f"Pos: {pos_val}cm" if pos_val else ""

        capa = data.get("CAPA", "--")
        dcapa = data.get("DCAPA", "0")
        layer_display = dcapa if dcapa not in ("0", "") else capa

        freno = data.get("FRENO", "0")
        var = data.get("VAR", "0")
        brake_text = "🔒 FRENO" if freno == "1" else "🔓 libre"
        motor_text = "⚡ MOTOR" if var == "1" else "⏹ parado"

        is_manual = estado_num == "13"

        alert_text, alert_color = self._status_alert_for_state(estado_num)

        return StatusUiData(
            raw=data,
            estado_num=estado_num,
            estado_texto=estado_texto,

            recipe_name=recipe_name,
            section=section,
            total_sections=total_sections,
            layer_display=layer_display,
            total_layers=total_layers,
            target_turns=target_turns,
            current_turns=current_turns,
            rpm=rpm,
            position_cm=position_cm,
            position_label=position_label,
            brake_text=brake_text,
            motor_text=motor_text,

            is_manual=is_manual,
            alert_text=alert_text,
            alert_color=alert_color,

            state_machine=estado_texto,
            sync=data.get("SYNC", "0"),
            encoder_count=data.get("ENC", ""),
            turns_x100="",
            turns_display=current_turns,
            position_steps=data.get("POS", ""),
            position_mm_x100="",
            position_mm="",
            esp_mm_x100="",
            esp_mm="",
            gear=data.get("GEAR", ""),
            jog_delay_us="",
            lim_min=data.get("LIM_MIN", "0"),
            lim_max=data.get("LIM_MAX", "0"),
            can_left=data.get("CAN_LEFT", "1"),
            can_right=data.get("CAN_RIGHT", "1"),
            block=data.get("BLOCK", "0"),
            is_home_ok=False,
            is_limit_blocked=False,
        )

    # ---------------------------------------------------------
    # Helpers privados
    # ---------------------------------------------------------

    def _fmt_x100(self, value: str, default: str = "0.00") -> str:
        try:
            n = int(value)
            sign = "-" if n < 0 else ""
            n = abs(n)
            return f"{sign}{n // 100}.{n % 100:02d}"
        except Exception:
            return default

    def _machine_state_text(self, state: str) -> str:
        textos = {
            "IDLE": "Sistema listo",
            "MANUAL": "Modo manual",
            "JOG_LEFT": "JOG izquierda",
            "JOG_RIGHT": "JOG derecha",
            "STOPPED": "Detenido",
            "SYNC": "Sincronizando encoder → husillo",
            "LIMIT_BLOCKED": "Bloqueado por límite",
            "HOMING": "Homing en progreso",
            "HOME_OK": "Home OK",
            "HOMING_ERROR": "Error de homing",
            "UNKNOWN": "Estado desconocido",
        }
        return textos.get(state, state)

    def _status_alert_for_machine_state(self, data: dict) -> tuple[Optional[str], Optional[str]]:
        state = data.get("STATE", "UNKNOWN")
        block = data.get("BLOCK", "0")
        lim_min = data.get("LIM_MIN", "0")
        lim_max = data.get("LIM_MAX", "0")
        sync = data.get("SYNC", "0")

        if state == "HOME_OK":
            return "⌂ HOME OK — posición cero validada", ACCENT_GREEN

        if state == "HOMING":
            return "⌂ HOMING en progreso...", ACCENT_ORANGE

        if state == "HOMING_ERROR":
            return "⚠ Error durante HOMING", ACCENT_RED

        if state == "LIMIT_BLOCKED" or block in ("1", "2"):
            if block == "1" or lim_min == "1":
                return "⛔ Límite HOME/MIN activo — solo puede salir hacia la derecha", ACCENT_RED
            if block == "2" or lim_max == "1":
                return "⛔ Límite FINAL/MAX activo — solo puede salir hacia la izquierda", ACCENT_RED
            return "⛔ Movimiento bloqueado por límite", ACCENT_RED

        if state == "SYNC" or sync == "1":
            return "● SINCRONIZANDO — encoder controla el husillo", ACCENT_GREEN

        if state == "JOG_LEFT":
            return "◀ JOG izquierda", ACCENT_BLUE

        if state == "JOG_RIGHT":
            return "▶ JOG derecha", ACCENT_BLUE

        if state == "MANUAL":
            return "⚙ Modo manual", ACCENT_ORANGE

        if state == "STOPPED":
            return "■ Sistema detenido", ACCENT_YELLOW

        if state == "IDLE":
            return "Sistema listo", TEXT_SECONDARY

        return None, None

    def _extract_der_or_barrier_alert(self, msg: str) -> str:
        parts = msg.split(":")
        alert = ""

        for i, part in enumerate(parts):
            if part == "MSG" and i + 1 < len(parts):
                alert = parts[i + 1]
                break

        if alert:
            return alert

        for i, part in enumerate(parts):
            if part in ("DER", "BARRERA") and i + 1 < len(parts):
                return f"⚡ {parts[i + 1]}"

        return "⚠ Pausa del proceso"

    def _extract_layer_pause_number(self, msg: str) -> str:
        parts = msg.split(":")
        return parts[2] if len(parts) > 2 else "?"

    def _extract_next_section_name(self, msg: str) -> str:
        parts = msg.split(":")
        for i, part in enumerate(parts):
            if part == "NEXT_NOMBRE" and i + 1 < len(parts):
                return parts[i + 1]
        return "?"

    def _status_alert_for_state(self, estado_num: str) -> tuple[Optional[str], Optional[str]]:
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
        return alertas.get(estado_num, (None, None))