# app/services/log_service.py

from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime, date
from pathlib import Path
from typing import Deque, List, Optional


class LogService:
    """
    Servicio de logging persistente para la app.

    Responsabilidades:
    - crear carpeta de logs
    - escribir eventos en archivo diario
    - hacer flush inmediato
    - rotar automáticamente por fecha
    - permitir lectura de últimas líneas para recuperación
    """

    def __init__(
        self,
        logs_dir: Optional[Path] = None,
        app_name: str = "bobinadora",
        encoding: str = "utf-8",
        fsync_enabled: bool = False,
    ) -> None:
        """
        fsync_enabled=False:
            Más rápido, normalmente suficiente con flush().
        fsync_enabled=True:
            Más robusto ante apagones bruscos, pero más pesado.
        """
        self.app_name = app_name
        self.encoding = encoding
        self.fsync_enabled = fsync_enabled

        if logs_dir is None:
            # app/services/log_service.py -> app/services -> app -> proyecto
            project_root = Path(__file__).resolve().parents[2]
            logs_dir = project_root / "data" / "logs"

        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._current_date: Optional[date] = None
        self._current_path: Optional[Path] = None
        self._fh = None

        self._ensure_file_ready()

    # -------------------------------------------------------------------------
    # API pública
    # -------------------------------------------------------------------------

    def log(self, message: str, tag: str = "normal") -> str:
        """
        Escribe una línea de log y devuelve la línea ya formateada.
        """
        line = self._format_line(message=message, tag=tag)
        self._write_line(line)
        return line

    def session_start(self, extra: Optional[str] = None) -> str:
        """
        Marca inicio de sesión en el log.
        """
        divider = "================ INICIO DE SESIÓN ================="
        line1 = self.log(divider, tag="session")

        if extra:
            self.log(extra, tag="session")

        return line1

    def session_end(self, extra: Optional[str] = None) -> str:
        """
        Marca fin de sesión en el log.
        """
        if extra:
            self.log(extra, tag="session")

        divider = "================ FIN DE SESIÓN ================="
        return self.log(divider, tag="session")

    def read_recent_lines(
        self,
        max_lines: int = 50,
        include_previous_day_if_empty: bool = True,
    ) -> List[str]:
        """
        Lee las últimas N líneas del log actual.
        Si el de hoy está vacío y include_previous_day_if_empty=True,
        intenta leer del archivo de ayer.
        """
        today_path = self._build_log_path(datetime.now().date())
        lines = self._tail_file(today_path, max_lines=max_lines)

        if lines:
            return lines

        if include_previous_day_if_empty:
            yesterday = datetime.now().date().fromordinal(datetime.now().date().toordinal() - 1)
            yesterday_path = self._build_log_path(yesterday)
            return self._tail_file(yesterday_path, max_lines=max_lines)

        return []

    def get_last_relevant_event(self, tags: Optional[List[str]] = None) -> Optional[str]:
        """
        Busca hacia atrás el último evento que coincida con alguno de los tags dados.
        Si tags es None, devuelve simplemente la última línea disponible.
        """
        recent = self.read_recent_lines(max_lines=200)

        if not recent:
            return None

        if not tags:
            return recent[-1]

        expected = [self._normalize_tag(tag) for tag in tags]

        for line in reversed(recent):
            for tag in expected:
                needle = f"[{tag}]"
                if needle in line:
                    return line

        return None

    def was_last_session_closed_cleanly(self) -> bool:
        """
        Revisa si en las últimas líneas aparece FIN DE SESIÓN después del último INICIO.
        """
        recent = self.read_recent_lines(max_lines=300)

        if not recent:
            return True

        last_start_idx = -1
        last_end_idx = -1

        for idx, line in enumerate(recent):
            if "INICIO DE SESIÓN" in line:
                last_start_idx = idx
            if "FIN DE SESIÓN" in line:
                last_end_idx = idx

        if last_start_idx == -1:
            return True

        return last_end_idx > last_start_idx

    def close(self) -> None:
        """
        Cierra el archivo actual.
        """
        with self._lock:
            if self._fh:
                try:
                    self._fh.flush()
                except Exception:
                    pass

                try:
                    self._fh.close()
                except Exception:
                    pass

                self._fh = None
                self._current_date = None
                self._current_path = None

    # -------------------------------------------------------------------------
    # Internos
    # -------------------------------------------------------------------------

    def _format_line(self, message: str, tag: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized_tag = self._normalize_tag(tag)
        safe_message = str(message).replace("\r\n", " ").replace("\n", " ").strip()
        return f"[{now}] [{normalized_tag}] {safe_message}"

    def _normalize_tag(self, tag: str) -> str:
        tag = (tag or "normal").strip().upper()

        aliases = {
            "NORMAL": "INFO",
            "INFO": "INFO",
            "OK": "OK",
            "ERROR": "ERROR",
            "PAUSE": "PAUSE",
            "WARNING": "WARN",
            "WARN": "WARN",
            "SESSION": "SESSION",
            "MANUAL": "MANUAL",
            "BARRERA": "BARRERA",
            "DEBUG": "DEBUG",
        }

        return aliases.get(tag, tag)

    def _ensure_file_ready(self) -> None:
        current_day = datetime.now().date()

        if self._fh is not None and self._current_date == current_day:
            return

        if self._fh is not None:
            try:
                self._fh.flush()
                self._fh.close()
            except Exception:
                pass
            finally:
                self._fh = None

        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._current_date = current_day
        self._current_path = self._build_log_path(current_day)

        self._fh = open(
            self._current_path,
            mode="a",
            encoding=self.encoding,
            buffering=1,  # line-buffered
        )

    def _build_log_path(self, day: date) -> Path:
        filename = f"{day.strftime('%Y-%m-%d')}_{self.app_name}.log"
        return self.logs_dir / filename

    def _write_line(self, line: str) -> None:
        with self._lock:
            self._ensure_file_ready()

            if self._fh is None:
                raise RuntimeError("No se pudo abrir el archivo de log.")

            self._fh.write(line + "\n")
            self._fh.flush()

            if self.fsync_enabled:
                try:
                    os.fsync(self._fh.fileno())
                except Exception:
                    # No rompemos la app si fsync falla
                    pass

    def _tail_file(self, path: Path, max_lines: int = 50) -> List[str]:
        if max_lines <= 0:
            return []

        if not path.exists() or not path.is_file():
            return []

        try:
            with open(path, "r", encoding=self.encoding, errors="replace") as fh:
                tail: Deque[str] = deque(fh, maxlen=max_lines)
            return [line.rstrip("\n") for line in tail]
        except Exception:
            return []

    # -------------------------------------------------------------------------
    # Soporte para "with"
    # -------------------------------------------------------------------------

    def __enter__(self) -> "LogService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()