"""Exercise capability separation around the integrated MIN0 CORE FORTH loader."""

from __future__ import annotations

import json

from min0_core_forth_capability import (
    AuthorizationError,
    CapabilityError,
    LoaderAuthority,
    LoaderSession,
    PROFILE_MONITOR,
    PROFILE_PROVISIONER,
    PROFILE_RECOVERY,
    PROFILE_RUNTIME,
)
from min0_core_forth_image import IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY
from min0_core_forth_loader import LoaderError
from loader_state_demo import _fixtures, _loader


def _rejected(operation) -> bool:
    try:
        operation()
    except (CapabilityError, LoaderError):
        return True
    return False


def _sessions(loader):
    authority = LoaderAuthority(loader)
    return authority, {
        "runtime": authority.issue(PROFILE_RUNTIME, label="forth-runtime"),
        "monitor": authority.issue(PROFILE_MONITOR, label="update-monitor"),
        "monitor2": authority.issue(PROFILE_MONITOR, label="second-monitor"),
        "recovery": authority.issue(PROFILE_RECOVERY, label="recovery-console"),
        "provisioner": authority.issue(
            PROFILE_PROVISIONER, label="physical-provisioner"
        ),
    }


def _advance_to_key_overlap(sessions, packages) -> None:
    provisioner = sessions["provisioner"]
    provisioner.stage_root(packages["root2"])
    provisioner.commit_root()
    provisioner.stage_trust(packages["trust2"])
    provisioner.commit_trust()


def run_demo(implementation: str = "python") -> dict:
    fixture = _fixtures()
    packages = fixture["packages"]

    loader = _loader(fixture)
    authority, sessions = _sessions(loader)
    readable = {
        name: session.status()["phase"] == "stable"
        for name, session in sessions.items()
        if name != "monitor2"
    }

    denied = {
        "runtime_normal_update": _rejected(
            lambda: sessions["runtime"].stage_image(
                packages["normal2"], role=IMAGE_ROLE_NORMAL
            )
        ),
        "monitor_root_update": _rejected(
            lambda: sessions["monitor"].stage_root(packages["root2"])
        ),
        "monitor_trust_update": _rejected(
            lambda: sessions["monitor"].stage_trust(packages["trust2"])
        ),
        "monitor_recovery_update": _rejected(
            lambda: sessions["monitor"].stage_image(
                packages["recovery2"], role=IMAGE_ROLE_RECOVERY
            )
        ),
        "recovery_repair_while_normal": _rejected(
            lambda: sessions["recovery"].stage_image(
                packages["normal2"], role=IMAGE_ROLE_NORMAL
            )
        ),
        "recovery_trust_update": _rejected(
            lambda: sessions["recovery"].stage_trust(packages["trust2"])
        ),
        "profile_string_forgery": _rejected(
            lambda: authority.status(PROFILE_PROVISIONER)
        ),
        "unissued_session": _rejected(
            lambda: LoaderSession(authority, 999, "forged", object())
        ),
    }

    _advance_to_key_overlap(sessions, packages)
    normal_slot = sessions["monitor"].stage_image(
        packages["normal2"], role=IMAGE_ROLE_NORMAL
    )
    owner_visible = sessions["runtime"].status()["transaction_owner"]
    parallel_stage_rejected = _rejected(
        lambda: sessions["provisioner"].stage_root(packages["root3"])
    )
    cross_session_commit_rejected = _rejected(
        lambda: sessions["monitor2"].commit_image(
            IMAGE_ROLE_NORMAL, normal_slot
        )
    )
    wrong_slot_rejected = _rejected(
        lambda: sessions["monitor"].commit_image(IMAGE_ROLE_NORMAL, "A")
    )
    sessions["monitor"].commit_image(IMAGE_ROLE_NORMAL, normal_slot)

    recovery_update_by_monitor_rejected = _rejected(
        lambda: sessions["monitor"].stage_image(
            packages["recovery2"], role=IMAGE_ROLE_RECOVERY
        )
    )
    recovery_slot = sessions["provisioner"].stage_image(
        packages["recovery2"], role=IMAGE_ROLE_RECOVERY
    )
    sessions["provisioner"].commit_image(IMAGE_ROLE_RECOVERY, recovery_slot)

    revoked = authority.issue(PROFILE_RUNTIME, label="temporary-observer")
    authority.revoke(revoked)
    revoked_session_rejected = _rejected(revoked.status)

    recovery_loader = _loader(fixture)
    _recovery_authority, recovery_sessions = _sessions(recovery_loader)
    _advance_to_key_overlap(recovery_sessions, packages)
    recovery_loader.normal_store.slots["A"].marker = None
    monitor_blocked_in_recovery = _rejected(
        lambda: recovery_sessions["monitor"].stage_image(
            packages["normal2"], role=IMAGE_ROLE_NORMAL
        )
    )
    repaired_slot = recovery_sessions["recovery"].stage_image(
        packages["normal2"], role=IMAGE_ROLE_NORMAL
    )
    mode_after_stage = recovery_sessions["recovery"].select_boot()["mode"]
    recovery_sessions["recovery"].commit_image(IMAGE_ROLE_NORMAL, repaired_slot)
    repaired_boot = recovery_sessions["runtime"].select_boot()

    resume_loader = _loader(fixture)
    _old_authority, old_sessions = _sessions(resume_loader)
    _advance_to_key_overlap(old_sessions, packages)
    pending_slot = old_sessions["monitor"].stage_image(
        packages["normal2"], role=IMAGE_ROLE_NORMAL
    )
    restarted_authority, restarted_sessions = _sessions(resume_loader)
    runtime_adoption_rejected = _rejected(
        restarted_sessions["runtime"].adopt_pending
    )
    adoption = restarted_sessions["monitor"].adopt_pending()
    restarted_sessions["monitor"].commit_image(
        IMAGE_ROLE_NORMAL, pending_slot
    )

    return {
        "implementation": implementation,
        "permissions": {
            "runtime": ["inspect"],
            "monitor": ["inspect", "normal"],
            "recovery": ["inspect", "normal-in-recovery-mode"],
            "provisioner": ["inspect", "normal", "recovery", "trust", "root"],
        },
        "readable": readable,
        "denied": {
            **denied,
            "parallel_stage": parallel_stage_rejected,
            "cross_session_commit": cross_session_commit_rejected,
            "wrong_slot_commit": wrong_slot_rejected,
            "monitor_recovery_after_normal_update": recovery_update_by_monitor_rejected,
            "revoked_session": revoked_session_rejected,
            "monitor_in_recovery_mode": monitor_blocked_in_recovery,
            "runtime_pending_adoption": runtime_adoption_rejected,
        },
        "ownership": {
            "owner_visible": owner_visible,
            "normal_slot": normal_slot,
            "phase_after_commit": sessions["runtime"].status()["phase"],
        },
        "recovery_repair": {
            "slot": repaired_slot,
            "mode_after_stage": mode_after_stage,
            "final_mode": repaired_boot["mode"],
            "generation": repaired_boot["generation"],
        },
        "restart_adoption": {
            **adoption,
            "final_phase": restarted_sessions["runtime"].status()["phase"],
            "generation": restarted_sessions["runtime"].status()[
                "normal_generation"
            ],
        },
        "final": sessions["runtime"].status(),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
