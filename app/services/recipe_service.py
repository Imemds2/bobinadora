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


class RecipeService:
    """
    Servicio de apoyo para lógica de recetas que no depende de UI.

    Etapa actual:
    - construir resumen legible de receta
    - helpers simples para listas y valores de UI
    - resolver selección de receta
    - validar y guardar receta
    - convertir receta a comandos para el controlador
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
        """
        Devuelve una lista de pares:
        - etiqueta legible para logs
        - comando serial a enviar
        """
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