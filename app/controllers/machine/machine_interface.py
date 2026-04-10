from abc import ABC, abstractmethod

from app.services.machine_state import MachineSnapshot


class MachineInterface(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Intenta conectar con la máquina. Regresa True si conecta."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Desconecta la máquina o cierra la sesión actual."""
        raise NotImplementedError

    @abstractmethod
    def update(self) -> None:
        """
        Actualiza el estado interno de la máquina.
        En el simulador avanzará tiempo; en el real leerá/parsing de eventos.
        """
        raise NotImplementedError

    @abstractmethod
    def get_snapshot(self) -> MachineSnapshot:
        """Devuelve una copia o referencia del estado actual de la máquina."""
        raise NotImplementedError

    @abstractmethod
    def start_job(self, target_turns: float, recipe_name: str | None = None) -> bool:
        """Inicia un trabajo con una meta de vueltas."""
        raise NotImplementedError

    @abstractmethod
    def pause(self) -> bool:
        """Pausa el trabajo actual."""
        raise NotImplementedError

    @abstractmethod
    def resume(self) -> bool:
        """Reanuda un trabajo pausado."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> bool:
        """Detiene el trabajo actual."""
        raise NotImplementedError
    
    @abstractmethod
    def reset(self) -> bool:
        """Resetea el trabajo/contador en el estado permitido."""
        raise NotImplementedError

    @abstractmethod
    def set_manual_mode(self, enabled: bool) -> bool:
        """Activa o desactiva el modo manual persistente."""
        raise NotImplementedError

    @abstractmethod
    def home(self) -> bool:
        """Inicia el proceso de homing."""
        raise NotImplementedError

    @abstractmethod
    def jog_left(self) -> bool:
        """Inicia movimiento manual hacia la izquierda."""
        raise NotImplementedError

    @abstractmethod
    def jog_right(self) -> bool:
        """Inicia movimiento manual hacia la derecha."""
        raise NotImplementedError
    
    @abstractmethod
    def jog_step(self, direction: str, distance_mm: float) -> bool:
        """Realiza un desplazamiento puntual en modo manual."""
        raise NotImplementedError

    @abstractmethod
    def stop_jog(self) -> bool:
        """Detiene el movimiento manual."""
        raise NotImplementedError

    @abstractmethod
    def reset_error(self) -> bool:
        """Limpia un estado de error si aplica."""
        raise NotImplementedError

    @abstractmethod
    def inject_error(self, message: str) -> bool:
        """Fuerza un error. Útil para simulación y pruebas."""
        raise NotImplementedError