from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.recipe_manager import validate_recipe, save_recipe


@dataclass
class SelectedRecipeData:
    name: str
    recipe: dict[str, Any]
    detail_text: str


@dataclass
class SaveRecipeResult:
    ok: bool
    recipe_name: str = ""
    error_message: str = ""


@dataclass
class SectionPositionData:
    section_number: int
    section_name: str
    section_type: str
    total_section_turns: float
    layer_index: int
    layer_number: int
    turns_before_layer: float
    turns_in_layer: float
    layer_turns: float
    layer_direction_text: str
    pulses: int
    next_derivation_text: str = ""

@dataclass
class RuntimeRecipeEvent:
    section_index: int
    section_number: int
    section_name: str
    section_type: str

    event_type: str
    turns: float
    vt_x100: int

    layer_index: int = 0
    layer_number: int = 0

    direction: str = "RIGHT"
    uses_husillo: bool = False

    etiqueta: str = ""
    mensaje: str = ""
    label: str = ""

class RecipeService:
    """
    Servicio de apoyo para lógica de recetas que no depende de UI.
    """

    def build_recipe_summary(self, recipe: dict[str, Any]) -> str:
        lines: list[str] = [
            f"NOMBRE   : {recipe['nombre']}",
            f"ESPESOR  : {recipe.get('espesorX10', 10) / 10:.1f} mm",
            f"SECCIONES: {len(recipe.get('secciones', []))}",
            "",
        ]

        for i, sec in enumerate(recipe.get("secciones", [])):
            tipo = sec.get("tipo", "BOB")
            nombre = sec.get("nombre", "")
            icono = "⚙" if tipo == "BOB" else "📄"
            lines.append(f"{icono} S{i+1}: {nombre} [{tipo}]")

            capas = sec.get("capas", [])
            dirs = sec.get("dirs", [True] * len(capas))
            acumulado_anterior = 0.0

            for capa_idx, (meta, direccion) in enumerate(zip(capas, dirs)):
                vueltas_capa = round(meta - acumulado_anterior, 1)
                sentido = "→MAX" if direccion else "←MIN"
                lines.append(
                    f"  Capa {capa_idx+1:2d}: {vueltas_capa:6.1f}v "
                    f"(acum:{meta:7.1f})  {sentido}"
                )
                acumulado_anterior = meta

            for derivacion in sec.get("derivaciones", []):
                mensaje = derivacion.get("mensaje", "")
                lines.append(
                    f"    ⚡ [{derivacion['etiqueta']}] @{derivacion['vuelta']}v"
                    + (f" → {mensaje}" if mensaje else "")
                )

            lines.append("")

        return "\n".join(lines)

    def get_recipe_names(self, recipes: list[str]) -> list[str]:
        return list(recipes)

    def get_recipe_display_name(self, recipe: dict[str, Any]) -> str:
        return str(recipe.get("nombre", "")).strip()

    def get_section_count(self, recipe: dict[str, Any]) -> int:
        return len(recipe.get("secciones", []))

    def get_section_number_values(self, recipe: dict[str, Any]) -> list[str]:
        count = self.get_section_count(recipe)
        return [str(i + 1) for i in range(count)]

    def has_recipe(self, recipe: dict[str, Any] | None) -> bool:
        return bool(recipe and recipe.get("nombre"))

    def get_recipe_run_name(self, recipe: dict[str, Any] | None) -> str:
        if not recipe:
            return ""
        return str(recipe.get("nombre", "")).strip()

    def build_selected_recipe_data(
        self,
        name: str,
        recipe: Optional[dict[str, Any]],
    ) -> Optional[SelectedRecipeData]:
        if not recipe:
            return None

        clean_name = str(name).strip()
        detail_text = self.build_recipe_summary(recipe)

        return SelectedRecipeData(
            name=clean_name,
            recipe=recipe,
            detail_text=detail_text,
        )

    def can_delete_recipe(self, selected_name: str | None) -> tuple[bool, str]:
        if not selected_name:
            return False, "Selecciona una receta primero"
        return True, ""

    def build_delete_confirmation_message(self, recipe_name: str) -> str:
        return f"¿Eliminar '{recipe_name}' del sistema local?"

    def save_recipe_flow(self, recipe: dict[str, Any]) -> SaveRecipeResult:
        ok, motivo = validate_recipe(recipe)
        if not ok:
            return SaveRecipeResult(
                ok=False,
                error_message=f"Error de validación: {motivo}",
            )

        resultado = save_recipe(recipe)
        if not resultado:
            return SaveRecipeResult(
                ok=False,
                error_message=(
                    "No se pudo guardar la receta.\n\n"
                    "Verifica que existe la carpeta de recetas en data/recetas."
                ),
            )

        recipe_name = self.get_recipe_display_name(recipe)
        return SaveRecipeResult(
            ok=True,
            recipe_name=recipe_name,
        )

    def build_recipe_upload_commands(self, recipe: dict[str, Any]) -> list[tuple[str, str]]:
        commands: list[tuple[str, str]] = []

        recipe_name = self.get_recipe_display_name(recipe)
        commands.append(("NEW", f"NEW:{recipe_name}"))
        commands.append(("ESP", f"ESP:{recipe.get('espesorX10', 10)}"))

        for i, sec in enumerate(recipe.get("secciones", []), start=1):
            section_prefix = f"S{i}"
            tipo = sec.get("tipo", "BOB")
            commands.append((f"{section_prefix} TIPO", f"{section_prefix}:TIPO:{tipo}"))

            nombre = str(sec.get("nombre", "")).strip()
            if nombre:
                commands.append((f"{section_prefix} NOMBRE", f"{section_prefix}:NOMBRE:{nombre}"))

            capas = sec.get("capas", [])
            capas_str = ",".join(str(c) for c in capas)
            commands.append((f"{section_prefix} CAPAS", f"{section_prefix}:C:{capas_str}"))

            if "dirs" in sec:
                dirs = sec.get("dirs", [])
                dirs_str = "".join(">" if d else "<" for d in dirs)
                commands.append((f"{section_prefix} DIR", f"{section_prefix}:DIR:{dirs_str}"))

            derivaciones = sec.get("derivaciones", [])
            if derivaciones:
                der_str = ",".join(
                    f"{d['vuelta']}:{d['etiqueta']}:{d.get('mensaje', '')}"
                    for d in derivaciones
                )
                commands.append((f"{section_prefix} DER", f"{section_prefix}:D:{der_str}"))

        commands.append(("END", "END"))
        return commands

    def build_run_command(self, recipe_name: str) -> str:
        clean_name = str(recipe_name).strip()
        return f"RUN:{clean_name}"

    def build_run_section_command(self, recipe_name: str, section_index: int) -> str:
        clean_name = str(recipe_name).strip()
        return f"RUN:{clean_name}:SEC:{section_index}"
    
    # ---------------------------------------------------------
    # STM32 / migración desde ESP32
    # ---------------------------------------------------------
    def get_espesor_x100(self, recipe: dict[str, Any]) -> int:
        """
        La receta actual guarda espesorX10:
            10 = 1.0 mm
            25 = 2.5 mm

        La STM32 espera ESP_MM_x100:
            100 = 1.00 mm
            250 = 2.50 mm
        """
        try:
            esp_x10 = int(recipe.get("espesorX10", 10))
        except (TypeError, ValueError):
            esp_x10 = 10

        return max(1, esp_x10 * 10)

    def section_uses_husillo(self, section: dict[str, Any]) -> bool:
        """
        Regla mínima, sin rediseñar recetas:

        - Si en el futuro una sección trae usar_husillo explícito,
          respetamos ese valor.
        - Si no existe, inferimos:
            BOB = usa husillo
            BAR / LAM / otros = no usa husillo
        """
        if "usar_husillo" in section:
            return bool(section.get("usar_husillo"))

        tipo = str(section.get("tipo", "BOB")).strip().upper()
        return tipo == "BOB"

    def recipe_uses_husillo(self, recipe: dict[str, Any]) -> bool:
        """
        La receta usa husillo si al menos una sección requiere avance automático.
        """
        return any(
            self.section_uses_husillo(sec)
            for sec in recipe.get("secciones", [])
        )

    def build_stm32_recipe_prepare_commands(
        self,
        recipe: dict[str, Any],
    ) -> list[tuple[str, str]]:
        """
        Reemplazo mínimo para cargar receta en STM32.

        Importante:
        Esto NO mueve el husillo.
        Solo configura valores operativos.
        """
        esp_x100 = self.get_espesor_x100(recipe)

        return [
            ("ESPESOR", f"SET_ESP_X100:{esp_x100}"),
            ("STATUS", "STATUS"),
            ("LIMITS", "LIMITS"),
        ]

    def build_stm32_run_commands(
        self,
        recipe: dict[str, Any],
    ) -> list[tuple[str, str]]:
        """
        START lógico para STM32.

        No arranca mandril.
        Solo arma sincronización del husillo si aplica.
        """
        if self.recipe_uses_husillo(recipe):
            return [
                ("SYNC HUSILLO", "SYNC_ON"),
            ]

        return [
            ("HUSILLO OFF", "SYNC_OFF"),
        ]

    def build_stm32_run_section_commands(
        self,
        recipe: dict[str, Any],
        section_index: int,
    ) -> list[tuple[str, str]]:
        """
        Inicio lógico de sección para STM32.

        Por ahora no hay motor/variador integrado.
        Solo activamos o desactivamos SYNC según la sección.
        """
        secciones = recipe.get("secciones", [])

        if section_index < 0 or section_index >= len(secciones):
            return [
                ("ERROR", "STATUS"),
            ]

        section = secciones[section_index]

        if self.section_uses_husillo(section):
            return [
                ("SYNC HUSILLO", "SYNC_ON"),
            ]

        return [
            ("HUSILLO OFF", "SYNC_OFF"),
        ]
    
    # ---------------------------------------------------------
    # Plan de ejecución / eventos de receta
    # ---------------------------------------------------------
    def build_runtime_plan(self, recipe: dict[str, Any]) -> list[RuntimeRecipeEvent]:
        """
        Construye el plan completo de eventos de la receta.

        Importante:
        Los eventos se manejan por sección. Las vueltas de cada sección son
        relativas a esa sección, igual que en el JSON actual.
        """
        events: list[RuntimeRecipeEvent] = []

        for section_index, section in enumerate(recipe.get("secciones", [])):
            events.extend(
                self.build_section_runtime_events(
                    recipe,
                    section_index,
                )
            )

        return events

    def build_section_runtime_events(
        self,
        recipe: dict[str, Any],
        section_index: int,
    ) -> list[RuntimeRecipeEvent]:
        secciones = recipe.get("secciones", [])

        if section_index < 0 or section_index >= len(secciones):
            return []

        sec = secciones[section_index]

        section_number = section_index + 1
        section_name = str(sec.get("nombre", "")).strip()
        section_type = str(sec.get("tipo", "BOB")).strip().upper()
        uses_husillo = self.section_uses_husillo(sec)

        capas = sec.get("capas", [])
        dirs = sec.get("dirs", [True] * len(capas))

        events: list[RuntimeRecipeEvent] = []

        # Eventos de fin de capa / barrera
        for layer_index, meta in enumerate(capas):
            try:
                turns = float(meta)
            except (TypeError, ValueError):
                continue

            dir_bool = dirs[layer_index] if layer_index < len(dirs) else True
            direction = "RIGHT" if dir_bool else "LEFT"

            if section_type == "BAR":
                event_type = "BARRIER"
                label = f"S{section_number} {section_name} — BARRERA @{turns:.2f}v"
            else:
                event_type = "LAYER_END"
                label = (
                    f"S{section_number} {section_name} — "
                    f"FIN CAPA {layer_index + 1} @{turns:.2f}v"
                )

            events.append(
                RuntimeRecipeEvent(
                    section_index=section_index,
                    section_number=section_number,
                    section_name=section_name,
                    section_type=section_type,
                    event_type=event_type,
                    turns=turns,
                    vt_x100=int(round(turns * 100)),
                    layer_index=layer_index,
                    layer_number=layer_index + 1,
                    direction=direction,
                    uses_husillo=uses_husillo,
                    label=label,
                )
            )

        # Eventos de derivación / taps
        for derivacion in sec.get("derivaciones", []):
            try:
                turns = float(derivacion.get("vuelta", 0))
            except (TypeError, ValueError):
                continue

            layer_index = self._find_layer_index(capas, turns) if capas else 0
            dir_bool = dirs[layer_index] if layer_index < len(dirs) else True
            direction = "RIGHT" if dir_bool else "LEFT"

            etiqueta = str(derivacion.get("etiqueta", "")).strip()
            mensaje = str(derivacion.get("mensaje", "")).strip()

            label = (
                f"S{section_number} {section_name} — "
                f"DERIVACIÓN {etiqueta} @{turns:.2f}v"
            )

            if mensaje:
                label += f" → {mensaje}"

            events.append(
                RuntimeRecipeEvent(
                    section_index=section_index,
                    section_number=section_number,
                    section_name=section_name,
                    section_type=section_type,
                    event_type="DERIVATION",
                    turns=turns,
                    vt_x100=int(round(turns * 100)),
                    layer_index=layer_index,
                    layer_number=layer_index + 1,
                    direction=direction,
                    uses_husillo=uses_husillo,
                    etiqueta=etiqueta,
                    mensaje=mensaje,
                    label=label,
                )
            )

        return sorted(
            events,
            key=lambda e: (
                e.vt_x100,
                self._runtime_event_priority(e.event_type),
            )
        )

    def _runtime_event_priority(self, event_type: str) -> int:
        """
        Si dos eventos caen en la misma vuelta:
        - Primero derivación.
        - Luego barrera.
        - Luego fin de capa.
        """
        priorities = {
            "DERIVATION": 10,
            "BARRIER": 20,
            "LAYER_END": 30,
        }

        return priorities.get(str(event_type).upper(), 99)

    # ---------------------------------------------------------
    # Posición / reanudación
    # ---------------------------------------------------------
    def get_section_position_data(
        self,
        recipe: dict[str, Any],
        section_number: int,
        current_turns: float,
    ) -> SectionPositionData:
        secciones = recipe.get("secciones", [])
        if section_number < 1 or section_number > len(secciones):
            raise ValueError(f"Sección {section_number} no existe")

        sec = secciones[section_number - 1]
        section_name = sec.get("nombre", "")
        section_type = sec.get("tipo", "BOB")
        capas = sec.get("capas", [])

        if not capas:
            raise ValueError(f"S{section_number} sin capas")

        total_section_turns = float(capas[-1])

        if current_turns < 0 or current_turns > total_section_turns:
            raise ValueError(
                f"Vuelta {current_turns} fuera de rango.\n"
                f"S{section_number} acepta: 0 – {total_section_turns:.1f}v acumuladas."
            )

        layer_index = self._find_layer_index(capas, current_turns)
        layer_number = layer_index + 1
        turns_before_layer = float(capas[layer_index - 1]) if layer_index > 0 else 0.0
        turns_in_layer = round(current_turns - turns_before_layer, 1)
        layer_turns = round(float(capas[layer_index]) - turns_before_layer, 1)

        dirs = sec.get("dirs", [True] * len(capas))
        direction = dirs[layer_index] if layer_index < len(dirs) else True
        layer_direction_text = "->" if direction else "<-"

        pulses = int(round(current_turns * 200))
        next_derivation_text = self._build_next_derivation_text(sec, current_turns)

        return SectionPositionData(
            section_number=section_number,
            section_name=section_name,
            section_type=section_type,
            total_section_turns=total_section_turns,
            layer_index=layer_index,
            layer_number=layer_number,
            turns_before_layer=turns_before_layer,
            turns_in_layer=turns_in_layer,
            layer_turns=layer_turns,
            layer_direction_text=layer_direction_text,
            pulses=pulses,
            next_derivation_text=next_derivation_text,
        )

    def normalize_turn_value(
        self,
        recipe: dict[str, Any],
        section_number: int,
        current_turns: float,
    ) -> float:
        position_data = self.get_section_position_data(
            recipe,
            section_number,
            current_turns,
        )
        value = position_data.turns_before_layer + position_data.turns_in_layer
        return round(value, 1)

    def increment_turn_value(
        self,
        recipe: dict[str, Any],
        section_number: int,
        current_turns: float,
        delta: float,
    ) -> float:
        sec = self._get_section(recipe, section_number)
        capas = sec.get("capas", [])
        if not capas:
            raise ValueError(f"S{section_number} sin capas")

        total = float(capas[-1])
        new_value = round(current_turns + delta, 1)
        new_value = max(0.0, min(new_value, total))
        return round(new_value, 1)

    def build_section_info_text(self, recipe: dict[str, Any], section_number: int) -> str:
        sec = self._get_section(recipe, section_number)
        return f"{sec.get('nombre', '')}  [{sec.get('tipo', 'BOB')}]"

    def build_layer_info_text(self, position_data: SectionPositionData) -> str:
        return (
            f"Capa {position_data.layer_number} "
            f"({position_data.layer_turns:.0f}v)  "
            f"{position_data.layer_direction_text}\n"
            f"Rango: 0 – {position_data.total_section_turns:.0f}v acum."
        )

    def build_position_summary(
        self,
        recipe_name: str,
        position_data: SectionPositionData,
    ) -> str:
        current_turns = position_data.turns_before_layer + position_data.turns_in_layer
        return (
            f"Receta   : {recipe_name}\n"
            f"Sección  : {position_data.section_number} — "
            f"{position_data.section_name} [{position_data.section_type}]\n"
            f"─────────────────────────────\n"
            f"Vuelta acum. : {current_turns:.1f}v "
            f"(de {position_data.total_section_turns:.1f}v totales)\n"
            f"Capa detect. : {position_data.layer_number} "
            f"({position_data.turns_in_layer:.1f}v dentro de capa)\n"
            f"Encoder      : {position_data.pulses} pulsos"
            f"{position_data.next_derivation_text}\n"
            f"─────────────────────────────\n"
            f"El controlador iniciará en S{position_data.section_number} "
            f"con encoder={position_data.pulses}."
        )

    # ---------------------------------------------------------
    # Helpers privados
    # ---------------------------------------------------------
    def _get_section(self, recipe: dict[str, Any], section_number: int) -> dict[str, Any]:
        secciones = recipe.get("secciones", [])
        if section_number < 1 or section_number > len(secciones):
            raise ValueError(f"Sección {section_number} no existe")
        return secciones[section_number - 1]

    def _find_layer_index(self, capas: list[Any], current_turns: float) -> int:
        for idx, limit in enumerate(capas):
            if current_turns <= float(limit):
                return idx
        return max(0, len(capas) - 1)

    def _build_next_derivation_text(self, sec: dict[str, Any], current_turns: float) -> str:
        for der in sec.get("derivaciones", []):
            if float(der["vuelta"]) > current_turns:
                return f"\n  Próx. parada : [{der['etiqueta']}] @{der['vuelta']}v"
        return ""