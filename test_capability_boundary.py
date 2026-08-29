import unittest

from capability_boundary_demo import run_demo


class CapabilityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_profiles_are_least_privilege(self) -> None:
        self.assertEqual(
            self.result["permissions"],
            {
                "runtime": ["inspect"],
                "monitor": ["inspect", "normal"],
                "recovery": ["inspect", "normal-in-recovery-mode"],
                "provisioner": ["inspect", "normal", "recovery", "trust", "root"],
            },
        )
        self.assertTrue(all(self.result["readable"].values()))

    def test_unauthorized_forged_and_revoked_access_is_rejected(self) -> None:
        self.assertTrue(all(self.result["denied"].values()))

    def test_transaction_is_bound_to_session_and_slot(self) -> None:
        self.assertEqual(
            self.result["ownership"],
            {
                "owner_visible": {
                    "label": "update-monitor",
                    "domain": "normal",
                    "slot": "B",
                },
                "normal_slot": "B",
                "phase_after_commit": "stable",
            },
        )

    def test_recovery_can_repair_only_from_recovery_mode(self) -> None:
        self.assertEqual(
            self.result["recovery_repair"],
            {
                "slot": "B",
                "mode_after_stage": "normal",
                "final_mode": "normal",
                "generation": 2,
            },
        )

    def test_authorized_session_can_adopt_persistent_pending_state(self) -> None:
        self.assertEqual(
            self.result["restart_adoption"],
            {
                "phase": "normal-awaiting-commit",
                "domain": "normal",
                "slot": "B",
                "final_phase": "stable",
                "generation": 2,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
