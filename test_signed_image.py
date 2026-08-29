import unittest

from signed_image_demo import run_demo


class SignedImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_fixed_signed_image_vector(self) -> None:
        self.assertEqual(self.result["format_version"], 5)
        self.assertEqual(self.result["scheme"], "ed25519")
        self.assertEqual(self.result["image_role"], "normal")
        self.assertEqual(self.result["key_id"], "fixture-ed25519-01")
        self.assertEqual(
            self.result["identity"],
            "ac47aa6417ba1356b28daf3e7254343b5a56503ca2f633ba60384f17e0843274",
        )
        self.assertEqual(
            self.result["signature_hex"],
            "f346d5616b09e519a89ff0014ab1476ac2dc197fcfb33b16c32c8e59ac479fa7"
            "24fec25076560d31aa79a911afa6ad89ab3ed723a6453c0319bee993be23c50e",
        )

    def test_fail_closed_matrix(self) -> None:
        self.assertEqual(
            self.result["rejected"],
            [
                "component-tamper",
                "signature-tamper",
                "malformed-signature",
                "key-id-tamper",
                "unknown-scheme",
                "extra-authentication-field",
                "unknown-key",
                "wrong-public-key",
                "missing-trust-store",
                "unsigned-secure-mode",
                "signed-rollback",
                "signed-relocation-without-resigning",
            ],
        )

    def test_final_layout_can_be_resigned_and_validated(self) -> None:
        self.assertEqual(self.result["generation"], 7)
        self.assertEqual(
            self.result["target_signed"],
            {
                "identity": "0effb8955fa15fe1e8a4ddd5e3a2c78c701223740d56040ce81d97247c846715",
                "generation": 7,
                "valid": True,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
