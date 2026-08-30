import unittest

from sealed_execution_demo import run_demo


class SealedExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_build_rwx_becomes_one_way_runtime_rx(self) -> None:
        self.assertEqual(self.result["before_permissions"], "rwx")
        self.assertEqual(self.result["after_permissions"], "rx")
        self.assertFalse(self.result["code_programmable_after_seal"])
        self.assertTrue(self.result["code_sealed"])
        self.assertGreater(self.result["verified_boundary_count"], 0)

    def test_safe_code_data_and_defer_still_execute(self) -> None:
        self.assertEqual(
            self.result["values"],
            {
                "literal_0x25": 0x25,
                "data_roundtrip": 123,
                "defer_before_corruption": 7,
                "primitive_after_seal": 5,
            },
        )

    def test_write_execute_and_corrupt_target_attacks_are_rejected(self) -> None:
        self.assertTrue(self.result["code_unchanged"])
        self.assertEqual(
            self.result["corrupted_target_payload"], self.result["operand_address"]
        )
        self.assertTrue(all(self.result["rejected"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
