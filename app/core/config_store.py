import json
from app.paths import CONFIG_FILE


def cargar_config() -> dict:
    defaults = {
        "espesor_mm": 1.0,
        "retardo_freno": 1.5,
        "freno_no": True,
        "dir_inicial": True,
        "vueltas_prefreno": 5,
        "puerto": "",
        "baudrate": 115200,
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
        except Exception:
            pass

    return defaults


def guardar_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)