"""Build a deployable HTTPS/offline iPhone web-app package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def current_revision(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.resolve().as_posix()}", "rev-parse", "--short", "HEAD"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _mobile_builder():
    path = Path(__file__).with_name("build_mobile_forth.py")
    spec = importlib.util.spec_from_file_location("min0_build_mobile_forth_for_pwa", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Mobile FORTH builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_index(revision: str, root: Path = ROOT) -> str:
    rendered = _mobile_builder().render(root=root, revision=revision)
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

評価時は、古いservice worker cacheとの取り違えを避けるため、最初に次の形式で開きます。

index.html?eval={revision}

詳しい確認順序と期待結果はEVALUATION_JP.txtを参照してください。
"""


def evaluation_guide(revision: str) -> str:
    return f"""MIN0 CORE FORTH Mobile Learning iPhone評価手順

評価対象revision: {revision}

準備

1. ZIPの5ファイルを同じdirectoryへ展開し、HTTPSの静的Web serverへ配置します。
2. Safariで `index.html?eval={revision}` を開きます。
3. 画面上部のbuild表示が `{revision}` であることを確認します。
4. 最初のRun後、実行環境が「Worker分離モード」であることを確認します。
   「互換モード」の場合は機能試験を続けられますが、Worker評価は保留として画面を記録してください。

試験A：正常終了

入力：
2 3 +

期待結果：
- 状態：正常終了
- 最終stack：<1> 5
- エラー表示なし

試験B：安全な失敗と復旧

入力：
7 0 /MOD

期待結果：
- 状態：エラー停止
- 0除算のエラーを表示
- エラー停止時stackを確認可能
- 「実行前へ復旧」後のstack：<0>

試験C：実行中操作

入力：
: SPIN BEGIN 1 DROP AGAIN ;
SPIN

順序：
1. Run
2. chunk番号と累計命令境界が増えることを確認
3. Pause → 状態が「一時停止」
4. 1命令 → 1命令進んで再び「一時停止」
5. Continue → 「実行中」
6. 安全停止 → 「安全停止」
7. 現在位置がSPIN、呼出し履歴にCALL_RETURNがあることを確認
8. 実行前へ復旧 → stackが<0>

試験D：ホーム画面とオフライン

1. Safariの共有メニューから「ホーム画面に追加」を選びます。
2. 追加したアプリをオンラインで一度起動します。
3. アプリを閉じ、機内モードにします。
4. ホーム画面から再起動し、`2 3 +`が正常終了することを確認します。
5. 試験後は機内モードを解除します。

結果記入欄

- build表示：
- 実行環境表示：Worker分離 / 互換モード / その他
- 試験A：OK / NG
- 試験B：OK / NG
- 試験C：OK / NG
- 試験D：OK / NG
- iPhone機種：
- iOS version：
- Safari／ホーム画面で気付いた点：
"""


def build(output: Path, *, root: Path = ROOT, revision: str | None = None) -> dict[str, object]:
    revision = revision or current_revision(root)
    files = {
        "index.html": render_index(revision, root).encode("utf-8"),
        "manifest.webmanifest": manifest().encode("utf-8"),
        "sw.js": service_worker(revision).encode("utf-8"),
        "README_JP.txt": readme(revision).encode("utf-8"),
        "EVALUATION_JP.txt": evaluation_guide(revision).encode("utf-8"),
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
