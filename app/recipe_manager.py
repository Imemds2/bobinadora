import json
from typing import Optional
from .paths import RECIPES_DIR


def _filepath(nombre: str):
    safe = "".join(c for c in nombre if c.isalnum() or c in "_-. ")
    safe = safe.strip().replace(" ", "_")
    if not safe:
        safe = "receta"
    return RECIPES_DIR / f"{safe}.json"


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