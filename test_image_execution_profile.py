import unittest

from image_execution_profile_demo import run_demo


class ImageExecutionProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_profile_is_derived_from_compiled_defer_store(self) -> None:
        self.assertEqual(self.result["safe_image_profile"], "safe-runtime")
        self.assertEqual(self.result["build_image_profile"], "standard-build")
        self.assertTrue(self.result["build_has_defer_store_record"])
        self.assertEqual(self.result["safe_verified_capabilities"], [])
        self.assertEqual(
            self.result["build_verified_capabilities"], ["compiled-defer-store"]
        )
        self.assertGreater(self.result["build_verified_instruction_count"], 0)

    def test_safe_loader_rejects_before_inactive_slot_write(self) -> None:
        self.assertTrue(self.result["safe_loader_rejected_before_write"])
        self.assertTrue(self.result["inactive_slot_untouched"])
        self.assertEqual(self.result["standard_build_installed_slot"], "B")

    def test_signed_profile_cannot_be_relabeled_and_recovery_stays_safe(self) -> None:
        self.assertTrue(self.result["profile_tamper_rejected"])
        self.assertTrue(self.result["standard_build_recovery_rejected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
