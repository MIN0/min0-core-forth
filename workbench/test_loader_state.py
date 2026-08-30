import unittest

from loader_state_demo import run_demo


class LoaderStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_complete_rotation_reaches_stable_generation_two(self) -> None:
        self.assertEqual(
            self.result["final"],
            {
                "phase": "stable",
                "runtime_profile": "safe-runtime",
                "root_epoch": 3,
                "minimum_root_epoch": 3,
                "trust_epoch": 3,
                "minimum_trust_epoch": 3,
                "normal_generation": 2,
                "minimum_normal_generation": 2,
                "recovery_generation": 2,
                "minimum_recovery_generation": 2,
                "boot": {
                    "mode": "normal",
                    "slot": "B",
                    "generation": 2,
                    "sequence": 2,
                    "identity": "e1cd103c1561aff4e351cc7c75f4f8310a9a5985d59f3b28828422709ee6a4a6",
                    "trusted_generation": 2,
                },
            },
        )

    def test_history_exposes_each_pending_commit_boundary(self) -> None:
        self.assertEqual(
            [(item["action"], item["phase"]) for item in self.result["history"]],
            [
                ("initialized", "stable"),
                ("stage-root", "root-awaiting-commit"),
                ("commit-root", "stable"),
                ("stage-trust", "trust-awaiting-commit"),
                ("commit-trust", "stable"),
                ("stage-normal", "normal-awaiting-commit"),
                ("commit-normal", "stable"),
                ("stage-recovery", "recovery-awaiting-commit"),
                ("commit-recovery", "stable"),
                ("stage-trust", "trust-awaiting-commit"),
                ("commit-trust", "stable"),
                ("stage-root", "root-awaiting-commit"),
                ("commit-root", "stable"),
            ],
        )

    def test_unsafe_order_and_invalid_packages_are_rejected(self) -> None:
        self.assertTrue(all(self.result["ordering"].values()))
        self.assertTrue(all(self.result["rejected"].values()))

    def test_root_stage_power_loss_never_commits_early(self) -> None:
        self.assertEqual(
            self.result["root_stage_power_loss"],
            {
                "erase-inactive-root-state": {
                    "root_epoch": 1,
                    "minimum_epoch": 1,
                    "phase": "stable",
                },
                "write-root-policy-chain": {
                    "root_epoch": 1,
                    "minimum_epoch": 1,
                    "phase": "stable",
                },
                "seal-root-state": {
                    "root_epoch": 2,
                    "minimum_epoch": 1,
                    "phase": "root-awaiting-commit",
                },
            },
        )

    def test_root_commit_power_loss_is_detected_from_persistent_state(self) -> None:
        self.assertEqual(
            self.result["root_commit_power_loss"],
            {
                "erase-next-trusted-record": {
                    "root_epoch": 2,
                    "minimum_epoch": 1,
                    "phase": "root-awaiting-commit",
                },
                "write-next-trusted-record": {
                    "root_epoch": 2,
                    "minimum_epoch": 1,
                    "phase": "root-awaiting-commit",
                },
                "seal-next-trusted-record": {
                    "root_epoch": 2,
                    "minimum_epoch": 2,
                    "phase": "stable",
                },
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
