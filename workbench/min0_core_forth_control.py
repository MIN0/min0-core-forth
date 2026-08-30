"""Safe-point execution control for the MIN0 CORE FORTH VM.

This module is deliberately outside the bytecode VM.  FORTH code cannot forge
control authority by placing values on a stack or in memory; a trusted host
must hold an issued, non-serializable session object.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Final

from min0_core_forth_vm import Min0CoreForthVM, VMError

if TYPE_CHECKING:
    from min0_core_forth_dictionary import RuntimeDictionary


PROFILE_OBSERVER: Final = "observer"
PROFILE_MONITOR: Final = "monitor"

STATE_PAUSED: Final = "paused"
STATE_RUNNING: Final = "running"
STATE_WATCHDOG: Final = "watchdog-latched"
STATE_HALTED: Final = "halted"
STATE_FAULTED: Final = "faulted"

STOP_REQUESTED: Final = "pause-requested"
STOP_BUDGET: Final = "budget-exhausted"
STOP_WATCHDOG: Final = "watchdog-expired"
STOP_HALT: Final = "halted"


class ControlError(RuntimeError):
    """Base class for control-plane failures."""


class ControlAuthorizationError(ControlError):
    pass


class ControlStateError(ControlError):
    pass


class ControlInvariantError(ControlStateError):
    pass


@dataclass(frozen=True)
class SafePoint:
    """Immutable observation made between two complete VM instructions."""

    slice_steps: int
    total_steps: int
    ip: int
    data_stack: tuple[int, ...]
    return_stack: tuple[int, ...]
    loop_stack: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class RunResult:
    reason: str
    executed: int
    total_steps: int
    ip: int
    data_stack: tuple[int, ...]
    return_stack: tuple[int, ...]
    loop_stack: tuple[tuple[int, int], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason,
            "executed": self.executed,
            "total_steps": self.total_steps,
            "ip": self.ip,
            "data_stack": list(self.data_stack),
            "return_stack": list(self.return_stack),
            "loop_stack": [list(frame) for frame in self.loop_stack],
        }


SafePointObserver = Callable[[SafePoint], None]
WatchdogCheck = Callable[[SafePoint], bool]


class ControlSession:
    """Opaque host capability; it is intentionally not serializable."""

    __slots__ = ("_authority", "serial", "label")

    def __init__(
        self,
        authority: "MonitorControlAuthority",
        serial: int,
        label: str,
        marker: object,
    ) -> None:
        if not authority._valid_session_marker(marker):
            raise ControlAuthorizationError(
                "control sessions must be issued by the authority"
            )
        self._authority = authority
        self.serial = serial
        self.label = label

    def status(self) -> dict[str, object]:
        return self._authority.status(self)

    def request_pause(self) -> None:
        self._authority.request_pause(self)

    def run_slice(
        self,
        *,
        budget: int,
        watchdog: WatchdogCheck | None = None,
        on_safe_point: SafePointObserver | None = None,
    ) -> RunResult:
        return self._authority.run_slice(
            self,
            budget=budget,
            watchdog=watchdog,
            on_safe_point=on_safe_point,
        )

    def clear_watchdog(self) -> None:
        self._authority.clear_watchdog(self)

    def inspect_paused(self) -> dict[str, object]:
        return self._authority.inspect_paused(self)

    def switch_defer(self, defer_name: str, target_name: str) -> dict[str, object]:
        return self._authority.switch_defer(self, defer_name, target_name)

    def apply_forth_control(self, source: str) -> dict[str, object]:
        return self._authority.apply_forth_control(self, source)


class MonitorControlAuthority:
    """Trusted control plane around one VM instance."""

    def __init__(
        self, vm: Min0CoreForthVM, dictionary: "RuntimeDictionary | None" = None
    ) -> None:
        self.vm = vm
        self.dictionary = dictionary
        self.vm.lock_defer_store()
        self._defer_authorization = object()
        if dictionary is not None:
            dictionary.lock_defer_updates(self._defer_authorization)
        self._marker = object()
        self._profiles: dict[ControlSession, str] = {}
        self._next_serial = 1
        self._pause_requested = False
        self._watchdog_latched = False
        self._state = STATE_HALTED if vm.halted else STATE_PAUSED
        self._last_stop: str | None = STOP_HALT if vm.halted else None
        self._audit: list[dict[str, object]] = []
        self._seal = self._control_fingerprint()

    def _valid_session_marker(self, marker: object) -> bool:
        return marker is self._marker

    def issue(self, profile: str, *, label: str | None = None) -> ControlSession:
        if profile not in (PROFILE_OBSERVER, PROFILE_MONITOR):
            raise ValueError(f"unknown control profile {profile!r}")
        session = ControlSession(
            self,
            self._next_serial,
            label or profile,
            self._marker,
        )
        self._next_serial += 1
        self._profiles[session] = profile
        return session

    def revoke(self, session: ControlSession) -> None:
        self._profile(session)
        del self._profiles[session]

    def _profile(self, session: object) -> str:
        try:
            return self._profiles[session]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise ControlAuthorizationError(
                "unknown, forged, or revoked control session"
            ) from exc

    def _require_monitor(self, session: object) -> None:
        if self._profile(session) != PROFILE_MONITOR:
            raise ControlAuthorizationError("monitor control authority is required")

    def _safe_point(self, slice_steps: int) -> SafePoint:
        return SafePoint(
            slice_steps=slice_steps,
            total_steps=self.vm.steps,
            ip=self.vm.ip,
            data_stack=tuple(self.vm.data_stack),
            return_stack=tuple(self.vm.return_stack),
            loop_stack=tuple(
                (frame.limit, frame.index) for frame in self.vm.loop_stack
            ),
        )

    def status(self, session: object) -> dict[str, object]:
        self._profile(session)
        point = self._safe_point(0)
        return {
            "state": self._state,
            "last_stop": self._last_stop,
            "pause_requested": self._pause_requested,
            "watchdog_latched": self._watchdog_latched,
            "total_steps": point.total_steps,
            "ip": point.ip,
            "data_stack": list(point.data_stack),
            "return_stack": list(point.return_stack),
            "loop_stack": [list(frame) for frame in point.loop_stack],
        }

    def inspect_paused(self, session: object) -> dict[str, object]:
        self._profile(session)
        if self._state not in (STATE_PAUSED, STATE_WATCHDOG, STATE_HALTED):
            raise ControlStateError("inspection requires a stopped VM")
        self._verify_resume_invariants()
        result = self.status(session)
        result["dictionary"] = []
        if self.dictionary is not None:
            result["dictionary"] = [
                {
                    "name": entry.name,
                    "kind": entry.kind,
                    "xt": entry.xt,
                    "payload": entry.payload,
                }
                for entry in self.dictionary.entries(include_hidden=False)
            ]
        result["audit"] = [dict(record) for record in self._audit]
        return result

    def switch_defer(
        self, session: object, defer_name: str, target_name: str
    ) -> dict[str, object]:
        self._require_monitor(session)
        if self._state != STATE_PAUSED or self._watchdog_latched:
            raise ControlStateError("DEFER switching requires an acknowledged pause")
        if self.dictionary is None:
            raise ControlStateError("no runtime dictionary is attached")
        self._verify_resume_invariants()
        deferred = self.dictionary.find(defer_name)
        target = self.dictionary.find(target_name)
        if deferred is None:
            raise ControlStateError(f"unknown DEFER word {defer_name!r}")
        if target is None:
            raise ControlStateError(f"unknown DEFER target {target_name!r}")
        old_xt = self.dictionary.read_defer_target(deferred)
        old_name = self._colon_name_for(old_xt)
        updated = self.dictionary.set_defer(
            deferred, target, authorization=self._defer_authorization
        )
        record: dict[str, object] = {
            "sequence": len(self._audit) + 1,
            "operation": "defer-switch",
            "defer": updated.name,
            "from": old_name,
            "to": target.name,
            "old_xt": old_xt,
            "new_xt": updated.payload,
            "total_steps": self.vm.steps,
            "ip": self.vm.ip,
        }
        self._audit.append(record)
        self._seal = self._control_fingerprint()
        return dict(record)

    def apply_forth_control(
        self, session: object, source: str
    ) -> dict[str, object]:
        from min0_core_forth_compiler import tokenize

        tokens = tokenize(source)
        if len(tokens) == 4 and tokens[0] == "'" and tokens[2] == "IS":
            return self.switch_defer(session, tokens[3], tokens[1])
        self._profile(session)
        if len(tokens) == 2 and tokens[0] == "ACTION-OF":
            if self.dictionary is None:
                raise ControlStateError("no runtime dictionary is attached")
            deferred = self.dictionary.find(tokens[1])
            if deferred is None:
                raise ControlStateError(f"unknown DEFER word {tokens[1]!r}")
            target_xt = self.dictionary.read_defer_target(deferred)
            return {
                "operation": "action-of",
                "defer": deferred.name,
                "target": self._colon_name_for(target_xt),
                "target_xt": target_xt,
            }
        raise ControlStateError(
            "control source must be: ' target IS defer, or ACTION-OF defer"
        )

    def request_pause(self, session: object) -> None:
        self._require_monitor(session)
        self._pause_requested = True

    def clear_watchdog(self, session: object) -> None:
        self._require_monitor(session)
        if not self._watchdog_latched:
            raise ControlStateError("watchdog is not latched")
        self._watchdog_latched = False
        self._state = STATE_PAUSED

    def run_slice(
        self,
        session: object,
        *,
        budget: int,
        watchdog: WatchdogCheck | None = None,
        on_safe_point: SafePointObserver | None = None,
    ) -> RunResult:
        self._require_monitor(session)
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise ValueError("instruction budget must be a positive integer")
        if self._watchdog_latched:
            raise ControlStateError(
                "watchdog must be explicitly cleared before execution resumes"
            )
        if self._state == STATE_FAULTED:
            raise ControlStateError("faulted execution cannot be resumed")
        self._verify_resume_invariants()
        if self.vm.halted:
            self._state = STATE_HALTED
            return self._result(STOP_HALT, 0)

        self._state = STATE_RUNNING
        executed = 0
        try:
            while True:
                point = self._safe_point(executed)
                if on_safe_point is not None:
                    on_safe_point(point)
                if self._pause_requested:
                    self._pause_requested = False
                    self._state = STATE_PAUSED
                    return self._result(STOP_REQUESTED, executed)
                if executed >= budget:
                    self._state = STATE_PAUSED
                    return self._result(STOP_BUDGET, executed)
                if watchdog is not None and not watchdog(point):
                    self._watchdog_latched = True
                    self._state = STATE_WATCHDOG
                    return self._result(STOP_WATCHDOG, executed)

                self.vm.step()
                executed += 1
                if self.vm.halted:
                    self._state = STATE_HALTED
                    return self._result(STOP_HALT, executed)
        except VMError:
            self._state = STATE_FAULTED
            raise

    def _result(self, reason: str, executed: int) -> RunResult:
        self._last_stop = reason
        point = self._safe_point(executed)
        result = RunResult(
            reason=reason,
            executed=executed,
            total_steps=point.total_steps,
            ip=point.ip,
            data_stack=point.data_stack,
            return_stack=point.return_stack,
            loop_stack=point.loop_stack,
        )
        self._seal = self._control_fingerprint()
        return result

    def _colon_name_for(self, target_xt: int) -> str:
        if target_xt == 0:
            return "<unassigned>"
        assert self.dictionary is not None
        from min0_core_forth_dictionary import KIND_COLON

        for entry in self.dictionary.entries(include_hidden=False):
            if entry.kind == KIND_COLON and entry.xt == target_xt:
                return entry.name
        return f"0x{target_xt:08X}"

    def _control_fingerprint(self) -> tuple[object, ...]:
        dictionary_state: tuple[object, ...] | None = None
        if self.dictionary is not None:
            dictionary_state = (
                self.dictionary.here,
                self.dictionary.data_here,
                self.dictionary.latest,
                hashlib.sha256(self.dictionary.image()).digest(),
            )
        return (
            self.vm.ip,
            self.vm.steps,
            self.vm.halted,
            self.vm.allow_defer_store,
            tuple(self.vm.data_stack),
            tuple(self.vm.return_stack),
            tuple((frame.limit, frame.index) for frame in self.vm.loop_stack),
            dictionary_state,
        )

    def _verify_resume_invariants(self) -> None:
        if self.vm.allow_defer_store:
            raise ControlInvariantError(
                "compiled DEFER store must remain disabled under Monitor control"
            )
        if len(self.vm.data_stack) > self.vm.max_data_depth:
            raise ControlInvariantError("DATA stack exceeds its configured limit")
        if len(self.vm.return_stack) > self.vm.max_return_depth:
            raise ControlInvariantError("RETURN stack exceeds its configured limit")
        if len(self.vm.loop_stack) > self.vm.max_loop_depth:
            raise ControlInvariantError("LOOP stack exceeds its configured limit")
        try:
            if not self.vm.halted:
                self.vm.memory.check_fetch(self.vm.ip, 1)
            for address in self.vm.return_stack:
                self.vm.memory.check_fetch(address, 1)
            if self.dictionary is not None:
                from min0_core_forth_dictionary import KIND_DEFER

                for entry in self.dictionary.entries():
                    if entry.kind == KIND_DEFER:
                        self.dictionary.read_defer_target(entry)
        except Exception as exc:
            raise ControlInvariantError("control-state structure is invalid") from exc
        if self._control_fingerprint() != self._seal:
            raise ControlInvariantError(
                "control-critical state changed outside an authorized operation"
            )
