"""Compile and execute dot-quote through the verified terminal service."""

from __future__ import annotations

import json

from constructor_image_fixture import make_system
from min0_core_forth_linker import build_manifest
from min0_core_forth_outer import (
    DEFAULT_CODE_BASE,
    TERMINAL_TYPE_SERVICE_ID,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_verify import verify_image_bytecode
from min0_core_forth_vm import ServiceRegistrySealed


def run_demo(implementation: str = "python") -> dict[str, object]:
    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(': HELLO ." Hello" ;')
    outer.interpret(': GREET HELLO ."  Service" ;')
    components = {
        "code": vm.read_bytes(DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE),
        "dictionary": dictionary.image(),
        "data": dictionary.body_image(),
    }
    bases = {
        "code": DEFAULT_CODE_BASE,
        "dictionary": dictionary.base,
        "data": dictionary.body_base,
    }
    verification = verify_image_bytecode(
        components, bases, build_manifest(outer.relocation_manifest())
    )
    vm.memory.seal_read_only_region("DATA")
    vm.seal_verified_execution(
        verification, extra_entries=outer.execution_extra_entries()
    )
    stack = outer.interpret("GREET")
    try:
        vm.register_service(2, lambda: None)
    except ServiceRegistrySealed:
        late_registration_rejected = True
    else:
        late_registration_rejected = False
    data_region = next(region for region in vm.memory.regions if region.name == "DATA")
    code_region = next(region for region in vm.memory.regions if region.name == "CODE")
    return {
        "implementation": implementation,
        "service_id": TERMINAL_TYPE_SERVICE_ID,
        "service_ids": verification["service_ids"],
        "service_addresses": verification["service_addresses"],
        "registered_service_ids": list(vm.registered_service_ids()),
        "registry_sealed": vm.service_registry_sealed,
        "late_registration_rejected": late_registration_rejected,
        "stack": stack,
        "output": list(outer.output),
        "terminal_text": outer.terminal_text,
        "code_permissions": code_region.permissions,
        "data_permissions": data_region.permissions,
        "code_here": outer.code_here,
        "relocation_kinds": [
            record["kind"] for record in outer.relocation_manifest()
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
