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


class StatusService:
    """
    Servicio para interpretar mensajes del controlador y traducirlos
    a efectos de UI simples, sin depender de Tkinter.

    Esta versión maneja:
    - clasificación de tag para monitor
    - alertas derivadas de mensajes no STATUS:
    - transformación de STATUS:... a una estructura amigable para UI
    """

    def classify_message_tag(self, msg: str) -> str:
        if "PAUSA:CAPA" in msg:
            return "pause"
        if "PAUSA:DER" in msg:
            return "pause"
        if "PAUSA:BARRERA" in msg:
            return "barrera"
        if "TERMINADA" in msg:
            return "ok"
        if "ERR" in msg:
            return "error"
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
        )

    # ---------------------------------------------------------
    # Helpers privados
    # ---------------------------------------------------------
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