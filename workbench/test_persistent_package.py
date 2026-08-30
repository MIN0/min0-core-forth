import unittest

from persistent_package_demo import run_demo


class PersistentPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_cross_language_package_vectors_are_stable(self) -> None:
        self.assertEqual(self.result["format_version"], 1)
        self.assertEqual(
            self.result["packages"],
            {
                "image": {
                    "bytes": 8356,
                    "sha256": "571516cbebd7ce8c2f53d4acb5db0fbc3e07871b2e8d9ce8996b0bf954d17f43",
                },
                "trust_bundle": {
                    "bytes": 538,
                    "sha256": "be731c1b8dcf241c7f96203bbac5d562e9be450da62bfc50f8b69ef20519ba83",
                },
                "root_policy_chain": {
                    "bytes": 1364,
                    "sha256": "415d92cfb51c5150c9d101745bc166d37aa17e73bf57b1b7eb4b4c7c6d3b4490",
                },
            },
        )

    def test_external_signed_image_round_trip_executes(self) -> None:
        self.assertEqual(self.result["external_file"]["generation"], 7)
        self.assertEqual(
            self.result["external_file"]["stack"],
            [99, 2, 3, 3, 0, 2, 7, 32768],
        )
        self.assertEqual(
            self.result["external_file"]["write_sha256"],
            self.result["packages"]["image"]["sha256"],
        )
        self.assertEqual(
            self.result["trust_chain"],
            {
                "root_epoch": 2,
                "trust_epoch": 2,
                "image_key_id": "fixture-ed25519-01",
                "valid": True,
            },
        )

    def test_structural_and_resource_attacks_are_rejected(self) -> None:
        self.assertEqual(len(self.result["rejected"]), 15)
        self.assertTrue(all(self.result["rejected"].values()))
        self.assertEqual(
            self.result["limits"],
            {
                "max_file_bytes": 1_048_576,
                "max_sections": 8,
                "max_metadata_bytes": 262_144,
            },
        )

    def test_container_checksum_is_not_mistaken_for_authentication(self) -> None:
        self.assertEqual(
            self.result["layering"],
            {
                "resealed_container_passes_structure": True,
                "image_signature_rejects_resealed_tamper": True,
                "unknown_image_metadata_rejected": True,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
