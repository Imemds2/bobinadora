from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SelectedRecipeData:
    name: str
    recipe: dict[str, Any]
    detail_text: str


class RecipeService:
    """
    Servicio de apoyo para lógica de recetas que no depende de UI.

    Etapa actual:
    - construir resumen legible de receta
    - helpers simples para listas y valores de UI
    - resolver selección de receta
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