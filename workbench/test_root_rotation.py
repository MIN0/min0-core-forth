import unittest

from root_rotation_demo import run_demo


class RootRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_root_policy_vectors_are_stable(self) -> None:
        self.assertEqual(self.result["root_policy_format_version"], 1)
        self.assertEqual(
            self.result["root_public_keys"],
            {
                "old": "d404bc44565aedbb899150e5b0b3b32b9441bf0cb7884c33130da8dbc27dd2cf",
                "new": "ed3234b276d4ceda57d59bad14fbaf5a773c0f318c999de3a60d53c5a5b34c05",
            },
        )
        self.assertEqual(
            self.result["policy_digests"]["4"],
            "a70508d1a419a705d0945248e68e43cb3eeac866735c06eda118058c6f416080",
        )
        self.assertEqual(
            self.result["policy_signatures"]["4"]["fixture-offline-root-02"],
            "7c3af72ae28b03180e5a3978625d5c75000847aca9df54b10cefc4bc3c692910"
            "a5b4505c3506e0f0e77beb25b8c801f5cb49860575e51413191a517c81627604",
        )

    def test_root_state_and_epoch_journal_are_power_loss_safe(self) -> None:
        self.assertEqual(
            self.result["root_write_power_loss"],
            {
                "erase-inactive-root-state": {
                    "visible_epoch": 1,
                    "minimum_epoch": 1,
                },
                "write-root-policy-chain": {
                    "visible_epoch": 1,
                    "minimum_epoch": 1,
                },
                "seal-root-state": {
                    "visible_epoch": 2,
                    "minimum_epoch": 1,
                },
            },
        )
        self.assertEqual(
            self.result["root_commit_power_loss"],
            {
                "erase-next-trusted-record": {
                    "visible_epoch": 2,
                    "minimum_epoch": 1,
                },
                "write-next-trusted-record": {
                    "visible_epoch": 2,
                    "minimum_epoch": 1,
                },
                "seal-next-trusted-record": {
                    "visible_epoch": 2,
                    "minimum_epoch": 2,
                },
            },
        )

    def test_bundle_migration_precedes_old_root_retirement(self) -> None:
        self.assertEqual(
            self.result["ordering"],
            {
                "overlap_accepts_old_and_new_bundles": True,
                "new_bundle_survives_retirement": True,
                "old_bundle_rejected_after_retirement": True,
                "premature_retirement_breaks_old_bundle": True,
                "post_retirement_new_root_only_policy": True,
            },
        )
        self.assertEqual(self.result["final_root_epoch"], 4)
        self.assertEqual(
            self.result["final_active_roots"], ["fixture-offline-root-02"]
        )

    def test_transition_forgery_tamper_and_rollback_are_rejected(self) -> None:
        self.assertEqual(
            self.result["rejected"],
            {
                "missing_new_signature": True,
                "tampered_signature": True,
                "broken_chain_link": True,
                "root_key_replacement": True,
                "retired_root_reactivation": True,
                "root_policy_rollback": True,
                "corrupted_committed_chain_fails_closed": True,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
