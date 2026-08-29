"""Executable audit of current MIN0 CORE FORTH security controls and gaps."""

from __future__ import annotations

import copy
import json

from constructor_image_fixture import make_system
from min0_core_forth_image import (
    ImageError,
    build_image_envelope,
    validate_image_envelope,
)
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import StepLimitExceeded
from image_envelope_demo import (
    SOURCE_BASES,
    SOURCE_LIMITS,
    build_source_image,
)


def _scenario(threat_id: str, name: str, result: str, status: str) -> dict[str, str]:
    return {"id": threat_id, "scenario": name, "result": result, "status": status}


def run_demo(implementation: str = "python") -> dict:
    components, envelope = build_source_image()

    corrupted = dict(components)
    corrupted_code = bytearray(corrupted["code"])
    corrupted_code[-1] = 0  # Valid NOP: altered semantics, still valid bytecode.
    corrupted["code"] = bytes(corrupted_code)
    try:
        validate_image_envelope(corrupted, envelope)
    except ImageError:
        corruption = "blocked"
    else:
        corruption = "accepted"

    manifest_tamper = copy.deepcopy(envelope)
    manifest_tamper["manifest"]["records"][0]["kind"] += "-tampered"
    try:
        validate_image_envelope(components, manifest_tamper)
    except ImageError:
        manifest_result = "blocked"
    else:
        manifest_result = "accepted"

    rebuilt_envelope = build_image_envelope(
        corrupted,
        SOURCE_BASES,
        SOURCE_LIMITS,
        envelope["allocator"],
        envelope["manifest"],
        generation=envelope["generation"],
    )
    validate_image_envelope(corrupted, rebuilt_envelope)
    malicious_development = "accepted"
    try:
        validate_image_envelope(
            corrupted, rebuilt_envelope, require_authentication=True
        )
    except ImageError:
        malicious_authenticated = "blocked"
    else:
        malicious_authenticated = "accepted"

    old_components, old_envelope = build_source_image(envelope["generation"] - 1)
    try:
        validate_image_envelope(
            old_components,
            old_envelope,
            minimum_generation=envelope["generation"],
        )
    except ImageError:
        rollback_result = "blocked"
    else:
        rollback_result = "accepted"

    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(": FOREVER BEGIN AGAIN ;")
    forever = dictionary.find("FOREVER")
    assert forever is not None
    try:
        vm.resume(forever.payload, return_to=outer.return_trampoline, max_steps=20)
    except StepLimitExceeded:
        execution_limit = "blocked"
    else:
        execution_limit = "accepted"

    scenarios = [
        _scenario("T01", "component-corruption", corruption, "controlled"),
        _scenario("T02", "manifest-tamper", manifest_result, "controlled"),
        _scenario(
            "T03", "malicious-rebuild-development", malicious_development, "gap"
        ),
        _scenario(
            "T04",
            "malicious-rebuild-authentication-required",
            malicious_authenticated,
            "policy-boundary",
        ),
        _scenario("T05", "rollback-old-valid-image", rollback_result, "controlled"),
        _scenario("T06", "infinite-execution", execution_limit, "controlled"),
    ]
    return {
        "implementation": implementation,
        "authentication": envelope["authentication"]["scheme"],
        "generation_present": "generation" in envelope,
        "scenarios": scenarios,
        "controlled": sum(item["status"] == "controlled" for item in scenarios),
        "gaps": [item["id"] for item in scenarios if item["status"] == "gap"],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
