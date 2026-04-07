import json
from typing import Optional
from .paths import RECIPES_DIR


def _filepath(nombre: str):
    safe = "".join(c for c in nombre if c.isalnum() or c in "_-. ")
    safe = safe.strip().replace(" ", "_")
    if not safe:
        safe = "receta"
    return RECIPES_DIR / f"{safe}.json"


def validate_recipe(recipe: dict):
    if not isinstance(recipe, dict):
        return False, "La receta debe ser un objeto válido"

    nombre = str(recipe.get("nombre", "")).strip()
    if not nombre:
        return False, "La receta debe tener un nombre"

    secciones = recipe.get("secciones")
    if not isinstance(secciones, list) or not secciones:
        return False, "La receta debe tener al menos una sección"

    for idx, sec in enumerate(secciones, start=1):
        if not isinstance(sec, dict):
            return False, f"La sección {idx} no es válida"

        capas = sec.get("capas", [])
        if not isinstance(capas, list) or not capas:
            return False, f"La sección {idx} debe tener al menos una capa"

        try:
            capas_float = [float(c) for c in capas]
        except Exception:
            return False, f"La sección {idx} contiene capas inválidas"

        for i in range(1, len(capas_float)):
            if capas_float[i] <= capas_float[i - 1]:
                return False, (
                    f"La sección {idx} debe tener capas acumuladas en orden ascendente"
                )

        dirs = sec.get("dirs", [])
        if dirs and len(dirs) != len(capas):
            return False, (
                f"La sección {idx} tiene una cantidad de direcciones distinta a sus capas"
            )

        derivaciones = sec.get("derivaciones", [])
        if derivaciones and not isinstance(derivaciones, list):
            return False, f"La sección {idx} tiene derivaciones inválidas"

    return True, "OK"


def save_recipe(recipe: dict) -> bool:
    try:
        nombre = recipe.get("nombre", "sin_nombre")
        path = _filepath(nombre)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(recipe, f, indent=2, ensure_ascii=False)

        print(f"[recipe_manager] Guardada: {path}")
        return True
    except Exception as e:
        print(f"[recipe_manager] ERROR save_recipe: {e}")
        return False


def load_recipe(nombre: str) -> Optional[dict]:
    if not nombre:
        return None
    try:
        path = _filepath(nombre)
        if not path.exists():
            alt = RECIPES_DIR / f"{nombre}.json"
            if alt.exists():
                path = alt
            else:
                return None

        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[recipe_manager] ERROR load_recipe '{nombre}': {e}")
        return None


def list_recipes() -> list:
    try:
        nombres = []
        for path in sorted(RECIPES_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                nombres.append(data.get("nombre", path.stem))
            except Exception:
                nombres.append(path.stem)
        return nombres
    except Exception as e:
        print(f"[recipe_manager] ERROR list_recipes: {e}")
        return []


def delete_recipe(nombre: str) -> bool:
    try:
        path = _filepath(nombre)
        if path.exists():
            path.unlink()
            print(f"[recipe_manager] Eliminada: {path}")
            return True

        alt = RECIPES_DIR / f"{nombre}.json"
        if alt.exists():
            alt.unlink()
            print(f"[recipe_manager] Eliminada: {alt}")
            return True

        print(f"[recipe_manager] No encontrada: {nombre}")
        return False
    except Exception as e:
        print(f"[recipe_manager] ERROR delete_recipe: {e}")
        return False