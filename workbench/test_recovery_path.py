import unittest

from recovery_path_demo import run_demo


class RecoveryPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_recovery_has_separate_role_key_and_generation_domain(self) -> None:
        self.assertEqual(self.result["format_version"], 5)
        self.assertEqual(self.result["recovery_role"], "recovery")
        self.assertEqual(self.result["recovery_boot"]["mode"], "recovery")
        self.assertEqual(self.result["recovery_boot"]["slot"], "R")
        self.assertEqual(self.result["separate_generations"], {"normal": 8, "recovery": 1})

    def test_repair_is_power_loss_safe(self) -> None:
        matrix = self.result["repair_power_loss"]
        for step in self.result["repair_steps"][:-1]:
            with self.subTest(step=step):
                self.assertEqual(
                    matrix[step],
                    {
                        "mode": "recovery",
                        "generation": 1,
                        "normal_trusted_generation": 8,
                    },
                )
        self.assertEqual(
            matrix["seal-complete-marker"],
            {
                "mode": "normal",
                "generation": 8,
                "normal_trusted_generation": 8,
            },
        )

    def test_completed_repair_returns_to_normal_without_downgrade(self) -> None:
        self.assertEqual(self.result["repaired_boot"]["mode"], "normal")
        self.assertEqual(self.result["repaired_boot"]["generation"], 8)
        self.assertEqual(self.result["normal_trusted_after_repair"], 8)

    def test_role_confusion_and_unauthorized_repair_are_rejected(self) -> None:
        self.assertEqual(
            self.result["rejected"],
            {
                "old_normal_repair": True,
                "normal_as_recovery": True,
                "recovery_as_normal": True,
                "role_tamper": True,
                "repair_outside_recovery": True,
            },
        )
        self.assertTrue(self.result["corrupt_recovery_total_failure_visible"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
