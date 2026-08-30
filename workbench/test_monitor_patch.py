import unittest

from min0_core_forth_control import ControlInvariantError, MonitorControlAuthority, PROFILE_MONITOR
from min0_core_forth_dictionary import KIND_DEFER
from monitor_patch_demo import _system, run_demo


class MonitorPatchTests(unittest.TestCase):
    def test_compiled_defer_changes_only_after_authorized_switch(self) -> None:
        result = run_demo()
        self.assertEqual(result["first"]["data_stack"], [10])
        self.assertEqual(result["final_stack"], [10, 20])
        self.assertEqual(result["service_before"]["kind"], KIND_DEFER)
        self.assertNotEqual(
            result["service_before"]["payload"],
            result["service_after"]["payload"],
        )
        self.assertTrue(result["snapshot_copy_isolated"])
        self.assertTrue(all(result["denied"].values()))

    def test_switch_has_one_observer_visible_audit_record(self) -> None:
        result = run_demo()
        self.assertEqual(result["audit"]["operation"], "defer-switch")
        self.assertEqual(result["audit"]["from"], "OLD-SERVICE")
        self.assertEqual(result["audit"]["to"], "NEW-SERVICE")
        self.assertEqual(result["audit_visible_to_observer"], [result["audit"]])

    def test_compiler_emits_typed_dictionary_relocation(self) -> None:
        record = run_demo()["defer_relocation"]
        self.assertEqual(record["target"], "dictionary")
        self.assertEqual(record["kind"], "defer-slot")
        self.assertEqual(record["width"], 4)

    def test_out_of_band_dictionary_change_blocks_resume(self) -> None:
        vm, dictionary, _outer = _system()
        authority = MonitorControlAuthority(vm, dictionary)
        monitor = authority.issue(PROFILE_MONITOR)
        dictionary.add_constant("OUT-OF-BAND", 1)
        with self.assertRaises(ControlInvariantError):
            monitor.run_slice(budget=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
