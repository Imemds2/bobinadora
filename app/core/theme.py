import customtkinter as ctk

BG_DARK        = "#0D1117"
BG_PANEL       = "#161B22"
BG_CARD        = "#1C2128"
BG_INPUT       = "#21262D"
ACCENT_GREEN   = "#00FF88"
ACCENT_RED     = "#FF3B3B"
ACCENT_YELLOW  = "#FFB800"
ACCENT_BLUE    = "#58A6FF"
ACCENT_ORANGE  = "#F78166"
ACCENT_PURPLE  = "#BC8CFF"
TEXT_PRIMARY   = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
BORDER_COLOR   = "#30363D"
DIR_FWD_COLOR  = "#00FF88"
DIR_REV_COLOR  = "#FF3B3B"

F_TITLE  = ("Consolas", 24, "bold")
F_HEAD   = ("Consolas", 16, "bold")
F_BODY   = ("Consolas", 14)
F_BODY_B = ("Consolas", 14, "bold")
F_BIG    = ("Consolas", 36, "bold")
F_SMALL  = ("Consolas", 12)

ESTADOS = {
    "0":  "IDLE",
    "1":  "BOBINANDO",
    "2":  "PREFRENO",
    "3":  "PAUSA CAPA",
    "4":  "DESBLOQ",
    "5":  "PAUSA DER",
    "6":  "DER DESBL",
    "7":  "ENTRE SEC",
    "8":  "TERMINADO",
    "9":  "JOG",
    "10": "BARRERA",
    "11": "PAUS BARR",
    "12": "HOMING",
    "13": "MANUAL",
}

def setup_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")