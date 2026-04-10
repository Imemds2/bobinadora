import time

from app.controllers.machine.machine_interface import MachineInterface
from app.services.machine_state import (
    MachineDirections,
    MachineSnapshot,
    MachineStates,
)


class SimulatedMachineController(MachineInterface):
    def __init__(self) -> None:
        self.snapshot = MachineSnapshot()
        self._last_update = time.monotonic()
        self._turns_per_second = 2.0
        self._homing_duration_ms = 2000

    def connect(self) -> bool:
        if self.snapshot.connected:
            return True

        self.snapshot.connected = True
        self.snapshot.state = MachineStates.IDLE
        self.snapshot.alarm_message = ""
        self.snapshot.direction = MachineDirections.STOP
        self._last_update = time.monotonic()
        return True

    def disconnect(self) -> None:
        self.snapshot.connected = False
        self.snapshot.state = MachineStates.DISCONNECTED
        self.snapshot.current_turns = 0.0
        self.snapshot.target_turns = 0.0
        self.snapshot.current_layer = 0
        self.snapshot.position_mm = 0.0
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        self.snapshot.jog_active = False
        self.snapshot.manual_mode = False
        self.snapshot.recipe_name = None
        self.snapshot.alarm_message = ""
        self.snapshot.homing_remaining_ms = 0

    def update(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now

        if not self.snapshot.connected:
            return

        if self.snapshot.state == MachineStates.RUNNING:
            self.snapshot.current_turns += self._turns_per_second * elapsed
            self.snapshot.rpm = self._turns_per_second * 60.0
            self.snapshot.direction = MachineDirections.RIGHT

            if self.snapshot.current_turns >= self.snapshot.target_turns:
                self.snapshot.current_turns = self.snapshot.target_turns
                self.snapshot.state = MachineStates.IDLE
                self.snapshot.rpm = 0.0
                self.snapshot.direction = MachineDirections.STOP

        elif self.snapshot.state == MachineStates.HOMING:
            elapsed_ms = int(elapsed * 1000)
            self.snapshot.homing_remaining_ms = max(
                0,
                self.snapshot.homing_remaining_ms - elapsed_ms
            )

            if self.snapshot.homing_remaining_ms == 0:
                self.snapshot.state = MachineStates.IDLE
                self.snapshot.position_mm = 0.0
                self.snapshot.rpm = 0.0
                self.snapshot.direction = MachineDirections.STOP

        elif self.snapshot.jog_active:
            jog_speed_mm_per_sec = 5.0
            delta_mm = jog_speed_mm_per_sec * elapsed

            if self.snapshot.direction == MachineDirections.LEFT:
                self.snapshot.position_mm = max(0.0, self.snapshot.position_mm - delta_mm)
            elif self.snapshot.direction == MachineDirections.RIGHT:
                self.snapshot.position_mm += delta_mm

            self.snapshot.rpm = 0.0

        else:
            self.snapshot.rpm = 0.0
            if self.snapshot.state != MachineStates.ERROR:
                self.snapshot.direction = MachineDirections.STOP

    def get_snapshot(self) -> MachineSnapshot:
        return self.snapshot

    def start_job(self, target_turns: float, recipe_name: str | None = None) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state != MachineStates.IDLE:
            return False

        if target_turns <= 0:
            return False

        self.snapshot.state = MachineStates.RUNNING
        self.snapshot.current_turns = 0.0
        self.snapshot.target_turns = target_turns
        self.snapshot.recipe_name = recipe_name
        self.snapshot.alarm_message = ""
        self.snapshot.manual_mode = False
        self.snapshot.jog_active = False
        self.snapshot.direction = MachineDirections.RIGHT
        self._last_update = time.monotonic()
        return True

    def pause(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state != MachineStates.RUNNING:
            return False

        self.snapshot.state = MachineStates.PAUSED
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        return True

    def resume(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state != MachineStates.PAUSED:
            return False

        self.snapshot.state = MachineStates.RUNNING
        self._last_update = time.monotonic()
        return True

    def stop(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state not in (
            MachineStates.RUNNING,
            MachineStates.PAUSED,
            MachineStates.HOMING,
        ):
            return False

        self.snapshot.state = MachineStates.IDLE
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        self.snapshot.jog_active = False
        self.snapshot.homing_remaining_ms = 0
        return True
    
    def reset(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state == MachineStates.RUNNING:
            return False

        self.snapshot.current_turns = 0.0
        self.snapshot.target_turns = 0.0
        self.snapshot.current_layer = 0
        self.snapshot.recipe_name = None
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        self.snapshot.jog_active = False

        return True
    
    def set_manual_mode(self, enabled: bool) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state in (MachineStates.RUNNING, MachineStates.HOMING, MachineStates.ERROR):
            return False

        self.snapshot.manual_mode = enabled

        if not enabled:
            self.snapshot.jog_active = False
            self.snapshot.rpm = 0.0
            self.snapshot.direction = MachineDirections.STOP

        return True

    def home(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state in (MachineStates.RUNNING, MachineStates.ERROR):
            return False

        self.snapshot.state = MachineStates.HOMING
        self.snapshot.homing_remaining_ms = self._homing_duration_ms
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.LEFT
        self.snapshot.jog_active = False
        self._last_update = time.monotonic()
        return True

    def jog_left(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state not in (MachineStates.IDLE, MachineStates.PAUSED):
            return False

        if not self.snapshot.manual_mode:
            return False

        self.snapshot.jog_active = True
        self.snapshot.direction = MachineDirections.LEFT
        return True

    def jog_right(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state not in (MachineStates.IDLE, MachineStates.PAUSED):
            return False

        if not self.snapshot.manual_mode:
            return False

        self.snapshot.jog_active = True
        self.snapshot.direction = MachineDirections.RIGHT
        return True
    
    def jog_step(self, direction: str, distance_mm: float) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state not in (MachineStates.IDLE, MachineStates.PAUSED):
            return False

        if not self.snapshot.manual_mode:
            return False

        if distance_mm <= 0:
            return False

        direction = direction.lower().strip()

        if direction == "left":
            self.snapshot.position_mm = max(0.0, self.snapshot.position_mm - distance_mm)
            self.snapshot.direction = MachineDirections.LEFT
        elif direction == "right":
            self.snapshot.position_mm += distance_mm
            self.snapshot.direction = MachineDirections.RIGHT
        else:
            return False

        self.snapshot.rpm = 0.0
        self.snapshot.jog_active = False
        return True

    def stop_jog(self) -> bool:
        if not self.snapshot.connected:
            return False

        if not self.snapshot.jog_active:
            return False

        self.snapshot.jog_active = False
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        return True

    def reset_error(self) -> bool:
        if not self.snapshot.connected:
            return False

        if self.snapshot.state != MachineStates.ERROR:
            return False

        self.snapshot.state = MachineStates.IDLE
        self.snapshot.alarm_message = ""
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        self.snapshot.jog_active = False
        self.snapshot.homing_remaining_ms = 0
        return True

    def inject_error(self, message: str) -> bool:
        if not self.snapshot.connected:
            return False

        self.snapshot.state = MachineStates.ERROR
        self.snapshot.alarm_message = message.strip() or "Simulated error"
        self.snapshot.rpm = 0.0
        self.snapshot.direction = MachineDirections.STOP
        self.snapshot.jog_active = False
        self.snapshot.homing_remaining_ms = 0
        return True