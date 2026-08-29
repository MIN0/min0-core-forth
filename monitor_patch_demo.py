"""Pause, inspect, switch one DEFER target, and resume safely."""

from __future__ import annotations

import json

from min0_core_forth_control import (
    ControlError,
    ControlInvariantError,
    MonitorControlAuthority,
    PROFILE_MONITOR,
    PROFILE_OBSERVER,
)
from min0_core_forth_dictionary import DictionaryError, RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Assembler, Min0CoreForthVM, Op


def _system():
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(": OLD-SERVICE 10 ; : NEW-SERVICE 20 ;")
    old_service = dictionary.find("OLD-SERVICE")
    assert old_service is not None
    dictionary.add_defer("SERVICE", old_service)
    outer.interpret(": APPLICATION SERVICE ;")
    dictionary.add_constant("NOT-CODE", 7)
    application = dictionary.find("APPLICATION")
    assert application is not None

    wrapper = Assembler()
    wrapper.emit(Op.CALL, application.payload)
    wrapper.emit(Op.CALL, application.payload)
    wrapper.emit(Op.HALT)
    vm.load(wrapper.build(), 0x200)
    return vm, dictionary, outer


def _rejected(operation) -> bool:
    try:
        operation()
    except (ControlError, DictionaryError, ValueError):
        return True
    return False


def _tamper_rejected() -> bool:
    vm, dictionary, _outer = _system()
    authority = MonitorControlAuthority(vm, dictionary)
    monitor = authority.issue(PROFILE_MONITOR)
    monitor.request_pause()
    monitor.run_slice(budget=10)
    vm.data_stack.append(0xBAD)
    try:
        monitor.run_slice(budget=1)
    except ControlInvariantError:
        return True
    return False


def _ordinary_source_switch_rejected() -> bool:
    vm, dictionary, outer = _system()
    authority = MonitorControlAuthority(vm, dictionary)
    monitor = authority.issue(PROFILE_MONITOR)
    deferred = dictionary.find("SERVICE")
    assert deferred is not None
    before = dictionary.read_defer_target(deferred)
    rejected = _rejected(
        lambda: outer.interpret("' NEW-SERVICE IS SERVICE")
    )
    unchanged = dictionary.read_defer_target(deferred) == before
    invariant_blocked = _rejected(lambda: monitor.run_slice(budget=1))
    return rejected and unchanged and invariant_blocked


def run_demo(implementation: str = "python") -> dict[str, object]:
    vm, dictionary, outer = _system()
    authority = MonitorControlAuthority(vm, dictionary)
    observer = authority.issue(PROFILE_OBSERVER, label="viewer")
    monitor = authority.issue(PROFILE_MONITOR, label="authenticated-monitor")

    def stop_between_calls(point) -> None:
        if point.slice_steps == 5:
            monitor.request_pause()

    first = monitor.run_slice(budget=30, on_safe_point=stop_between_calls)
    inspection = observer.inspect_paused()
    service_before = next(
        item for item in inspection["dictionary"] if item["name"] == "SERVICE"
    )
    copied_stack = inspection["data_stack"]
    copied_stack.append(999)  # returned observation must not alias the VM stack
    snapshot_copy_isolated = vm.data_stack == [10]

    denied = {
        "observer_switch": _rejected(
            lambda: observer.apply_forth_control("' NEW-SERVICE IS SERVICE")
        ),
        "non_defer_source": _rejected(
            lambda: monitor.switch_defer("OLD-SERVICE", "NEW-SERVICE")
        ),
        "non_colon_target": _rejected(
            lambda: monitor.switch_defer("SERVICE", "NOT-CODE")
        ),
        "out_of_band_stack_tamper": _tamper_rejected(),
        "ordinary_source_after_lock": _ordinary_source_switch_rejected(),
    }
    audit = monitor.apply_forth_control("' NEW-SERVICE IS SERVICE")
    action_of = observer.apply_forth_control("ACTION-OF SERVICE")
    inspection_after = observer.inspect_paused()
    service_after = next(
        item for item in inspection_after["dictionary"] if item["name"] == "SERVICE"
    )
    final = monitor.run_slice(budget=30)
    defer_relocation = next(
        record
        for record in outer.relocation_manifest()
        if record["kind"] == "defer-slot"
    )

    return {
        "implementation": implementation,
        "first": first.as_dict(),
        "service_before": service_before,
        "snapshot_copy_isolated": snapshot_copy_isolated,
        "denied": denied,
        "audit": audit,
        "action_of": action_of,
        "service_after": service_after,
        "final": final.as_dict(),
        "final_stack": list(vm.data_stack),
        "audit_visible_to_observer": inspection_after["audit"],
        "defer_relocation": defer_relocation,
    }


def main() -> None:
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
