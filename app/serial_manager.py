"""
Módulo de comunicación serial con STM32
Maneja conexión, envío y recepción en hilo separado.

La conexión solo se considera válida si:
1. El puerto abre correctamente.
2. El controlador responde PING -> PONG.
"""

import serial
import serial.tools.list_ports
import threading
import time
from typing import Callable, Optional


class SerialManager:
    def __init__(
        self,
        on_message: Callable,
        on_status_change: Callable,
    ):
        self.ser: Optional[serial.Serial] = None
        self.on_message = on_message
        self.on_status_change = on_status_change
        self.connected = False
        self._read_thread: Optional[threading.Thread] = None
        self._running = False
        self._send_lock = threading.Lock()

    def get_ports(self) -> list:
        """Lista los puertos seriales disponibles."""
        try:
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """
        Conecta al puerto serial indicado.

        Importante:
        Abrir el puerto NO significa que la STM32 esté viva.
        Por eso se hace handshake con PING/PONG antes de marcar conectado.
        """
        try:
            self.disconnect_silent()

            self.ser = serial.Serial(
                port,
                baudrate,
                timeout=1,
                write_timeout=2,
            )

            # Tiempo para estabilizar UART / posible reset del adaptador.
            time.sleep(1.5)

            if not self._probe_controller_alive():
                self.disconnect_silent()
                self.on_status_change(
                    False,
                    f"{port} abierto, pero STM32 no responde PING",
                )
                return False

            self.connected = True
            self._running = True

            self._read_thread = threading.Thread(
                target=self._read_loop,
                daemon=True,
                name="SerialReadLoop",
            )
            self._read_thread.start()

            self.on_status_change(True, port)
            return True

        except serial.SerialException as e:
            self.disconnect_silent()
            self.on_status_change(False, f"Puerto ocupado/no disponible: {e}")
            return False

        except Exception as e:
            self.disconnect_silent()
            self.on_status_change(False, str(e))
            return False

    def disconnect_silent(self) -> None:
        """
        Cierra el puerto sin notificar a la UI.
        Útil durante intentos de conexión fallidos.
        """
        self._running = False
        self.connected = False

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

        self.ser = None

    def disconnect(self):
        """Cierra la conexión serial y notifica a la UI."""
        self.disconnect_silent()
        self.on_status_change(False, "Desconectado")

    def _probe_controller_alive(self) -> bool:
        """
        Verifica que la STM32 esté viva.
        Envía PING y espera PONG.

        Se ejecuta antes de arrancar el hilo de lectura.
        """
        if not self.ser or not self.ser.is_open:
            return False

        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            self.ser.write(b"PING\r\n")
            self.ser.flush()

            deadline = time.time() + 2.0

            while time.time() < deadline:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode(errors="ignore").strip()

                    if not line:
                        continue

                    # Ignorar basura de arranque, caracteres raros, etc.
                    if "PONG" in line:
                        return True

                time.sleep(0.02)

            return False

        except Exception:
            return False

    def _resolve_timeout_ms(self, cmd: str, timeout_ms: int) -> int:
        """
        Algunos comandos tardan más porque la STM32 ejecuta movimiento físico.
        Si dejamos 500 ms, la respuesta llega después y puede mezclarse con STATUS.
        """
        clean = str(cmd or "").strip().upper()

        if clean.startswith("HOMING"):
            return max(timeout_ms, 120000)

        if clean.startswith("JOGMM_X100"):
            return max(timeout_ms, 60000)

        if clean.startswith("STOP"):
            return max(timeout_ms, 1500)

        if clean.startswith("SYNC_RESET"):
            return max(timeout_ms, 1500)

        if clean.startswith("SYNC_ON") or clean.startswith("SYNC_OFF"):
            return max(timeout_ms, 1500)

        return timeout_ms

    def send(self, cmd: str, timeout_ms: int = 500) -> list:
        timeout_ms = self._resolve_timeout_ms(cmd, timeout_ms)
        """
        Envía un comando y espera respuesta.

        Nota:
        Algunos comandos bloqueantes como HOMING o JOGMM grandes pueden
        responder después de que este timeout termine. En esos casos el hilo
        de lectura continua seguirá capturando las líneas posteriores.
        """
        if not self.connected or not self.ser or not self.ser.is_open:
            return ["ERR:No conectado"]

        with self._send_lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write((cmd + "\r\n").encode("utf-8"))
                self.ser.flush()

                resp = []
                deadline = time.time() + timeout_ms / 1000.0
                idle_since = None

                while time.time() < deadline:
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode(errors="ignore").strip()

                        if line:
                            resp.append(line)
                            deadline = time.time() + 0.15
                            idle_since = None
                    else:
                        if idle_since is None:
                            idle_since = time.time()
                        elif resp and time.time() - idle_since > 0.15:
                            break

                        time.sleep(0.005)

                return resp

            except serial.SerialTimeoutException:
                return ["ERR:Timeout escritura"]

            except serial.SerialException as e:
                self.connected = False
                self._running = False

                try:
                    self.on_status_change(False, f"Puerto desconectado: {e}")
                except Exception:
                    pass

                return [f"ERR:Puerto perdido:{e}"]

            except Exception as e:
                return [f"ERR:{e}"]

    def _read_loop(self):
        """
        Hilo de lectura continua para mensajes espontáneos:
        STATUS, OK:HOMING, OK:JOGMM, errores, etc.
        """
        while self._running:
            try:
                if not self.ser or not self.ser.is_open:
                    break

                if self._send_lock.locked():
                    time.sleep(0.01)
                    continue

                if self.ser.in_waiting:
                    line = self.ser.readline().decode(errors="ignore").strip()

                    if line:
                        try:
                            self.on_message(line)
                        except Exception as e:
                            print(f"[serial] callback error: {e}")
                else:
                    time.sleep(0.02)

            except serial.SerialException:
                if self.connected:
                    self.connected = False
                    self._running = False

                    try:
                        self.on_status_change(False, "Puerto desconectado")
                    except Exception:
                        pass

                break

            except Exception as e:
                print(f"[serial] _read_loop error: {e}")
                time.sleep(0.1)

        print("[serial] Hilo de lectura terminado")