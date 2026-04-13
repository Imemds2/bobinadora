from app.controllers.machine.simulated_machine_controller import SimulatedMachineController
from app.controllers.machine.serial_machine_controller import SerialMachineController


def create_machine_controller(cfg: dict):
    backend = str(cfg.get("machine_backend", "simulated")).strip().lower()

    if backend == "simulated":
        return SimulatedMachineController()

    if backend == "serial":
        return SerialMachineController(cfg)

    raise ValueError(f"Backend de máquina no soportado: {backend}")