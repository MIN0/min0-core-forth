"""Build the self-contained offline Mobile Learning HTML."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_MARKER = "/*__MIN0_MOBILE_CORE__*/"
MONITOR_MARKER = "/*__MIN0_MONITOR_STATE__*/"
SESSION_MARKER = "/*__MIN0_MOBILE_SESSION__*/"
SCHEDULER_MARKER = "/*__MIN0_MOBILE_SCHEDULER__*/"
REVISION_MARKER = "__MIN0_REVISION__"


def current_revision(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.resolve().as_posix()}", "rev-parse", "--short", "HEAD"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def build(output: Path, *, root: Path = ROOT, revision: str | None = None) -> Path:
    template = (root / "viewer" / "mobile-forth-template.html").read_text(encoding="utf-8")
    modules = {
        CORE_MARKER: root / "viewer" / "mobile-forth-core.js",
        MONITOR_MARKER: root / "viewer" / "mobile-monitor-state.js",
        SESSION_MARKER: root / "viewer" / "mobile-forth-session.js",
        SCHEDULER_MARKER: root / "viewer" / "mobile-forth-scheduler.js",
    }
    if any(template.count(marker) != 1 for marker in modules) or template.count(REVISION_MARKER) != 1:
        raise ValueError("mobile template markers are missing or duplicated")
    rendered = template
    for marker, path in modules.items():
        rendered = rendered.replace(marker, path.read_text(encoding="utf-8"))
    rendered = rendered.replace(REVISION_MARKER, revision or current_revision(root))
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
