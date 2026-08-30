import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from release_tool import (
    PROMINENT_NOTICE_REQUIREMENTS,
    PROJECT_ROOT,
    REQUIRED_PATHS,
    _is_internal_document,
    _scan_text,
    audit_tree,
    build_release,
    collect_release_files,
)


class ReleaseToolTests(unittest.TestCase):
    def test_workspace_selection_excludes_private_work(self) -> None:
        selected = {path.as_posix() for path in collect_release_files(PROJECT_ROOT)}
        self.assertIn(".gitattributes", selected)
        self.assertIn("viewer/value-trace.html", selected)
        self.assertIn("workbench/min0_forth.py", selected)
        self.assertIn("docs/QUICKSTART.md", selected)
        self.assertNotIn("docs/CHECKPOINT_2026-08-26.md", selected)
        self.assertNotIn("新FORTHシステム仕様を検討_会話記録.docx", selected)
        self.assertFalse(any(path.startswith("document_work/") for path in selected))
        self.assertFalse(any("__pycache__" in path for path in selected))

    def test_internal_conversation_and_checkpoint_names_are_not_publishable(self) -> None:
        rejected = (
            Path("docs/CHECKPOINT_2026-08-26.md"),
            Path("docs/project-conversation.md"),
            Path("docs/開発会話記録.md"),
            Path("docs/20260824_2142_新規FORTH_CORE開発.md"),
        )
        for relative in rejected:
            with self.subTest(relative=relative):
                self.assertTrue(_is_internal_document(relative))

    def test_current_tree_has_no_unexpected_release_blocker(self) -> None:
        result = audit_tree(PROJECT_ROOT)
        license_path = PROJECT_ROOT / "LICENSE"
        if license_path.is_file():
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["issues"], [])
        else:
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["issues"], ["missing required release file: LICENSE"])

    def test_scanner_rejects_private_material_and_personal_paths(self) -> None:
        text = "-----BEGIN " + "PRIVATE KEY-----\nC:\\Users\\someone\\secret\n"
        issues = _scan_text(Path("bad.txt"), text)
        self.assertTrue(any("private-key-pem" in issue for issue in issues))
        self.assertTrue(any("personal-windows-path" in issue for issue in issues))

    def test_deterministic_archive_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            for relative_text in REQUIRED_PATHS:
                relative = Path(relative_text)
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative.name == "VERSION":
                    content = "0.1.0-rc.1\n"
                elif relative.name == "LICENSE":
                    content = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
                elif relative.as_posix() in PROMINENT_NOTICE_REQUIREMENTS:
                    content = "\n".join(
                        PROMINENT_NOTICE_REQUIREMENTS[relative.as_posix()]
                    ) + "\n"
                else:
                    content = f"fixture for {relative.as_posix()}\n"
                path.write_text(content, encoding="utf-8", newline="\n")
            first = build_release(source, temporary / "release-a")
            second = build_release(source, temporary / "release-b")
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            archive = Path(first["archive"])
            self.assertEqual(
                hashlib.sha256(archive.read_bytes()).hexdigest(),
                first["archive_sha256"],
            )
            checksum = Path(first["checksums"]).read_text(encoding="ascii")
            self.assertIn(first["archive_sha256"], checksum)

    def test_audit_rejects_a_license_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "VERSION").write_text("0.1.0-rc.1\n", encoding="utf-8")
            (source / "LICENSE").write_text(
                "RELEASE REHEARSAL ONLY\n", encoding="utf-8"
            )
            result = audit_tree(source)
            self.assertIn(
                "LICENSE does not match the approved MIN0 CORE FORTH MIT text",
                result["issues"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
