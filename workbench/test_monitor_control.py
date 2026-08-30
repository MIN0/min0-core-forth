import unittest

from min0_core_forth_control import (
    ControlAuthorizationError,
    ControlStateError,
    MonitorControlAuthority,
    PROFILE_MONITOR,
    PROFILE_OBSERVER,
    STOP_BUDGET,
    STOP_HALT,
    STOP_REQUESTED,
    STOP_WATCHDOG,
)
from min0_core_forth_vm import Assembler, Min0CoreForthVM, Op
from monitor_control_demo import run_demo


def make_vm() -> Min0CoreForthVM:
    asm = Assembler()
    asm.emit(Op.NOP)
    asm.emit(Op.NOP)
    asm.emit(Op.HALT)
    vm = Min0CoreForthVM()
    vm.load(asm.build())
    return vm


class MonitorControlTests(unittest.TestCase):
    def test_demo_preserves_state_across_all_stop_reasons(self) -> None:
        result = run_demo()
        self.assertTrue(all(result["denied"].values()))
        self.assertEqual(result["pause"]["reason"], STOP_REQUESTED)
        self.assertEqual(result["pause"]["data_stack"], [3])
        self.assertEqual(result["budget"]["reason"], STOP_BUDGET)
        self.assertEqual(result["watchdog"]["reason"], STOP_WATCHDOG)
        self.assertTrue(result["resume_while_latched_rejected"])
        self.assertEqual(result["final"]["reason"], STOP_HALT)
        self.assertEqual(result["final"]["total_steps"], 6)

    def test_queued_pause_stops_before_the_next_instruction(self) -> None:
        vm = make_vm()
        authority = MonitorControlAuthority(vm)
        monitor = authority.issue(PROFILE_MONITOR)
        monitor.request_pause()
        stopped = monitor.run_slice(budget=10)
        self.assertEqual(stopped.reason, STOP_REQUESTED)
        self.assertEqual(stopped.executed, 0)
        self.assertEqual(vm.steps, 0)

    def test_budget_is_per_slice_and_resume_continues_at_same_ip(self) -> None:
        vm = make_vm()
        authority = MonitorControlAuthority(vm)
        monitor = authority.issue(PROFILE_MONITOR)
        first = monitor.run_slice(budget=1)
        second = monitor.run_slice(budget=1)
        final = monitor.run_slice(budget=1)
        self.assertEqual([first.reason, second.reason, final.reason], [
            STOP_BUDGET, STOP_BUDGET, STOP_HALT
        ])
        self.assertEqual([first.ip, second.ip, final.ip], [1, 2, 3])

    def test_watchdog_is_latched_until_monitor_acknowledges_it(self) -> None:
        authority = MonitorControlAuthority(make_vm())
        monitor = authority.issue(PROFILE_MONITOR)
        stopped = monitor.run_slice(budget=10, watchdog=lambda _point: False)
        self.assertEqual(stopped.reason, STOP_WATCHDOG)
        self.assertEqual(stopped.executed, 0)
        with self.assertRaises(ControlStateError):
            monitor.run_slice(budget=1)
        monitor.clear_watchdog()
        self.assertEqual(monitor.run_slice(budget=3).reason, STOP_HALT)

    def test_observer_can_inspect_but_cannot_control(self) -> None:
        authority = MonitorControlAuthority(make_vm())
        observer = authority.issue(PROFILE_OBSERVER)
        self.assertEqual(observer.status()["state"], "paused")
        with self.assertRaises(ControlAuthorizationError):
            observer.request_pause()
        with self.assertRaises(ControlAuthorizationError):
            observer.run_slice(budget=1)

    def test_invalid_budgets_are_rejected(self) -> None:
        authority = MonitorControlAuthority(make_vm())
        monitor = authority.issue(PROFILE_MONITOR)
        for invalid in (0, -1, True, 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    monitor.run_slice(budget=invalid)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
