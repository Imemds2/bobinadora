import time

from app.controllers.machine.simulated_machine_controller import SimulatedMachineController


def print_snapshot(title: str, machine: SimulatedMachineController) -> None:
    snapshot = machine.get_snapshot()
    print(f"\n--- {title} ---")
    print(f"connected       : {snapshot.connected}")
    print(f"state           : {snapshot.state}")
    print(f"current_turns   : {snapshot.current_turns:.2f}")
    print(f"target_turns    : {snapshot.target_turns:.2f}")
    print(f"current_layer   : {snapshot.current_layer}")
    print(f"rpm             : {snapshot.rpm:.2f}")
    print(f"direction       : {snapshot.direction}")
    print(f"manual_mode     : {snapshot.manual_mode}")
    print(f"jog_active      : {snapshot.jog_active}")
    print(f"recipe_name     : {snapshot.recipe_name}")
    print(f"alarm_message   : {snapshot.alarm_message}")
    print(f"homing_remain_ms: {snapshot.homing_remaining_ms}")


def run_updates(machine: SimulatedMachineController, seconds: float, label: str) -> None:
    start = time.monotonic()

    while time.monotonic() - start < seconds:
        machine.update()
        snapshot = machine.get_snapshot()
        print(
            f"[{label}] state={snapshot.state:<12} "
            f"turns={snapshot.current_turns:>6.2f}/{snapshot.target_turns:<6.2f} "
            f"rpm={snapshot.rpm:>6.2f} "
            f"dir={snapshot.direction:<5} "
            f"alarm={snapshot.alarm_message or '-'}"
        )
        time.sleep(0.2)


def main() -> None:
    machine = SimulatedMachineController()

    print_snapshot("INITIAL", machine)

    print("\nConectando...")
    ok = machine.connect()
    print(f"connect() -> {ok}")
    print_snapshot("AFTER CONNECT", machine)

    print("\nIniciando trabajo de 10 vueltas...")
    ok = machine.start_job(target_turns=10, recipe_name="RECETA_PRUEBA")
    print(f"start_job() -> {ok}")
    run_updates(machine, seconds=2.0, label="RUN 1")
    print_snapshot("AFTER RUN 1", machine)

    print("\nPausando...")
    ok = machine.pause()
    print(f"pause() -> {ok}")
    print_snapshot("AFTER PAUSE", machine)

    print("\nEsperando un poco en pausa...")
    run_updates(machine, seconds=1.0, label="PAUSED")
    print_snapshot("AFTER PAUSED LOOP", machine)

    print("\nReanudando...")
    ok = machine.resume()
    print(f"resume() -> {ok}")
    run_updates(machine, seconds=3.5, label="RUN 2")
    print_snapshot("AFTER RUN 2", machine)

    print("\nProbando jog a la derecha...")
    ok = machine.jog_right()
    print(f"jog_right() -> {ok}")
    run_updates(machine, seconds=1.5, label="JOG RIGHT")
    print_snapshot("AFTER JOG RIGHT", machine)

    print("\nDeteniendo jog...")
    ok = machine.stop_jog()
    print(f"stop_jog() -> {ok}")
    print_snapshot("AFTER STOP JOG", machine)

    print("\nProbando home...")
    ok = machine.home()
    print(f"home() -> {ok}")
    run_updates(machine, seconds=2.5, label="HOMING")
    print_snapshot("AFTER HOME", machine)

    print("\nInyectando error...")
    ok = machine.inject_error("Error de prueba manual")
    print(f"inject_error() -> {ok}")
    print_snapshot("AFTER ERROR", machine)

    print("\nIntentando iniciar trabajo con error activo...")
    ok = machine.start_job(target_turns=5, recipe_name="NO_DEBERIA")
    print(f"start_job() -> {ok}")
    print_snapshot("AFTER FAILED START", machine)

    print("\nReseteando error...")
    ok = machine.reset_error()
    print(f"reset_error() -> {ok}")
    print_snapshot("AFTER RESET ERROR", machine)

    print("\nDesconectando...")
    machine.disconnect()
    print_snapshot("AFTER DISCONNECT", machine)


if __name__ == "__main__":
    main()