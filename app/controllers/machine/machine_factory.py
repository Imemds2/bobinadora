from app.controllers.machine.simulated_machine_controller import SimulatedMachineController


def create_machine_controller(cfg: dict):
    backend = str(cfg.get("machine_backend", "simulated")).strip().lower()

    if backend == "simulated":
        return SimulatedMachineController()

    if backend == "serial":
        raise NotImplementedError(
            "SerialMachineController aún no está implementado"
        )

    raise ValueError(f"Backend de máquina no soportado: {backend}")