"""Build a privacy-filtered, offline iPhone reading pack."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)

DOCUMENTS = (
    ("01_README_JP.txt", "README_JP.md", "概要"),
    ("02_FIRST_READ_JP.txt", "FIRST_READ_JP.md", "最初に読む説明"),
    ("03_QUICKSTART_JP.txt", "docs/QUICKSTART_JP.md", "クイックスタート"),
    ("04_WORD_REFERENCE_JP.txt", "docs/WORD_REFERENCE_JP.md", "74ワード・リファレンス"),
    ("05_LIVE_VIEWER_JP.txt", "docs/LIVE_VIEWER_JP.md", "Live Viewer説明"),
    ("06_VIEWER_GUIDE_JP.txt", "docs/VIEWER_GUIDE_V0_1.md", "Guided Viewer操作"),
    ("07_KNOWN_LIMITATIONS_JP.txt", "docs/KNOWN_LIMITATIONS_0.1_JP.md", "既知の制限"),
    ("08_LICENSE_SECURITY_JP.txt", "docs/LICENSE_AND_SECURITY_JP.md", "ライセンスと安全"),
    ("09_PROJECT_ORIGIN_JP.txt", "docs/PROJECT_ORIGIN_JP.md", "プロジェクトの由来"),
    ("10_MOBILE_FORTH_JP.txt", "docs/MOBILE_FORTH_JP.md", "スマホ学習版の説明"),
)

EXAMPLES = (
    ("basic.fth.txt", "workbench/examples/basic.fth"),
    ("hello.fth.txt", "workbench/examples/hello.fth"),
)

SOURCES = (
    "workbench/min0_core_forth_vm.py",
    "workbench/min0_core_forth_vm.rb",
    "workbench/min0_core_forth_compiler.py",
    "workbench/min0_core_forth_compiler.rb",
    "workbench/min0_core_forth_outer.py",
    "workbench/min0_core_forth_outer.rb",
    "workbench/min0_forth.py",
    "workbench/min0_forth.rb",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def current_revision(root: Path = ROOT) -> str:
    result = subprocess.run(
        [
            "git", "-c", f"safe.directory={root.resolve().as_posix()}",
            "rev-parse", "--short", "HEAD",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _read(relative: str, root: Path = ROOT) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _reader_html(revision: str, documents: list[tuple[str, str]]) -> str:
    sections = []
    for index, (title, text) in enumerate(documents):
        open_attribute = " open" if index == 0 else ""
        sections.append(
            f'<details{open_attribute}><summary>{html.escape(title)}</summary>'
            f'<pre>{html.escape(text)}</pre></details>'
        )
    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang=\"ja\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>MIN0 CORE FORTH iPhone Reader</title>
<style>
:root{{color-scheme:light dark;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif}}
body{{max-width:860px;margin:auto;padding:16px;line-height:1.65;background:#0e171d;color:#eef7f8}}
h1{{font-size:1.65rem}} .meta{{color:#b8cbd0}} details{{margin:12px 0;background:#17262d;border-radius:10px;padding:10px}}
summary{{font-size:1.1rem;font-weight:700;cursor:pointer}} pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:0.94rem/1.65 -apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif}}
a{{color:#ffd166}} code{{font-family:ui-monospace,monospace}}
</style></head><body>
<h1>MIN0 CORE FORTH iPhone Reader</h1>
<p class=\"meta\">開発候補 commit {html.escape(revision)}。閲覧専用・オフライン用です。</p>
<p>見出しをタップして開閉できます。FORTH実行機能はありません。静的Guided Viewerは同梱の
<code>guided-viewer.html</code>で試せますが、iPhoneのfile previewでは動作が制限される場合があります。</p>
{body}
</body></html>"""


def _mobile_html(revision: str, root: Path = ROOT) -> bytes:
    template = _read("viewer/mobile-forth-template.html", root)
    core = _read("viewer/mobile-forth-core.js", root)
    core_marker = "/*__MIN0_MOBILE_CORE__*/"
    revision_marker = "__MIN0_REVISION__"
    if template.count(core_marker) != 1 or template.count(revision_marker) != 1:
        raise ValueError("mobile template markers are missing or duplicated")
    return template.replace(core_marker, core).replace(
        revision_marker, revision
    ).encode("utf-8")


def build_pack(output: Path, *, root: Path = ROOT, revision: str | None = None) -> dict:
    revision = revision or current_revision(root)
    version = _read("VERSION", root).strip()
    files: dict[str, bytes] = {}
    reader_documents: list[tuple[str, str]] = []

    for target, source, title in DOCUMENTS:
        text = _read(source, root)
        files[f"documents/{target}"] = text.encode("utf-8")
        reader_documents.append((title, text))
    for target, source in EXAMPLES:
        files[f"examples/{target}"] = _read(source, root).encode("utf-8")
    for source in SOURCES:
        target = "source/" + Path(source).name + ".txt"
        files[target] = _read(source, root).encode("utf-8")

    files["MIN0_CORE_FORTH_READER_JP.html"] = _reader_html(
        revision, reader_documents
    ).encode("utf-8")
    files["guided-viewer.html"] = (root / "viewer/value-trace.html").read_bytes()
    files["MIN0_FORTH_MOBILE.html"] = _mobile_html(revision, root)
    start_text = f"""MIN0 CORE FORTH iPhone閲覧パック

開発候補commit: {revision}
VERSION表記: {version}（正式リリースは保留中）

1. ZIPをiPhoneの「ファイル」へ保存して展開します。
2. FORTHを作成・実行する場合はMIN0_FORTH_MOBILE.htmlを開きます。
3. 資料を読む場合はMIN0_CORE_FORTH_READER_JP.htmlを開きます。
4. HTML表示が利用できない場合はdocuments内の番号付きtxtを開きます。
5. examplesは学習用FORTH、sourceはPython／Ruby主要ソースの閲覧用です。
6. guided-viewer.htmlは静的教材ですが、iPhoneのfile previewではJavaScriptが
   制限される場合があります。

MIN0_FORTH_MOBILE.htmlは個人学習用の互換サブセットで、PCや通信なしに実行できます。
正式COREの全機能を動かすLive ViewerにはWindows PC上のserverが必要です。
Git履歴、秘密情報、build生成物、個人pathは収録していません。
"""
    files["START_HERE_JP.txt"] = start_text.encode("utf-8")

    manifest = {
        "format": "min0-core-forth-iphone-reading-pack/0.1",
        "revision": revision,
        "version_label": version,
        "release_status": "development-candidate-not-released",
        "file_count_without_checksums": len(files),
        "files": sorted(files),
    }
    files["MANIFEST.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    checksums = "".join(
        f"{sha256(data)}  {name}\n" for name, data in sorted(files.items())
    )
    files["SHA256SUMS.txt"] = checksums.encode("ascii")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)

    result = {
        "output": str(output),
        "sha256": sha256(output.read_bytes()),
        "file_count": len(files),
        "revision": revision,
        "version_label": version,
    }
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{result['sha256']}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the iPhone offline reading pack")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_pack(args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
