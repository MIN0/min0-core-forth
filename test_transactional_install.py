import unittest

from transactional_install_demo import run_demo


class TransactionalInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_unsealed_slot_never_replaces_last_known_good(self) -> None:
        matrix = self.result["install_power_loss"]
        for step in self.result["install_steps"][:-1]:
            with self.subTest(step=step):
                self.assertEqual(
                    matrix[step],
                    {
                        "boot_generation": 7,
                        "boot_slot": "A",
                        "trusted_generation": 7,
                    },
                )
        self.assertEqual(
            matrix["seal-complete-marker"],
            {
                "boot_generation": 8,
                "boot_slot": "B",
                "trusted_generation": 7,
            },
        )

    def test_trusted_generation_journal_is_power_loss_safe(self) -> None:
        matrix = self.result["trust_power_loss"]
        for step in self.result["trust_commit_steps"][:2]:
            with self.subTest(step=step):
                self.assertEqual(matrix[step]["boot_generation"], 8)
                self.assertEqual(matrix[step]["trusted_generation"], 7)
        self.assertEqual(
            matrix["seal-next-trusted-record"],
            {
                "boot_generation": 8,
                "boot_slot": "B",
                "trusted_generation": 8,
            },
        )
        self.assertEqual(self.result["successful_commit_generation"], 8)

    def test_failed_or_corrupt_candidate_falls_back_before_commit(self) -> None:
        self.assertEqual(self.result["pending_boot"]["generation"], 8)
        for name in (
            "failed_boot_fallback",
            "corrupted_candidate_fallback",
            "torn_marker_fallback",
            "unchanged_after_rollback",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.result[name]["generation"], 7)
                self.assertEqual(self.result[name]["slot"], "A")
        self.assertTrue(self.result["rollback_rejected"])

    def test_remaining_recovery_boundary_is_explicit(self) -> None:
        self.assertEqual(
            self.result["trusted_journal_corruption"],
            {"fallback_generation": 7, "boot_generation": 8},
        )
        self.assertTrue(
            self.result["post_commit_active_corruption_requires_recovery"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
