"""Build the self-contained offline Mobile Learning HTML."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_MARKER = "/*__MIN0_MOBILE_CORE__*/"
REVISION_MARKER = "__MIN0_REVISION__"


def current_revision(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.resolve().as_posix()}", "rev-parse", "--short", "HEAD"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def build(output: Path, *, root: Path = ROOT, revision: str | None = None) -> Path:
    template = (root / "viewer" / "mobile-forth-template.html").read_text(encoding="utf-8")
    core = (root / "viewer" / "mobile-forth-core.js").read_text(encoding="utf-8")
    if template.count(CORE_MARKER) != 1 or template.count(REVISION_MARKER) != 1:
        raise ValueError("mobile template markers are missing or duplicated")
    rendered = template.replace(CORE_MARKER, core).replace(REVISION_MARKER, revision or current_revision(root))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "viewer" / "mobile-forth.html")
    args = parser.parse_args()
    print(build(args.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
