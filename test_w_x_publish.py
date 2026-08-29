import unittest

from w_x_publish_demo import run_demo


class WxPublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_staging_is_rw_and_non_executable(self) -> None:
        self.assertEqual(self.result["staging_permissions"], "rw")
        self.assertTrue(self.result["rejected"]["execute_staging"])

    def test_runtime_is_rx_sealed_and_still_runs(self) -> None:
        self.assertEqual(self.result["runtime_permissions"], "rx")
        self.assertFalse(self.result["runtime_programmable"])
        self.assertTrue(self.result["runtime_sealed"])
        self.assertEqual(self.result["stack"], [7, 5])

    def test_staging_is_detached_and_attacks_are_rejected(self) -> None:
        self.assertTrue(self.result["staging_changed_after_publish"])
        self.assertTrue(self.result["runtime_unchanged_after_staging_change"])
        self.assertTrue(all(self.result["rejected"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
