import unittest

from anti_rollback_demo import run_demo


class AntiRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_signed_old_image_is_rejected_by_generation_policy(self) -> None:
        self.assertEqual(
            self.result["signature_valid"],
            {"old": True, "current": True, "next": True},
        )
        self.assertTrue(self.result["old_signed_image_rejected"])

    def test_trusted_state_changes_only_after_successful_commit(self) -> None:
        self.assertEqual(
            self.result["trusted_state"],
            {
                "before_failed_install": 7,
                "after_failed_install": 7,
                "after_successful_install": 8,
            },
        )
        self.assertTrue(self.result["current_rejected_after_commit"])
        self.assertEqual(self.result["linked_generation"], 8)

    def test_generation_is_uint64_without_wrap_or_decrease(self) -> None:
        self.assertEqual(
            self.result["bounds"],
            {
                "negative_rejected": True,
                "overflow_rejected": True,
                "lower_commit_rejected": True,
            },
        )
        self.assertEqual(self.result["format_version"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
