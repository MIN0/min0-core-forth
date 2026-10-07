"""Build a deployable HTTPS/offline iPhone web-app package."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
CORE_MARKER = "/*__MIN0_MOBILE_CORE__*/"
REVISION_MARKER = "__MIN0_REVISION__"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def current_revision(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.resolve().as_posix()}", "rev-parse", "--short", "HEAD"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def render_index(revision: str, root: Path = ROOT) -> str:
    template = (root / "viewer" / "mobile-forth-template.html").read_text(encoding="utf-8")
    core = (root / "viewer" / "mobile-forth-core.js").read_text(encoding="utf-8")
    rendered = template.replace(CORE_MARKER, core).replace(REVISION_MARKER, revision)
    head = """<link rel="manifest" href="./manifest.webmanifest">
  <meta name="theme-color" content="#091319">
  <meta name="apple-mobile-web-app-title" content="MIN0 FORTH">"""
    registration = """<script>
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}
</script>"""
    return rendered.replace("</head>", head + "\n</head>", 1).replace(
        "</body>", registration + "\n</body>", 1
    )


def manifest() -> str:
    value = {
        "name": "MIN0 CORE FORTH Mobile Learning",
        "short_name": "MIN0 FORTH",
        "description": "Personal offline FORTH learning environment",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "background_color": "#091319",
        "theme_color": "#091319",
        "lang": "ja",
    }
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def service_worker(revision: str) -> str:
    return f'''"use strict";
const CACHE_NAME = "min0-forth-{revision}";
const APP_FILES = ["./", "./index.html", "./manifest.webmanifest"];
self.addEventListener("install", event => {{
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_FILES)).then(() => self.skipWaiting()));
}});
self.addEventListener("activate", event => {{
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
}});
self.addEventListener("fetch", event => {{
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {{
    const copy = response.clone();
    caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    return response;
  }})));
}});
'''


def readme(revision: str) -> str:
    return f"""MIN0 CORE FORTH Mobile Learning Web App

revision: {revision}

このZIPはWebサーバー配置用です。iPhoneの「ファイル」からindex.htmlを直接開いても
JavaScriptは実行されません。HTTPSの静的Webサーバーへ3ファイルを同じ場所に配置します。

- index.html
- manifest.webmanifest
- sw.js

iPhoneではSafariで配置先URLを開き、共有メニューの「ホーム画面に追加」で
「Webアプリとして開く」を有効にします。初回読込み後はservice workerが必要ファイルを
端末へ保存するため、オフラインでも起動できます。

このアプリは外部APIへFORTHソースを送信しません。保存先はブラウザのlocalStorageです。
"""


def build(output: Path, *, root: Path = ROOT, revision: str | None = None) -> dict[str, object]:
    revision = revision or current_revision(root)
    files = {
        "index.html": render_index(revision, root).encode("utf-8"),
        "manifest.webmanifest": manifest().encode("utf-8"),
        "sw.js": service_worker(revision).encode("utf-8"),
        "README_JP.txt": readme(revision).encode("utf-8"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    digest = sha256(output.read_bytes())
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return {"output": str(output), "sha256": digest, "revision": revision, "files": sorted(files)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
