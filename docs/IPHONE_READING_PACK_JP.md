# MIN0 CORE FORTH iPhone学習パック

## 目的

開発中のMIN0 CORE FORTHを正式公開せず、所有者のiPhoneへコピーし、外出中に
オフラインで資料閲覧とFORTHの基礎学習ができるようにする。正式COREとは分離した、
個人学習・確認専用の選別済みsnapshotである。

## 内容

- `START_HERE_JP.txt`：iPhoneで最初に読む説明
- `MIN0_CORE_FORTH_READER_JP.html`：主要日本語資料を一つにまとめた入口
- `MIN0_FORTH_MOBILE.html`：編集・実行・スタック確認ができる個人学習用互換サブセット
- `documents/`：HTMLが表示できない場合にも読める番号付きUTF-8 text
- `examples/`：FORTH例題
- `source/`：Python／Ruby主要ソースの閲覧用text
- `guided-viewer.html`：自己完結型の静的Guided Viewer
- `MANIFEST.json`、`SHA256SUMS.txt`：内容一覧と整合性情報

Git履歴、秘密情報、通常のbuild生成物、個人pathは収録しない。Mobile Learningは
PCなしで動くが、正式COREの全機能を動かすLive Viewer serverは含めない。

## 作成

正本repoで次を実行する。

```powershell
python tools/build_iphone_reading_pack.py --output "出力先\min0-core-forth-iphone-reading.zip"
```

ZIP本体と、そのZIPの`.sha256`が生成される。

## iPhoneへの移動

1. ZIPをDropboxまたはiCloud Driveへコピーする。
2. iPhoneでZIPを「ファイル」へ保存し、必要ならオフライン利用を指定する。
3. ZIPをタップして展開する。
4. `START_HERE_JP.txt`を読み、実行学習には`MIN0_FORTH_MOBILE.html`を開く。
5. 資料閲覧には`MIN0_CORE_FORTH_READER_JP.html`を開く。
6. HTML previewが使えない場合は`documents/`の番号付きtextを開く。

`MIN0_FORTH_MOBILE.html`と`guided-viewer.html`はnetwork不要だが、iPhoneのfile previewが
JavaScriptを制限する場合がある。その場合は共有メニューからSafariなどへ渡す。
それも使えない場合、資料、例題、sourceはtextとして閲覧できる。
