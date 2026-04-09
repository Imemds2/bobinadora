from dataclasses import dataclass
from typing import Optional


class MachineStates:
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    HOMING = "HOMING"
    ERROR = "ERROR"


class MachineDirections:
    STOP = "STOP"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


@dataclass
class MachineSnapshot:
    connected: bool = False
    state: str = MachineStates.DISCONNECTED

    current_turns: float = 0.0
    target_turns: float = 0.0
    current_layer: int = 0

    rpm: float = 0.0
    direction: str = MachineDirections.STOP

    manual_mode: bool = False
    jog_active: bool = False

    recipe_name: Optional[str] = None

    alarm_message: str = ""

    homing_remaining_ms: int = 0

    def has_error(self) -> bool:
        return self.state == MachineStates.ERROR

    def is_running(self) -> bool:
        return self.state == MachineStates.RUNNING

    def is_paused(self) -> bool:
        return self.state == MachineStates.PAUSED

    def is_connected_and_idle(self) -> bool:
        return self.connected and self.state == MachineStates.IDLE