import unittest

from compiled_defer_demo import run_demo


class CompiledDeferTests(unittest.TestCase):
    def test_safe_profile_compiles_read_only_xt_operations(self) -> None:
        result = run_demo()
        self.assertEqual(result["safe_literal_xt"], result["safe_new_xt"])
        self.assertEqual(result["safe_current_xt"], result["safe_old_xt"])
        self.assertEqual(
            set(result["safe_relocations"]), {"xt-literal", "action-of-slot"}
        )

    def test_safe_profile_rejects_compiled_is_without_changing_target(self) -> None:
        result = run_demo()
        self.assertTrue(result["safe_compiled_is_rejected"])
        self.assertTrue(result["safe_target_unchanged"])

    def test_standard_build_profile_executes_compiled_is(self) -> None:
        result = run_demo()
        self.assertEqual(result["build_before_switch"], 10)
        self.assertEqual(result["build_after_switch"], 20)
        self.assertEqual(result["build_target_xt"], result["build_new_xt"])
        self.assertEqual(result["store_relocation"]["target"], "dictionary")

    def test_standard_build_requires_explicit_vm_permission(self) -> None:
        self.assertTrue(run_demo()["profile_requires_build_vm"])

    def test_monitor_forcibly_disables_precompiled_is(self) -> None:
        result = run_demo()
        self.assertTrue(result["monitor_denied_compiled_is"])
        self.assertTrue(result["monitor_target_unchanged"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
