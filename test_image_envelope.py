import unittest

from image_envelope_demo import run_demo


class ImageEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_identity_binds_components_manifest_and_allocator(self) -> None:
        self.assertEqual(self.result["record_count"], 68)
        self.assertEqual(
            self.result["source_identity"],
            "b6752a2cbed614a7515f04722e5b9447aa0cc54bdcc5b5505acdee8dcbe8d694",
        )
        self.assertNotEqual(
            self.result["source_identity"], self.result["different_identity"]
        )
        self.assertTrue(self.result["identity_changed"])
        self.assertEqual(self.result["generation"], 7)
        self.assertEqual(self.result["linked_generation"], 7)

    def test_linked_allocator_and_execution_move_together(self) -> None:
        source = self.result["source_allocator"]
        linked = self.result["linked_allocator"]
        self.assertEqual(linked["code_here"] - source["code_here"], 0x1000)
        self.assertEqual(linked["header_here"] - source["header_here"], 0x1000)
        self.assertEqual(linked["data_here"] - source["data_here"], 0x1000)
        self.assertEqual(linked["latest"] - source["latest"], 0x1000)
        self.assertEqual(self.result["stack"], [99, 2, 3, 3, 0, 2, 7, 0x9000])

    def test_mismatch_and_unauthenticated_secure_mode_are_rejected(self) -> None:
        self.assertEqual(self.result["authentication"], "none")
        self.assertEqual(
            self.result["rejected"],
            [
                "different-image",
                "different-envelope",
                "allocator-metadata",
                "manifest-digest",
                "authentication-required",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
