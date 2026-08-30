import unittest

from trust_rotation_demo import run_demo


class TrustRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_root_signed_bundle_vectors_are_stable(self) -> None:
        self.assertEqual(self.result["bundle_format_version"], 1)
        self.assertEqual(
            self.result["root_public_key_hex"],
            "d404bc44565aedbb899150e5b0b3b32b9441bf0cb7884c33130da8dbc27dd2cf",
        )
        self.assertEqual(
            self.result["bundle_signatures"]["4"],
            "4f4c3bc0be4f30552c60f369b3093e6beff7c53945b47bfd53646884963bea6b"
            "53a5eb9b0c8e6cc3060ff790984b4ccedec1890f803868ac589c1ea36f34f403",
        )

    def test_bundle_and_epoch_journals_are_power_loss_safe(self) -> None:
        self.assertEqual(
            self.result["bundle_power_loss"],
            {
                "erase-inactive-trust-slot": {"visible_epoch": 1, "minimum_epoch": 1},
                "write-trust-bundle": {"visible_epoch": 1, "minimum_epoch": 1},
                "seal-trust-slot": {"visible_epoch": 2, "minimum_epoch": 1},
            },
        )
        self.assertEqual(
            self.result["epoch_commit_power_loss"],
            {
                "erase-next-trusted-record": {"visible_epoch": 2, "minimum_epoch": 1},
                "write-next-trusted-record": {"visible_epoch": 2, "minimum_epoch": 1},
                "seal-next-trusted-record": {"visible_epoch": 2, "minimum_epoch": 2},
            },
        )

    def test_normal_rotation_overlaps_before_revocation(self) -> None:
        self.assertEqual(
            self.result["normal_rotation"],
            {
                "overlap_accepts_old_and_new": True,
                "old_revoked_at_epoch3": True,
                "new_survives_epoch3": True,
            },
        )

    def test_recovery_update_precedes_old_key_revocation(self) -> None:
        matrix = self.result["recovery_update_power_loss"]
        for step in list(matrix)[:-1]:
            with self.subTest(step=step):
                self.assertEqual(matrix[step]["generation"], 1)
                self.assertEqual(matrix[step]["slot"], "A")
        self.assertEqual(matrix["seal-complete-marker"]["generation"], 2)
        self.assertEqual(self.result["post_revoke_recovery_boot"]["generation"], 2)
        self.assertEqual(
            self.result["ordering"],
            {
                "premature_revoke_breaks_old_recovery": True,
                "correct_order_keeps_new_recovery": True,
            },
        )

    def test_forgery_tamper_and_bundle_rollback_are_rejected(self) -> None:
        self.assertEqual(
            self.result["rejected"],
            {
                "bundle_rollback": True,
                "forged_root_signature": True,
                "tampered_bundle": True,
            },
        )
        self.assertEqual(self.result["final_trust_epoch"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
