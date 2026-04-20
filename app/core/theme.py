import json

import customtkinter as ctk

from app.paths import CONFIG_FILE


LIGHT_THEME = {
    "APP_BG": "#F4F7FB",
    "BG_DARK": "#16324A",
    "BG_PANEL": "#FFFFFF",
    "BG_CARD": "#F8FBFF",
    "BG_INPUT": "#ECF2F8",
    "ACCENT_GREEN": "#1F7A4D",
    "ACCENT_RED": "#C44545",
    "ACCENT_YELLOW": "#B7791F",
    "ACCENT_BLUE": "#2B6CB0",
    "ACCENT_ORANGE": "#C05621",
    "ACCENT_PURPLE": "#6B46C1",
    "TEXT_PRIMARY": "#16324A",
    "TEXT_SECONDARY": "#6B7C8F",
    "BORDER_COLOR": "#D7E1EC",
    "TEXT_ON_ACCENT": "#FFFFFF",
    "DIR_FWD_COLOR": "#1F7A4D",
    "DIR_REV_COLOR": "#C44545",
}

DARK_THEME = {
    "APP_BG": "#0D1117",
    "BG_DARK": "#0D1117",
    "BG_PANEL": "#161B22",
    "BG_CARD": "#1C2128",
    "BG_INPUT": "#21262D",
    "ACCENT_GREEN": "#2ECC71",
    "ACCENT_RED": "#FF5A5F",
    "ACCENT_YELLOW": "#E3B341",
    "ACCENT_BLUE": "#58A6FF",
    "ACCENT_ORANGE": "#F0883E",
    "ACCENT_PURPLE": "#BC8CFF",
    "TEXT_PRIMARY": "#E6EDF3",
    "TEXT_SECONDARY": "#8B949E",
    "BORDER_COLOR": "#30363D",
    "TEXT_ON_ACCENT": "#FFFFFF",
    "DIR_FWD_COLOR": "#2ECC71",
    "DIR_REV_COLOR": "#FF5A5F",
}

F_TITLE = ("Consolas", 24, "bold")
F_HEAD = ("Consolas", 16, "bold")
F_BODY = ("Consolas", 14)
F_BODY_B = ("Consolas", 14, "bold")
F_BIG = ("Consolas", 36, "bold")
F_SMALL = ("Consolas", 12)

ESTADOS = {
    "0": "IDLE",
    "1": "BOBINANDO",
    "2": "PREFRENO",
    "3": "PAUSA CAPA",
    "4": "DESBLOQ",
    "5": "PAUSA DER",
    "6": "DER DESBL",
    "7": "ENTRE SEC",
    "8": "TERMINADO",
    "9": "JOG",
    "10": "BARRERA",
    "11": "PAUS BARR",
    "12": "HOMING",
    "13": "MANUAL",
}


def normalize_theme_mode(mode: str | None) -> str:
    value = str(mode or "light").strip().lower()
    return "dark" if value == "dark" else "light"


def get_theme_mode_label(mode: str | None) -> str:
    return "Oscuro" if normalize_theme_mode(mode) == "dark" else "Claro"


def cycle_theme_mode(mode: str | None) -> str:
    return "dark" if normalize_theme_mode(mode) == "light" else "light"


def _load_saved_theme_mode() -> str:
    if not CONFIG_FILE.exists():
        return "light"

    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return "light"

    return normalize_theme_mode(data.get("theme_mode", "light"))


def _apply_palette(mode: str) -> None:
    palette = DARK_THEME if mode == "dark" else LIGHT_THEME
    globals().update(palette)


CURRENT_THEME_MODE = _load_saved_theme_mode()
_apply_palette(CURRENT_THEME_MODE)


def setup_theme() -> None:
    ctk.set_appearance_mode(CURRENT_THEME_MODE)
    ctk.set_default_color_theme("blue")
