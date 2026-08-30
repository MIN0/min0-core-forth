import unittest

from security_boundary_demo import run_demo


class SecurityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()
        cls.by_id = {item["id"]: item for item in cls.result["scenarios"]}

    def test_current_integrity_and_execution_controls_are_visible(self) -> None:
        self.assertEqual(self.by_id["T01"]["result"], "blocked")
        self.assertEqual(self.by_id["T02"]["result"], "blocked")
        self.assertEqual(self.by_id["T06"]["result"], "blocked")
        self.assertEqual(self.result["controlled"], 4)

    def test_authenticity_gap_and_rollback_control_are_explicit(self) -> None:
        self.assertEqual(self.by_id["T03"]["result"], "accepted")
        self.assertEqual(self.by_id["T05"]["result"], "blocked")
        self.assertEqual(self.result["gaps"], ["T03"])
        self.assertTrue(self.result["generation_present"])

    def test_authenticated_policy_fails_closed(self) -> None:
        self.assertEqual(self.result["authentication"], "none")
        self.assertEqual(self.by_id["T04"]["result"], "blocked")
        self.assertEqual(self.by_id["T04"]["status"], "policy-boundary")


if __name__ == "__main__":
    unittest.main(verbosity=2)
