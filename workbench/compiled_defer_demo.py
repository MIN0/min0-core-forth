"""Compare safe-runtime and standard-build compile-state DEFER semantics."""

from __future__ import annotations

import json

from min0_core_forth_control import MonitorControlAuthority
from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    CompileStateError,
    OuterInterpreter,
    OuterInterpreterError,
    SOURCE_PROFILE_STANDARD_BUILD,
    install_core_primitives,
)
from min0_core_forth_vm import DeferStoreDenied, Min0CoreForthVM


def _system(*, standard_build: bool = False):
    vm = Min0CoreForthVM(allow_defer_store=standard_build)
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    options = (
        {"source_profile": SOURCE_PROFILE_STANDARD_BUILD}
        if standard_build
        else {}
    )
    outer = OuterInterpreter(vm, dictionary, **options)
    outer.interpret(
        ": OLD-ACTION 10 ; : NEW-ACTION 20 ; "
        "DEFER ACTION ' OLD-ACTION IS ACTION"
    )
    return vm, dictionary, outer


def _rejected(operation, errors) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def _monitor_disables_compiled_is() -> tuple[bool, bool]:
    vm, dictionary, outer = _system(standard_build=True)
    outer.interpret(": SWITCH ['] NEW-ACTION IS ACTION ;")
    deferred = dictionary.find("ACTION")
    assert deferred is not None
    before = dictionary.read_defer_target(deferred)
    MonitorControlAuthority(vm, dictionary)
    denied = _rejected(lambda: outer.interpret("SWITCH"), (DeferStoreDenied,))
    unchanged = dictionary.read_defer_target(deferred) == before
    return denied, unchanged


def run_demo(implementation: str = "python") -> dict[str, object]:
    safe_vm, safe_dictionary, safe_outer = _system()
    safe_outer.interpret(": XT-OF-NEW ['] NEW-ACTION ;")
    safe_outer.interpret(": CURRENT-ACTION ACTION-OF ACTION ;")
    new_action = safe_dictionary.find("NEW-ACTION")
    old_action = safe_dictionary.find("OLD-ACTION")
    action = safe_dictionary.find("ACTION")
    assert new_action is not None and old_action is not None and action is not None
    safe_outer.interpret("XT-OF-NEW CURRENT-ACTION")
    safe_current_xt = safe_vm.pop()
    safe_literal_xt = safe_vm.pop()
    safe_compiled_is_rejected = _rejected(
        lambda: safe_outer.interpret(": FORBIDDEN ['] NEW-ACTION IS ACTION ;"),
        (CompileStateError,),
    )
    safe_target_unchanged = safe_dictionary.read_defer_target(action) == old_action.xt
    safe_relocations = {
        record["kind"]: record
        for record in safe_outer.relocation_manifest()
        if record["kind"] in ("xt-literal", "action-of-slot")
    }

    build_vm, build_dictionary, build_outer = _system(standard_build=True)
    build_outer.interpret(
        ": USE-ACTION ACTION ; "
        ": SWITCH ['] NEW-ACTION IS ACTION ;"
    )
    build_outer.interpret("USE-ACTION")
    before_switch = build_vm.pop()
    build_outer.interpret("SWITCH USE-ACTION")
    after_switch = build_vm.pop()
    build_action = build_dictionary.find("ACTION")
    build_new = build_dictionary.find("NEW-ACTION")
    assert build_action is not None and build_new is not None
    build_target_xt = build_dictionary.read_defer_target(build_action)
    store_relocation = next(
        record
        for record in build_outer.relocation_manifest()
        if record["kind"] == "defer-store-slot"
    )

    wrong_vm = Min0CoreForthVM()
    wrong_dictionary = RuntimeDictionary(wrong_vm)
    profile_requires_build_vm = _rejected(
        lambda: OuterInterpreter(
            wrong_vm,
            wrong_dictionary,
            source_profile=SOURCE_PROFILE_STANDARD_BUILD,
        ),
        (OuterInterpreterError,),
    )
    monitor_denied, monitor_target_unchanged = _monitor_disables_compiled_is()

    return {
        "implementation": implementation,
        "safe_literal_xt": safe_literal_xt,
        "safe_new_xt": new_action.xt,
        "safe_current_xt": safe_current_xt,
        "safe_old_xt": old_action.xt,
        "safe_compiled_is_rejected": safe_compiled_is_rejected,
        "safe_target_unchanged": safe_target_unchanged,
        "safe_relocations": safe_relocations,
        "build_before_switch": before_switch,
        "build_after_switch": after_switch,
        "build_target_xt": build_target_xt,
        "build_new_xt": build_new.xt,
        "store_relocation": store_relocation,
        "profile_requires_build_vm": profile_requires_build_vm,
        "monitor_denied_compiled_is": monitor_denied,
        "monitor_target_unchanged": monitor_target_unchanged,
    }


def main() -> None:
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
