"""Build and audit a clean, deterministic MIN0 CORE FORTH release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIRECTORIES = {
    "docs": frozenset({".md"}),
    "tools": frozenset({".py"}),
    "workbench": frozenset({".py", ".rb", ".fth", ".fcb", ".json"}),
    "viewer": frozenset({".html"}),
}
EXCLUDED_PARTS = frozenset({
    ".git", "__pycache__", "document_work", "release", "release-staging",
})
INTERNAL_DOCUMENT_PATTERNS = (
    re.compile(r"checkpoint", re.IGNORECASE),
    re.compile(r"conversation", re.IGNORECASE),
    re.compile(r"会話"),
    re.compile(r"^[0-9]{8}_[0-9]{4}_"),
)
EXPLICIT_TOP_LEVEL = frozenset({
    ".gitattributes", ".gitignore", ".nojekyll", "FIRST_READ.md", "FIRST_READ_JP.md",
    "LICENSE", "README.md", "README_JP.md", "SECURITY.md", "SECURITY_JP.md", "VERSION",
    "requirements.txt",
})
TEXT_SUFFIXES = frozenset({".py", ".rb", ".md", ".txt", ".json", ".fth", ".html"})
REQUIRED_PATHS = (
    ".gitattributes",
    ".nojekyll",
    "README.md",
    "README_JP.md",
    "FIRST_READ.md",
    "FIRST_READ_JP.md",
    "SECURITY.md",
    "SECURITY_JP.md",
    "LICENSE",
    "VERSION",
    "requirements.txt",
    "docs/QUICKSTART.md",
    "docs/QUICKSTART_JP.md",
    "docs/WORD_REFERENCE.md",
    "docs/WORD_REFERENCE_JP.md",
    "docs/REFERENCES.md",
    "docs/REFERENCES_JP.md",
    "docs/README.md",
    "docs/README_JP.md",
    "docs/KNOWN_LIMITATIONS_0.1.md",
    "docs/KNOWN_LIMITATIONS_0.1_JP.md",
    "docs/RELEASE_NOTES_0.1.md",
    "docs/RELEASE_NOTES_0.1_RC1.md",
    "docs/RELEASE_CHECKLIST_0.1.md",
    "docs/RELEASE_AUDIT_0.1.md",
    "docs/RELEASE_SECURITY_AUDIT_PLAN.md",
    "docs/LICENSE_AND_SECURITY.md",
    "docs/LICENSE_AND_SECURITY_JP.md",
    "docs/PROJECT_ORIGIN.md",
    "docs/PROJECT_ORIGIN_JP.md",
    "docs/RELEASE_AUDIT_0.1.1_JP.md",
    "tools/release_tool.py",
    "workbench/min0_core_forth_vm.py",
    "workbench/min0_core_forth_vm.rb",
    "workbench/min0_core_forth_outer.py",
    "workbench/min0_core_forth_outer.rb",
    "workbench/min0_forth.py",
    "workbench/min0_forth.rb",
    "workbench/test_vm.py",
    "workbench/test_ruby_vm.rb",
    "workbench/cross_check.py",
    "workbench/cross_cli_check.py",
    "workbench/examples/basic.fth",
    "workbench/examples/hello.fth",
    "workbench/test_vectors/manifest.json",
    "viewer/trace-viewer-template.html",
    "viewer/value-trace.html",
    "viewer/value-trace-en.html",
)
FORBIDDEN_TEXT = (
    ("private-key-pem", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("personal-windows-path", re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+")),
    ("personal-file-uri", re.compile(r"(?i)file:/+[A-Z]:/+Users/+[^/\s]+")),
    (
        "codex-internal-reference",
        re.compile(r"(?i)(?:plugin" + r"://|codex-file-" + r"citation|\.codex[\\/])"),
    ),
)
FIXTURE_DECLARATION = re.compile(
    r"(?m)^([A-Z][A-Z0-9_]*(?:SEED|KEY))\s*="
)
FIXTURE_WARNING = "Never use this key"
FIXTURE_WARNINGS = (FIXTURE_WARNING, "Never use these keys")
VIEWER_NETWORK_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bfetch\s*\("),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\b"),
)
EXPECTED_LICENSE_SHA256 = "f597619c65a0712362d39b2a995e25bc77154964bdc6abdb71f73747d1c9ee08"
PROMINENT_NOTICE_REQUIREMENTS = {
    "README.md": ("FIRST_READ.md", "docs/LICENSE_AND_SECURITY.md"),
    "FIRST_READ.md": ("docs/LICENSE_AND_SECURITY.md",),
    "README_JP.md": ("FIRST_READ_JP.md", "docs/LICENSE_AND_SECURITY_JP.md"),
    "FIRST_READ_JP.md": ("docs/LICENSE_AND_SECURITY_JP.md",),
    "docs/LICENSE_AND_SECURITY.md": (
        "LICENSE", "SECURITY.md", "RELEASE_AUDIT_0.1.md",
        "KNOWN_LIMITATIONS_0.1.md", "THREAT_MODEL_R0.md",
    ),
}


def _allowed(relative: Path) -> bool:
    parts = relative.parts
    if not parts or any(part in EXCLUDED_PARTS for part in parts):
        return False
    if _is_internal_document(relative):
        return False
    if len(parts) == 1:
        return relative.name in EXPLICIT_TOP_LEVEL
    suffixes = ALLOWED_DIRECTORIES.get(parts[0])
    return suffixes is not None and relative.suffix in suffixes


def _is_internal_document(relative: Path) -> bool:
    """Reject conversation exports and chronological working notes from publication."""

    return relative.suffix.lower() == ".md" and any(
        pattern.search(relative.name) for pattern in INTERNAL_DOCUMENT_PATTERNS
    )


def collect_release_files(root: Path = PROJECT_ROOT) -> list[Path]:
    """Return the sorted allowlisted release file paths relative to ``root``."""

    root = root.resolve()
    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symbolic link is not allowed in release input: {relative.as_posix()}")
        if path.is_file() and _allowed(relative):
            files.append(relative)
    return sorted(files, key=lambda item: item.as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scan_text(relative: Path, text: str) -> list[str]:
    issues: list[str] = []
    for name, pattern in FORBIDDEN_TEXT:
        if pattern.search(text):
            issues.append(f"{relative.as_posix()}: forbidden {name}")
    declarations = FIXTURE_DECLARATION.findall(text)
    if declarations:
        for name in declarations:
            if "TEST" not in name and "FIXTURE" not in name:
                issues.append(
                    f"{relative.as_posix()}: fixture key name {name!r} lacks TEST/FIXTURE"
                )
        if not any(warning in text for warning in FIXTURE_WARNINGS):
            issues.append(
                f"{relative.as_posix()}: fixture key declaration lacks deployment warning"
            )
    return issues


def audit_tree(root: Path = PROJECT_ROOT) -> dict[str, object]:
    """Audit one source tree without changing it."""

    root = root.resolve()
    issues: list[str] = []
    try:
        files = collect_release_files(root)
    except ValueError as exc:
        files = []
        issues.append(str(exc))
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if _is_internal_document(relative):
            issues.append(
                f"{relative.as_posix()}: internal conversation/checkpoint document is not publishable"
            )
    selected = {path.as_posix() for path in files}
    for required in REQUIRED_PATHS:
        if required not in selected:
            issues.append(f"missing required release file: {required}")
    version_path = root / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else ""
    if not re.fullmatch(r"0\.1\.(?:0|[1-9][0-9]*)(?:-rc\.[1-9][0-9]*)?", version):
        issues.append("VERSION must be a 0.1.x release or 0.1.x-rc.N")
    license_path = root / "LICENSE"
    if license_path.is_file() and _sha256(license_path) != EXPECTED_LICENSE_SHA256:
        issues.append("LICENSE does not match the approved MIN0 CORE FORTH MIT text")
    for notice_path, required_links in PROMINENT_NOTICE_REQUIREMENTS.items():
        path = root / notice_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for required_link in required_links:
            if required_link not in text:
                issues.append(
                    f"{notice_path}: missing prominent notice link {required_link}"
                )
    for relative in files:
        path = root / relative
        if relative.suffix not in TEXT_SUFFIXES and relative.name not in {
            ".gitattributes", ".gitignore", "LICENSE", "VERSION",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(f"{relative.as_posix()}: text file is not UTF-8")
            continue
        issues.extend(_scan_text(relative, text))
        if relative.as_posix() in {
        "viewer/trace-viewer-template.html", "viewer/value-trace.html",
        }:
            for pattern in VIEWER_NETWORK_PATTERNS:
                if pattern.search(text):
                    issues.append(
                        f"{relative.as_posix()}: Viewer contains network-capable pattern {pattern.pattern!r}"
                    )
    excluded = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        relative = path.relative_to(root)
        if path.is_dir() and path.name in EXCLUDED_PARTS:
            excluded.append(relative.as_posix() + "/")
        elif path.is_file() and not _allowed(relative):
            excluded.append(relative.as_posix())
    return {
        "format": "min0-core-forth-release-audit/0.1",
        "version": version,
        "selected_file_count": len(files),
        "selected_files": [path.as_posix() for path in files],
        "excluded_top_level": excluded,
        "issues": sorted(set(issues)),
        "status": "pass" if not issues else "blocked",
    }


def _manifest_bytes(staging: Path, files: list[Path]) -> bytes:
    rows = [f"{_sha256(staging / relative)}  {relative.as_posix()}" for relative in files]
    return ("\n".join(rows) + "\n").encode("utf-8")


def _write_deterministic_zip(staging: Path, archive: Path, root_name: str) -> None:
    files = sorted(
        (path.relative_to(staging) for path in staging.rglob("*") if path.is_file()),
        key=lambda item: item.as_posix(),
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative in files:
            info = zipfile.ZipInfo(f"{root_name}/{relative.as_posix()}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, (staging / relative).read_bytes(), compresslevel=9)


def build_release(root: Path, output: Path) -> dict[str, object]:
    """Create clean staging, deterministic ZIP, and checksum after a passing audit."""

    root = root.resolve()
    output = output.resolve()
    audit = audit_tree(root)
    if audit["issues"]:
        raise RuntimeError("release audit is blocked:\n" + "\n".join(audit["issues"]))
    if output.exists():
        raise FileExistsError(f"release output already exists: {output}")
    version = str(audit["version"])
    root_name = f"min0-core-forth-{version}"
    staging = output / root_name
    staging.mkdir(parents=True)
    selected = [Path(item) for item in audit["selected_files"]]
    for relative in selected:
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, destination)
    (staging / "RELEASE_MANIFEST.txt").write_bytes(_manifest_bytes(staging, selected))
    archive = output / f"{root_name}.zip"
    _write_deterministic_zip(staging, archive, root_name)
    archive_sha256 = _sha256(archive)
    checksum = output / "SHA256SUMS.txt"
    checksum.write_text(f"{archive_sha256}  {archive.name}\n", encoding="ascii", newline="\n")
    return {
        "format": "min0-core-forth-release-build/0.1",
        "version": version,
        "selected_file_count": len(selected),
        "staging": str(staging),
        "archive": str(archive),
        "archive_sha256": archive_sha256,
        "checksums": str(checksum),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "build"))
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "audit":
        result = audit_tree(args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.output is None:
        parser.error("build requires --output")
    try:
        result = build_release(args.root, args.output)
    except (RuntimeError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
