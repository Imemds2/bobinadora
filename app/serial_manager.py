"""
Módulo de comunicación serial con ESP32
Maneja conexión, envío y recepción en hilo separado
Con pausa de STATUS durante carga de receta
"""
import serial
import serial.tools.list_ports
import threading
import time
from typing import Callable, Optional


class SerialManager:
    def __init__(self,
                 on_message: Callable,
                 on_status_change: Callable):
        self.ser: Optional[serial.Serial] = None
        self.on_message       = on_message
        self.on_status_change = on_status_change
        self.connected        = False
        self._read_thread: Optional[threading.Thread] = None
        self._running         = False
        self._send_lock       = threading.Lock()

    def get_ports(self) -> list:
        """Lista los puertos seriales disponibles."""
        try:
            return [p.device
                    for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def connect(self, port: str,
                baudrate: int = 115200) -> bool:
        """Conecta al puerto serial indicado."""
        try:
            # Cerrar conexión anterior si existe
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(
                port, baudrate,
                timeout=1,
                write_timeout=2)
            time.sleep(2)  # ESP32 necesita tiempo para reset

            self.connected = True
            self._running  = True

            self._read_thread = threading.Thread(
                target=self._read_loop,
                daemon=True,
                name="SerialReadLoop")
            self._read_thread.start()

            self.on_status_change(True, port)
            return True

        except serial.SerialException as e:
            self.on_status_change(False,
                                  f"Puerto ocupado: {e}")
            return False
        except Exception as e:
            self.on_status_change(False, str(e))
            return False

    def disconnect(self):
        """Cierra la conexión serial."""
        self._running  = False
        self.connected = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.on_status_change(False, "Desconectado")

    def send(self, cmd: str,
             timeout_ms: int = 500) -> list:
        """
        Envía un comando y espera la respuesta.
        Usa lock para evitar colisiones con el hilo de lectura.
        Retorna lista de líneas recibidas.
        """
        if not self.connected or not self.ser:
            return ["ERR:No conectado"]

        with self._send_lock:
            try:
                # Limpiar buffer antes de enviar
                self.ser.reset_input_buffer()

                # Enviar comando
                self.ser.write((cmd + "\n").encode("utf-8"))

                # Esperar respuesta con timeout dinámico
                resp       = []
                deadline   = time.time() + timeout_ms / 1000.0
                idle_since = None

                while time.time() < deadline:
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode(
                            errors="ignore").strip()
                        if line:
                            resp.append(line)
                            # Extender deadline si llega data
                            deadline   = time.time() + 0.15
                            idle_since = None
                    else:
                        if idle_since is None:
                            idle_since = time.time()
                        # Si llevamos 150ms sin data y ya
                        # tenemos al menos una respuesta, salir
                        elif (resp and
                              time.time() - idle_since > 0.15):
                            break
                        time.sleep(0.005)

                return resp

            except serial.SerialTimeoutException:
                return ["ERR:Timeout escritura"]
            except serial.SerialException as e:
                # Puerto desconectado físicamente
                self.connected = False
                self._running  = False
                try:
                    self.on_status_change(
                        False, f"Puerto desconectado: {e}")
                except Exception:
                    pass
                return [f"ERR:Puerto perdido:{e}"]
            except Exception as e:
                return [f"ERR:{e}"]

    def _read_loop(self):
        """
        Hilo de lectura continua para mensajes espontáneos
        del ESP32 (STATUS periódico, alertas, etc).
        Solo lee cuando send() no está activo.
        """
        while self._running:
            try:
                if not self.ser or not self.ser.is_open:
                    break

                # No leer mientras send() tiene el lock
                if self._send_lock.locked():
                    time.sleep(0.01)
                    continue

                if self.ser.in_waiting:
                    line = self.ser.readline().decode(
                        errors="ignore").strip()
                    if line:
                        try:
                            self.on_message(line)
                        except Exception as e:
                            print(f"[serial] callback "
                                  f"error: {e}")
                else:
                    time.sleep(0.02)

            except serial.SerialException:
                # Puerto desconectado físicamente
                if self.connected:
                    self.connected = False
                    self._running  = False
                    try:
                        self.on_status_change(
                            False,
                            "Puerto desconectado")
                    except Exception:
                        pass
                break
            except Exception as e:
                print(f"[serial] _read_loop error: {e}")
                time.sleep(0.1)

        print("[serial] Hilo de lectura terminado")