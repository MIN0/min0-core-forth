import unittest

from dictionary_capability_demo import run_demo


class DictionaryCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_runtime_dictionary_is_logically_write_protected(self) -> None:
        self.assertEqual(self.result["dictionary_permissions"], "rw")
        self.assertTrue(self.result["dictionary_write_protected"])
        self.assertTrue(self.result["runtime_structure_sealed"])

    def test_data_remains_writable_and_monitor_defer_still_works(self) -> None:
        self.assertEqual(self.result["data_value"], 123)
        self.assertEqual(self.result["defer_value_after_monitor"], 9)
        self.assertEqual(self.result["monitor_audit_operation"], "defer-switch")
        self.assertTrue(self.result["monitor_changed_only_defer_slot"])

    def test_ordinary_and_forged_dictionary_writes_are_rejected(self) -> None:
        self.assertTrue(self.result["attacks_left_dictionary_unchanged"])
        self.assertTrue(all(self.result["rejected"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
