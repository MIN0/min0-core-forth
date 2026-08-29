"""Exercise interpret-state DEFER, tick, IS, and ACTION-OF source syntax."""

from __future__ import annotations

import json

from min0_core_forth_dictionary import DictionaryError, RuntimeDictionary
from min0_core_forth_outer import CompileStateError, OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, UnassignedDefer


def _outer():
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


def _rejected(operation, errors) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict[str, object]:
    vm, dictionary, outer = _outer()
    outer.interpret(": OLD-ACTION 10 ; : NEW-ACTION 20 ; DEFER ACTION")
    unassigned_rejected = _rejected(
        lambda: outer.interpret("ACTION"), (UnassignedDefer,)
    )

    outer.interpret("' OLD-ACTION IS ACTION : USE-ACTION ACTION ; USE-ACTION")
    old_action = dictionary.find("OLD-ACTION")
    action = dictionary.find("ACTION")
    assert old_action is not None and action is not None
    first_value = vm.pop()
    outer.interpret("ACTION-OF ACTION")
    first_action_xt = vm.pop()

    outer.interpret("' NEW-ACTION IS ACTION USE-ACTION")
    new_action = dictionary.find("NEW-ACTION")
    assert new_action is not None
    second_value = vm.pop()
    outer.interpret("ACTION-OF ACTION")
    second_action_xt = vm.pop()

    relocation = next(
        record
        for record in outer.relocation_manifest()
        if record["kind"] == "defer-slot"
    )

    _bad_vm, bad_dictionary, bad_outer = _outer()
    bad_outer.interpret(": TARGET 1 ; DEFER D 7 CONSTANT NOT-COLON")
    non_colon_rejected = _rejected(
        lambda: bad_outer.interpret("' NOT-COLON IS D"), (DictionaryError,)
    )
    compile_rejected = _rejected(
        lambda: bad_outer.interpret(": BAD ['] TARGET IS D ;"),
        (CompileStateError,),
    )

    return {
        "implementation": implementation,
        "unassigned_rejected": unassigned_rejected,
        "first_value": first_value,
        "first_action_xt": first_action_xt,
        "old_xt": old_action.xt,
        "second_value": second_value,
        "second_action_xt": second_action_xt,
        "new_xt": new_action.xt,
        "defer_payload": dictionary.read_defer_target(action),
        "non_colon_rejected": non_colon_rejected,
        "compile_rejected": compile_rejected,
        "relocation": relocation,
    }


def main() -> None:
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
