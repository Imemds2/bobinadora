import customtkinter as ctk
import tkinter as tk

from app.core.theme import (
    BG_PANEL,
    BG_CARD,
    BG_INPUT,
    ACCENT_GREEN,
    ACCENT_BLUE,
    ACCENT_YELLOW,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER_COLOR,
    F_BODY,
    F_BODY_B,
    F_SMALL,
)


class SidebarPanel:
    def __init__(self, parent, cfg=None, on_refresh_ports=None, on_toggle_connect=None):
        self.parent = parent
        self.cfg = cfg or {}
        self.on_refresh_ports = on_refresh_ports
        self.on_toggle_connect = on_toggle_connect

        self.frame = None

        self.port_var = tk.StringVar(value=self.cfg.get("puerto", ""))

        self.port_combo = None
        self.btn_connect = None

        self.esp_estado = tk.StringVar(value="IDLE")
        self.esp_rec = tk.StringVar(value="--")
        self.esp_sec = tk.StringVar(value="--")
        self.esp_tsec = tk.StringVar(value="--")
        self.esp_capa = tk.StringVar(value="--")
        self.esp_tcap = tk.StringVar(value="--")
        self.esp_meta = tk.StringVar(value="--")
        self.esp_vueltas = tk.StringVar(value="0.0")
        self.esp_rpm = tk.StringVar(value="0")
        self.esp_pos = tk.StringVar(value="0.00cm")
        self.esp_freno = tk.StringVar(value="--")
        self.esp_variador = tk.StringVar(value="--")

    def build(self):
        self.frame = ctk.CTkFrame(
            self.parent,
            fg_color=BG_PANEL,
            width=270,
            corner_radius=8,
        )
        self.frame.grid(row=0, column=0, sticky="nsew")
        self.frame.pack_propagate(False)

        ctk.CTkLabel(
            self.frame,
            text="CONEXIÓN SERIAL",
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(18, 4), padx=15, anchor="w")

        self.port_combo = ctk.CTkComboBox(
            self.frame,
            variable=self.port_var,
            width=240,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=BG_CARD,
            dropdown_fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
        )
        self.port_combo.pack(padx=15, pady=4)

        ctk.CTkButton(
            self.frame,
            text="⟳  ACTUALIZAR",
            command=self._handle_refresh_ports,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_SECONDARY,
            height=36,
            font=ctk.CTkFont(*F_SMALL),
        ).pack(padx=15, pady=3, fill="x")

        self.btn_connect = ctk.CTkButton(
            self.frame,
            text="CONECTAR",
            command=self._handle_toggle_connect,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_INPUT,
            height=44,
            font=ctk.CTkFont(*F_BODY_B),
        )
        self.btn_connect.pack(padx=15, pady=(4, 12), fill="x")

        ctk.CTkFrame(
            self.frame,
            height=1,
            fg_color=BORDER_COLOR,
        ).pack(fill="x", padx=15)

        ctk.CTkLabel(
            self.frame,
            text="ESTADO CONTROLADOR",
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(10, 4), padx=15, anchor="w")

        self._ind(self.frame, "ESTADO", self.esp_estado, ACCENT_BLUE)
        self._ind(self.frame, "RECETA", self.esp_rec, ACCENT_YELLOW)
        self._ind(self.frame, "SECCIÓN", self.esp_sec, ACCENT_PURPLE)
        self._ind(self.frame, "TIPO", self.esp_tsec, ACCENT_ORANGE)
        self._ind(self.frame, "CAPA", self.esp_capa, ACCENT_YELLOW)
        self._ind(self.frame, "TOTAL C.", self.esp_tcap, TEXT_SECONDARY)
        self._ind(self.frame, "PROX PAR", self.esp_meta, ACCENT_GREEN)
        self._ind(self.frame, "VUELTAS", self.esp_vueltas, ACCENT_GREEN)
        self._ind(self.frame, "RPM", self.esp_rpm, ACCENT_ORANGE)
        self._ind(self.frame, "POSICIÓN", self.esp_pos, ACCENT_BLUE)

        ctk.CTkFrame(
            self.frame,
            height=1,
            fg_color=BORDER_COLOR,
        ).pack(fill="x", padx=15, pady=6)

        fv = ctk.CTkFrame(self.frame, fg_color=BG_CARD, corner_radius=6)
        fv.pack(padx=15, fill="x")

        ctk.CTkLabel(
            fv,
            textvariable=self.esp_freno,
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=10, pady=8)

        ctk.CTkLabel(
            fv,
            textvariable=self.esp_variador,
            font=ctk.CTkFont(*F_SMALL, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(side="right", padx=10, pady=8)

        return self.frame

    def _ind(self, parent, label, var, color):
        f = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=6)
        f.pack(padx=15, pady=2, fill="x")

        ctk.CTkLabel(
            f,
            text=label,
            font=ctk.CTkFont(*F_SMALL),
            text_color=TEXT_SECONDARY,
            width=80,
        ).pack(side="left", padx=8, pady=5)

        ctk.CTkLabel(
            f,
            textvariable=var,
            font=ctk.CTkFont("Consolas", 13, "bold"),
            text_color=color,
        ).pack(side="right", padx=8)

    def _handle_refresh_ports(self):
        if self.on_refresh_ports:
            self.on_refresh_ports()

    def _handle_toggle_connect(self):
        if self.on_toggle_connect:
            self.on_toggle_connect()

    def set_ports(self, ports):
        self.port_combo.configure(values=ports)

    def set_selected_port(self, port):
        self.port_var.set(port)

    def get_selected_port(self):
        return self.port_var.get()

    def set_connect_button_connected(self):
        self.btn_connect.configure(
            text="DESCONECTAR",
            fg_color="#FF3B3B",
            hover_color="#CC2222",
            text_color=TEXT_PRIMARY,
        )

    def set_connect_button_disconnected(self):
        self.btn_connect.configure(
            text="CONECTAR",
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=BG_INPUT,
        )

    def set_estado(self, value): self.esp_estado.set(value)
    def set_receta(self, value): self.esp_rec.set(value)
    def set_seccion(self, value): self.esp_sec.set(value)
    def set_tipo(self, value): self.esp_tsec.set(value)
    def set_capa(self, value): self.esp_capa.set(value)
    def set_total_capas(self, value): self.esp_tcap.set(value)
    def set_meta(self, value): self.esp_meta.set(value)
    def set_vueltas(self, value): self.esp_vueltas.set(value)
    def set_rpm(self, value): self.esp_rpm.set(value)
    def set_posicion(self, value): self.esp_pos.set(value)
    def set_freno(self, value): self.esp_freno.set(value)
    def set_variador(self, value): self.esp_variador.set(value)