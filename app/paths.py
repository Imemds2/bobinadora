from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RECIPES_DIR = DATA_DIR / "recetas"
CONFIG_FILE = DATA_DIR / "bobinadora_config.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RECIPES_DIR.mkdir(parents=True, exist_ok=True)