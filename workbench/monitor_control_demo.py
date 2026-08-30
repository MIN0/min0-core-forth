"""Deterministic safe-point, budget, and watchdog demonstration."""

from __future__ import annotations

import json

from min0_core_forth_control import (
    ControlError,
    ControlSession,
    MonitorControlAuthority,
    PROFILE_MONITOR,
    PROFILE_OBSERVER,
)
from min0_core_forth_vm import Assembler, Min0CoreForthVM, Op


def _program() -> bytes:
    asm = Assembler()
    asm.emit(Op.LIT, 1)
    asm.emit(Op.LIT, 2)
    asm.emit(Op.ADD)
    asm.emit(Op.NOP)
    asm.emit(Op.NOP)
    asm.emit(Op.HALT)
    return asm.build()


def _rejected(operation) -> bool:
    try:
        operation()
    except (ControlError, ValueError):
        return True
    return False


def run_demo(implementation: str = "python") -> dict[str, object]:
    vm = Min0CoreForthVM()
    vm.load(_program())
    authority = MonitorControlAuthority(vm)
    observer = authority.issue(PROFILE_OBSERVER, label="viewer")
    monitor = authority.issue(PROFILE_MONITOR, label="authenticated-monitor")

    forged_session_rejected = _rejected(
        lambda: ControlSession(authority, 999, "forged", object())
    )
    denied = {
        "observer_pause": _rejected(observer.request_pause),
        "observer_run": _rejected(lambda: observer.run_slice(budget=1)),
        "profile_string": _rejected(lambda: authority.status(PROFILE_MONITOR)),
        "forged_session": forged_session_rejected,
    }

    pause_points: list[dict[str, object]] = []

    def request_after_add(point) -> None:
        pause_points.append(
            {
                "slice_steps": point.slice_steps,
                "ip": point.ip,
                "data_stack": list(point.data_stack),
            }
        )
        if point.slice_steps == 3:
            monitor.request_pause()

    paused = monitor.run_slice(budget=20, on_safe_point=request_after_add)
    budgeted = monitor.run_slice(budget=1)
    watchdog = monitor.run_slice(
        budget=20,
        watchdog=lambda point: point.slice_steps < 1,
    )
    resume_while_latched_rejected = _rejected(
        lambda: monitor.run_slice(budget=1)
    )
    monitor.clear_watchdog()
    final = monitor.run_slice(budget=20)

    revoked = authority.issue(PROFILE_OBSERVER, label="temporary-viewer")
    authority.revoke(revoked)
    denied["revoked_session"] = _rejected(revoked.status)

    return {
        "implementation": implementation,
        "denied": denied,
        "pause": paused.as_dict(),
        "budget": budgeted.as_dict(),
        "watchdog": watchdog.as_dict(),
        "resume_while_latched_rejected": resume_while_latched_rejected,
        "final": final.as_dict(),
        "observer_status": observer.status(),
        "pause_points": pause_points,
    }


def main() -> None:
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
