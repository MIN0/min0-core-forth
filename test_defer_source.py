import unittest

from defer_source_demo import run_demo


class DeferSourceTests(unittest.TestCase):
    def test_defer_is_and_action_of_use_dictionary_xt(self) -> None:
        result = run_demo()
        self.assertEqual(result["first_value"], 10)
        self.assertEqual(result["second_value"], 20)
        self.assertEqual(result["first_action_xt"], result["old_xt"])
        self.assertEqual(result["second_action_xt"], result["new_xt"])
        self.assertEqual(result["defer_payload"], result["new_xt"])

    def test_unassigned_and_non_colon_targets_fail_closed(self) -> None:
        result = run_demo()
        self.assertTrue(result["unassigned_rejected"])
        self.assertTrue(result["non_colon_rejected"])

    def test_safe_profile_rejects_compiled_is(self) -> None:
        self.assertTrue(run_demo()["compile_rejected"])

    def test_compiled_defer_has_dictionary_typed_relocation(self) -> None:
        relocation = run_demo()["relocation"]
        self.assertEqual(relocation["target"], "dictionary")
        self.assertEqual(relocation["kind"], "defer-slot")


if __name__ == "__main__":
    unittest.main(verbosity=2)
