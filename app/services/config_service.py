from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ConfigReadResult:
    config: dict[str, Any]


class ConfigService:
    """
    Servicio para leer, normalizar y serializar la configuración
    de la aplicación sin depender de la UI.
    """

    def read_config_from_entries(
        self,
        current_config: dict[str, Any],
        cfg_entries: dict[str, tuple[Any, str]],
        backend_label: str | None = None,
        theme_label: str | None = None,
    ) -> ConfigReadResult:
        cfg = dict(current_config)

        for key, (entry, value_type) in cfg_entries.items():
            try:
                raw_value = entry.get().strip()

                if value_type == "float":
                    cfg[key] = float(raw_value)
                elif value_type == "int":
                    cfg[key] = int(raw_value)
                elif value_type == "bool":
                    cfg[key] = raw_value in ("1", "true", "True")
            except ValueError:
                # Conserva el valor previo si la conversión falla
                pass

        cfg["machine_backend"] = self.resolve_backend_value(backend_label)
        cfg["theme_mode"] = self.resolve_theme_value(theme_label)
        return ConfigReadResult(config=cfg)

    def resolve_backend_value(self, backend_label: str | None) -> str:
        label = str(backend_label or "").strip().lower()
        return "serial" if label == "serial" else "simulated"

    def resolve_theme_value(self, theme_label: str | None) -> str:
        label = str(theme_label or "").strip().lower()
        return "dark" if label == "oscuro" else "light"

    def apply_selected_port(
        self,
        config: dict[str, Any],
        port: str | None,
    ) -> dict[str, Any]:
        cfg = dict(config)
        cfg["puerto"] = str(port or "").strip()
        return cfg

    def build_controller_config_command(self, config: dict[str, Any]) -> str:
        esp_x10 = int(round(float(config.get("espesor_mm", 1.0)) * 10))
        retf = config.get("retardo_freno", 1.5)
        freno = 1 if config.get("freno_no", True) else 0
        dirinit = 1 if config.get("dir_inicial", True) else 0
        vpre = int(config.get("vueltas_prefreno", 5))

        return (
            f"CONFIG:esp={esp_x10},retf={retf},"
            f"frenoNO={freno},dirinit={dirinit},vpre={vpre}"
        )
    
    def build_stm32_config_commands(self, config: dict[str, Any]) -> list[str]:
        """
        Configuración para firmware STM32 actual.

        No mueve el husillo.
        Solo configura parámetros base y solicita estado.
        """
        try:
            esp_mm = float(config.get("espesor_mm", 1.0))
        except (TypeError, ValueError):
            esp_mm = 1.0

        esp_x100 = max(1, int(round(esp_mm * 100)))

        try:
            jog_delay_us = int(config.get("jog_delay_us", 600))
        except (TypeError, ValueError):
            jog_delay_us = 600

        # Mismo rango que firmware STM32.
        jog_delay_us = max(50, min(5000, jog_delay_us))

        try:
            husillo_mm_rev = float(config.get("husillo_mm_rev", 16.0))
        except (TypeError, ValueError):
            husillo_mm_rev = 16.0

        husillo_x100 = max(1, int(round(husillo_mm_rev * 100)))

        try:
            steps_rev = int(config.get("steps_rev", 2000))
        except (TypeError, ValueError):
            steps_rev = 2000

        steps_rev = max(1, steps_rev)

        return [
            f"SET_HUSILLO_X100:{husillo_x100}",
            f"SET_STEPS_REV:{steps_rev}",
            f"SET_ESP_X100:{esp_x100}",
            f"SET_JOG_DELAY_US:{jog_delay_us}",
            "STATUS",
            "LIMITS",
        ]
