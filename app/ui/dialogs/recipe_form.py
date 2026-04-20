import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk

from app.core.theme import (
    APP_BG,
    BG_DARK,
    BG_PANEL,
    BG_CARD,
    BG_INPUT,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_YELLOW,
    ACCENT_BLUE,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_ON_ACCENT,
    BORDER_COLOR,
    F_TITLE,
    F_HEAD,
    F_BODY,
    F_BODY_B,
)

from app.ui.widgets.layer_row import LayerRow
from app.ui.widgets.derivacion_row import DerivacionRow


class RecipeForm(ctk.CTkToplevel):
    def __init__(self, parent, recipe=None, on_save=None):
        super().__init__(parent)
        self.title("Editor de Receta — Bobinadora HMI v5.3")
        self.geometry("1060x820")
        self.configure(fg_color=APP_BG)
        self.grab_set()
        self.resizable(True, True)
        self.lift()
        self.focus_force()

        self.on_save = on_save
        self.editing = recipe is not None
        self.sec_layers = [[] for _ in range(8)]
        self.sec_der = [[] for _ in range(8)]
        self.sec_frames = [None] * 8
        self.sec_tipo = [tk.StringVar(value="BOB") for _ in range(8)]
        self.sec_nombre = [tk.StringVar() for _ in range(8)]
        self.num_secs = 0

        self._build(recipe)

    def _build(self, recipe):
        hdr = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=0,
            height=60,
        )
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="CREAR RECETA" if not self.editing else "EDITAR RECETA",
            font=ctk.CTkFont(*F_TITLE),
            text_color=ACCENT_GREEN,
        ).pack(side="left", padx=20, pady=10)

        footer = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=0,
            height=70,
        )
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer,
            text="✓  GUARDAR RECETA",
            command=self._save,
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=TEXT_ON_ACCENT,
            height=50,
            width=380,
            font=ctk.CTkFont("Consolas", 16, "bold"),
        ).pack(side="left", padx=(20, 8), pady=10)

        ctk.CTkButton(
            footer,
            text="✗  CANCELAR",
            command=self.destroy,
            fg_color=ACCENT_RED,
            hover_color="#CC2222",
            text_color=TEXT_ON_ACCENT,
            height=50,
            width=220,
            font=ctk.CTkFont("Consolas", 16, "bold"),
        ).pack(side="left", pady=10)

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=APP_BG,
            corner_radius=0,
        )
        self.scroll.pack(fill="both", expand=True, side="top")

        self._build_basic(recipe)
        self._build_add_section_btn()

        if recipe:
            for sec in recipe.get("secciones", []):
                self._add_section(recipe=sec)
        else:
            self._add_section()

    def _build_basic(self, recipe):
        f = ctk.CTkFrame(self.scroll, fg_color=BG_CARD, corner_radius=8)
        f.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            f,
            text="DATOS BÁSICOS",
            font=ctk.CTkFont(*F_HEAD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(
            row,
            text="Nombre:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        self.name_entry = ctk.CTkEntry(
            row,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(*F_BODY),
            width=300,
            placeholder_text="ej: TRAFO_100KVA_AT",
        )
        self.name_entry.pack(side="left", padx=(0, 30))

        ctk.CTkLabel(
            row,
            text="Espesor alambre (mm):",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        self.esp_entry = ctk.CTkEntry(
            row,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(*F_BODY),
            width=120,
            placeholder_text="ej: 1.5",
        )
        self.esp_entry.pack(side="left")

        if recipe:
            self.name_entry.insert(0, recipe.get("nombre", ""))
            self.esp_entry.insert(0, str(recipe.get("espesorX10", 10) / 10))

    def _build_add_section_btn(self):
        self.add_sec_btn = ctk.CTkButton(
            self.scroll,
            text="＋  AGREGAR NUEVA SECCIÓN",
            command=self._add_section,
            fg_color=BG_CARD,
            hover_color=BG_INPUT,
            border_color=ACCENT_BLUE,
            border_width=2,
            text_color=ACCENT_BLUE,
            height=48,
            font=ctk.CTkFont(*F_BODY_B),
        )
        self.add_sec_btn.pack(fill="x", padx=16, pady=6)

    def _add_section(self, recipe=None):
        if self.num_secs >= 8:
            messagebox.showwarning("Aviso", "Máximo 8 secciones")
            return

        sec_idx = self.num_secs
        self.num_secs += 1
        self.add_sec_btn.pack_forget()

        colors = [
            ACCENT_BLUE,
            ACCENT_GREEN,
            ACCENT_ORANGE,
            ACCENT_PURPLE,
            ACCENT_YELLOW,
            ACCENT_RED,
            "#00CCFF",
            "#FF88CC",
        ]
        color = colors[sec_idx % len(colors)]

        frame = ctk.CTkFrame(self.scroll, fg_color=BG_CARD, corner_radius=10)
        frame.pack(fill="x", padx=16, pady=6)
        self.sec_frames[sec_idx] = frame

        hdr = ctk.CTkFrame(frame, fg_color=BG_INPUT, corner_radius=8)
        hdr.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            hdr,
            text=f"  SECCIÓN {sec_idx + 1}",
            font=ctk.CTkFont(*F_HEAD),
            text_color=color,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            hdr,
            text="＋ AGREGAR CAPA",
            command=lambda s=sec_idx: self._add_layer(s),
            fg_color=ACCENT_GREEN,
            hover_color="#00CC6A",
            text_color=TEXT_ON_ACCENT,
            height=38,
            width=180,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="right", padx=10, pady=10)

        tipo_row = ctk.CTkFrame(frame, fg_color="transparent")
        tipo_row.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            tipo_row,
            text="Tipo:",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(4, 10))

        tipo_var = self.sec_tipo[sec_idx]
        if recipe:
            tipo_var.set(recipe.get("tipo", "BOB"))

        bob_btn = ctk.CTkButton(
            tipo_row,
            text="⚙  BOBINADO",
            width=160,
            height=40,
            font=ctk.CTkFont(*F_BODY_B),
            fg_color=ACCENT_BLUE,
            hover_color="#4080CC",
            text_color=TEXT_ON_ACCENT,
        )
        bob_btn.pack(side="left", padx=4)

        bar_btn = ctk.CTkButton(
            tipo_row,
            text="📄  BARRERA",
            width=160,
            height=40,
            font=ctk.CTkFont(*F_BODY_B),
            fg_color=BG_INPUT,
            hover_color="#8060CC",
            text_color=TEXT_SECONDARY,
        )
        bar_btn.pack(side="left", padx=4)

        def _set_bob():
            tipo_var.set("BOB")
            bob_btn.configure(
                fg_color=ACCENT_BLUE,
                text_color=TEXT_ON_ACCENT,
            )
            bar_btn.configure(
                fg_color=BG_INPUT,
                text_color=TEXT_SECONDARY,
            )

        def _set_bar():
            tipo_var.set("BAR")
            bob_btn.configure(
                fg_color=BG_INPUT,
                text_color=TEXT_SECONDARY,
            )
            bar_btn.configure(
                fg_color=ACCENT_PURPLE,
                text_color=TEXT_ON_ACCENT,
            )

        bob_btn.configure(command=_set_bob)
        bar_btn.configure(command=_set_bar)

        if tipo_var.get() == "BAR":
            _set_bar()

        ctk.CTkLabel(
            tipo_row,
            text="  Nombre:",
            font=ctk.CTkFont(*F_BODY),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(20, 6))

        nom_e = ctk.CTkEntry(
            tipo_row,
            textvariable=self.sec_nombre[sec_idx],
            placeholder_text="ej: Alta Tension",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(*F_BODY),
            width=240,
        )
        nom_e.pack(side="left", padx=6)

        if recipe and recipe.get("nombre"):
            self.sec_nombre[sec_idx].set(recipe["nombre"])

        col_hdr = ctk.CTkFrame(frame, fg_color=BG_INPUT, corner_radius=6)
        col_hdr.pack(fill="x", padx=12, pady=(8, 2))

        for txt, w in [
            ("N°", 60),
            ("VUELTAS ACUMULADAS", 200),
            ("DIRECCIÓN", 190),
            ("✕", 60),
        ]:
            ctk.CTkLabel(
                col_hdr,
                text=txt,
                width=w,
                font=ctk.CTkFont("Consolas", 12, "bold"),
                text_color=TEXT_SECONDARY,
            ).pack(side="left", padx=8, pady=7)

        rows_frame = ctk.CTkFrame(frame, fg_color="transparent")
        rows_frame.pack(fill="x", padx=12, pady=(0, 4))
        frame._rows_frame = rows_frame

        if recipe:
            capas = recipe.get("capas", [])
            dirs = recipe.get("dirs", [True] * len(capas))
            for meta, d in zip(capas, dirs):
                self._add_layer(sec_idx, meta, d)
        else:
            self._add_layer(sec_idx)

        self._build_derivaciones(frame, sec_idx, recipe)
        self._build_add_section_btn()

    def _add_layer(self, sec_idx, meta=None, direction=None):
        rows_frame = self.sec_frames[sec_idx]._rows_frame
        num = len(self.sec_layers[sec_idx]) + 1

        if direction is None:
            direction = (num % 2 == 1)

        row = LayerRow(
            rows_frame,
            num,
            meta,
            direction,
            on_delete=lambda r, s=sec_idx: self._del_layer(s, r),
        )
        row.pack(fill="x", pady=2)
        self.sec_layers[sec_idx].append(row)

    def _del_layer(self, sec_idx, row):
        self.sec_layers[sec_idx].remove(row)
        row.destroy()
        for i, r in enumerate(self.sec_layers[sec_idx]):
            r.update_num(i + 1)

    def _build_derivaciones(self, parent, sec_idx, recipe=None):
        f = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=8)
        f.pack(fill="x", padx=12, pady=(4, 14))

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            hdr,
            text="⚡  DERIVACIONES — paradas con mensaje",
            font=ctk.CTkFont(*F_BODY_B),
            text_color=ACCENT_YELLOW,
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="＋ AGREGAR",
            command=lambda s=sec_idx: self._add_derivacion(s),
            fg_color=ACCENT_YELLOW,
            hover_color="#CC9200",
            text_color=TEXT_ON_ACCENT,
            height=36,
            width=160,
            font=ctk.CTkFont(*F_BODY_B),
        ).pack(side="right")

        der_frame = ctk.CTkFrame(f, fg_color="transparent")
        der_frame.pack(fill="x", padx=10, pady=(0, 10))
        f._der_frame = der_frame
        self.sec_frames[sec_idx]._der_section = f

        if recipe:
            for d in recipe.get("derivaciones", []):
                self._add_derivacion(
                    sec_idx,
                    d.get("vuelta"),
                    d.get("etiqueta"),
                    d.get("mensaje", ""),
                )

    def _add_derivacion(self, sec_idx, vuelta=None, etiqueta=None, mensaje=None):
        der_frame = self.sec_frames[sec_idx]._der_section._der_frame
        row = DerivacionRow(
            der_frame,
            vuelta,
            etiqueta,
            mensaje,
            on_delete=lambda r, s=sec_idx: self._del_der(s, r),
        )
        row.pack(fill="x", pady=3)
        self.sec_der[sec_idx].append(row)

    def _del_der(self, sec_idx, row):
        self.sec_der[sec_idx].remove(row)
        row.destroy()

    def _save(self):
        nombre = self.name_entry.get().strip().replace(" ", "_")
        if not nombre:
            messagebox.showerror("Error", "El nombre no puede estar vacío")
            return

        try:
            esp_mm = float(self.esp_entry.get())
            esp_x10 = int(round(esp_mm * 10))
        except ValueError:
            messagebox.showerror("Error", "Espesor inválido")
            return

        secciones = []
        for sec_idx in range(self.num_secs):
            layers = self.sec_layers[sec_idx]
            if not layers:
                continue

            capas, dirs = [], []
            for row in layers:
                try:
                    meta = float(row.get_meta())
                    if meta <= 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror(
                        "Error",
                        f"S{sec_idx+1} Capa {row.num}: valor inválido",
                    )
                    return

                capas.append(meta)
                dirs.append(row.get_direction())

            for c in range(1, len(capas)):
                if capas[c] <= capas[c - 1]:
                    messagebox.showerror(
                        "Error",
                        f"S{sec_idx+1}: Capa {c+1} ({capas[c]}) debe ser mayor que Capa {c} ({capas[c-1]})",
                    )
                    return

            ders = []
            total = capas[-1]
            for row in self.sec_der[sec_idx]:
                try:
                    v = float(row.get_vuelta())
                    e = row.get_etiqueta()
                    m = row.get_mensaje()

                    if not e:
                        raise ValueError("etiqueta vacía")
                    if v <= 0 or v > total:
                        raise ValueError(f"vuelta {v} fuera de rango 0–{total}")

                    ders.append({
                        "vuelta": v,
                        "etiqueta": e,
                        "mensaje": m,
                    })
                except ValueError as err:
                    messagebox.showerror(
                        "Error",
                        f"S{sec_idx+1}: Derivación inválida — {err}",
                    )
                    return

            ders.sort(key=lambda d: d["vuelta"])

            secciones.append({
                "tipo": self.sec_tipo[sec_idx].get(),
                "nombre": self.sec_nombre[sec_idx].get(),
                "capas": capas,
                "dirs": dirs,
                "derivaciones": ders,
            })

        if not secciones:
            messagebox.showerror("Error", "Agrega al menos una sección")
            return

        recipe = {
            "nombre": nombre,
            "espesorX10": esp_x10,
            "secciones": secciones,
        }

        if self.on_save:
            self.on_save(recipe)

        self.destroy()
