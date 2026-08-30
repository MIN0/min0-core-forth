"""Show signed safe-runtime/standard-build image separation before slot writes."""

from __future__ import annotations

import copy
import json

from auth_comparison_demo import ED25519_TEST_SEED
from constructor_relocation_demo import collect_dictionary_relocations
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_image import (
    EXECUTION_PROFILE_SAFE_RUNTIME,
    EXECUTION_PROFILE_STANDARD_BUILD,
    IMAGE_ROLE_RECOVERY,
    ImageError,
    build_ed25519_image_envelope,
    validate_image_envelope,
)
from min0_core_forth_install import PersistentABStore, TransactionalInstaller
from min0_core_forth_linker import build_manifest
from min0_core_forth_outer import (
    DEFAULT_CODE_BASE,
    SOURCE_PROFILE_STANDARD_BUILD,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import MemoryRegion, Min0CoreForthVM, RegionMemory
from signed_image_demo import KEY_ID


BASES = {"code": 0x1000, "dictionary": 0x4000, "data": 0x8000}
LIMITS = {"code": 0x4000, "dictionary": 0x8000, "data": 0x10000}


def _build_candidate(*, standard_build: bool, generation: int, private_key):
    bus = RegionMemory(
        0x10000,
        [
            MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x8000, 0x8000, "rw"),
        ],
    )
    vm = Min0CoreForthVM(memory_bus=bus, allow_defer_store=standard_build)
    dictionary = RuntimeDictionary(
        vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x10000
    )
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
    if standard_build:
        outer.interpret(": SWITCH ['] NEW-ACTION IS ACTION ;")
    else:
        outer.interpret(": USE-ACTION ACTION ;")
    components = {
        "code": vm.read_bytes(DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE),
        "dictionary": dictionary.image(),
        "data": dictionary.body_image(),
    }
    allocator = {
        "code_here": outer.code_here,
        "header_here": dictionary.here,
        "data_here": dictionary.data_here,
        "latest": dictionary.latest,
    }
    records = outer.relocation_manifest() + collect_dictionary_relocations(vm, dictionary)
    envelope = build_ed25519_image_envelope(
        components,
        BASES,
        LIMITS,
        allocator,
        build_manifest(records),
        generation=generation,
        key_id=KEY_ID,
        private_key=private_key,
    )
    return components, envelope


def _rejected(operation) -> bool:
    try:
        operation()
    except ImageError:
        return True
    return False


def run_demo(implementation: str = "python") -> dict[str, object]:
    private_key = ed25519_private_from_seed(ED25519_TEST_SEED)
    trusted = {KEY_ID: ed25519_public_bytes(private_key)}
    safe_components, safe_envelope = _build_candidate(
        standard_build=False, generation=1, private_key=private_key
    )
    build_components, build_envelope = _build_candidate(
        standard_build=True, generation=2, private_key=private_key
    )
    validated_safe = validate_image_envelope(
        safe_components,
        safe_envelope,
        require_authentication=True,
        trusted_public_keys=trusted,
        runtime_profile=EXECUTION_PROFILE_SAFE_RUNTIME,
    )
    validated_build = validate_image_envelope(
        build_components,
        build_envelope,
        require_authentication=True,
        trusted_public_keys=trusted,
        runtime_profile=EXECUTION_PROFILE_STANDARD_BUILD,
    )

    store = PersistentABStore(safe_components, safe_envelope, 1)
    safe_installer = TransactionalInstaller(store, trusted)
    rejected_before_write = _rejected(
        lambda: safe_installer.install(build_components, build_envelope)
    )
    inactive_untouched = not store.slots["B"].components and store.slots["B"].envelope is None
    build_installer = TransactionalInstaller(
        store, trusted, runtime_profile=EXECUTION_PROFILE_STANDARD_BUILD
    )
    installed_slot = build_installer.install(build_components, build_envelope)

    profile_tamper = copy.deepcopy(build_envelope)
    profile_tamper["execution_profile"] = EXECUTION_PROFILE_SAFE_RUNTIME
    tamper_rejected = _rejected(
        lambda: validate_image_envelope(
            build_components,
            profile_tamper,
            require_authentication=True,
            trusted_public_keys=trusted,
            runtime_profile=EXECUTION_PROFILE_SAFE_RUNTIME,
        )
    )
    recovery_rejected = _rejected(
        lambda: build_ed25519_image_envelope(
            build_components,
            BASES,
            LIMITS,
            build_envelope["allocator"],
            build_envelope["manifest"],
            generation=2,
            key_id=KEY_ID,
            private_key=private_key,
            image_role=IMAGE_ROLE_RECOVERY,
        )
    )
    return {
        "implementation": implementation,
        "safe_image_profile": validated_safe["execution_profile"],
        "build_image_profile": validated_build["execution_profile"],
        "safe_verified_capabilities": validated_safe["code_verification"]["capabilities"],
        "build_verified_capabilities": validated_build["code_verification"]["capabilities"],
        "build_verified_instruction_count": validated_build["code_verification"]["instruction_count"],
        "build_has_defer_store_record": any(
            record["kind"] == "defer-store-slot"
            for record in build_envelope["manifest"]["records"]
        ),
        "safe_loader_rejected_before_write": rejected_before_write,
        "inactive_slot_untouched": inactive_untouched,
        "standard_build_installed_slot": installed_slot,
        "profile_tamper_rejected": tamper_rejected,
        "standard_build_recovery_rejected": recovery_rejected,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
