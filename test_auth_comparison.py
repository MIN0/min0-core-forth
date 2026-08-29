import unittest

from auth_comparison_demo import run_demo


class AuthenticationComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_cross_language_authentication_vectors_are_stable(self) -> None:
        self.assertEqual(
            self.result["hmac"]["tag_hex"],
            "d2dea082c439badd51ae464b36775297a2cef9c9184fe08ae621545c916d6573",
        )
        self.assertEqual(
            self.result["ed25519"]["public_key_hex"],
            "29acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7",
        )
        self.assertEqual(
            self.result["ed25519"]["signature_hex"],
            "81fad4a7f388a6355fb1c6e90ab1f838120d27e55acf5e6e3f49857048f5b464"
            "a62f4e65348b0a5f4f5c70fcbab43f684359921e3fee93564fc895a934ef7601",
        )

    def test_valid_only_and_wrong_inputs_are_rejected(self) -> None:
        self.assertEqual(
            self.result["verification"],
            {
                "hmac_valid": True,
                "hmac_tampered": False,
                "hmac_wrong_key": False,
                "ed25519_valid": True,
                "ed25519_tampered": False,
                "ed25519_wrong_key": False,
            },
        )

    def test_device_key_compromise_has_different_blast_radius(self) -> None:
        self.assertTrue(
            self.result["device_compromise"]["hmac_verifier_can_forge"]
        )
        self.assertFalse(
            self.result["device_compromise"]["ed25519_verifier_can_forge"]
        )
        self.assertEqual(self.result["sizes"]["hmac_tag"], 32)
        self.assertEqual(self.result["sizes"]["ed25519_signature"], 64)
        self.assertEqual(self.result["sizes"]["ed25519_device_public"], 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
