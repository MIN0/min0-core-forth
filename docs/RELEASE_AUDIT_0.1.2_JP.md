# MIN0 CORE FORTH 0.1.2 文書整備版リリース監査

[英語版はこちらです](RELEASE_AUDIT_0.1.2.md)

状態：Gate A、Gate B、Gate Cすべて合格。`v0.1.2`を公開し、公開物を独立して再取得して検証済みです。

## 対象範囲

`0.1.2`は`0.1.1`のFORTHの意味と実行可能な安全実験を変更しません。日英の案内層、英語版Guided Viewer、
ワード・ポケットリファレンス、学習資料、それらの完全性と言語分離を守る試験とrelease ruleが対象です。
`v0.1.0`と`v0.1.1`のtagおよび配布物は変更しません。

## Gate A：公開前

- 公開allowlist：380ファイル、問題0
- Python：298テスト合格
- Ruby：46テストファイル合格
- Python／Ruby相互検査：49ファイル合格
- local Markdown link：切れ0
- 言語経路：READMEの指定された先頭行を除く英語入口文書への日本語混入0、日英README経路、参考資料の
  対応、ポケットリファレンス全61ワードの一致を確認
- 独立した二回の`0.1.2` ZIP生成：バイト単位で一致。最終的な公開物のdigestは、監査記録の自己参照を
  避けるためZIP横の`SHA256SUMS.txt`へ記録
- GitHub secret-scanning alerts：open 0
- GitHub Dependabot alerts：open 0
- GitHub Pages：`main`から構築済み、HTTPS強制
- 公開前に`v0.1.2` tag／Releaseが存在しないことと、`v0.1.1`が変更されていない最新Releaseであることを確認

## Gate B：公開

- [公式v0.1.2リリース](https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.2)
- 公開日時：2026-08-30 22:36:50（日本時間）
- tag commit：`e34d203837ddc6bbd3ac1262d0b0c72d69c68af1`
- 配布物：`min0-core-forth-0.1.2.zip`、630759バイト
- SHA-256：`1fa73ed9278acda7dfa491fcf090e0f14175e13144727ad8c896e0ecd466f522`
- `SHA256SUMS.txt`：92バイト。記載したZIP digestとGitHub asset metadataが一致
- draftでもpre-releaseでもない通常Releaseとして公開し、latest releaseになったことを確認

## Gate C：公開後

- 公開ZIPと`SHA256SUMS.txt`を新しいdirectoryへ取得。ZIPのsizeとSHA-256が、公開前の最終物、checksum、
  GitHub asset metadataと一致
- ZIP内の監査対象380ファイルと`RELEASE_MANIFEST.txt`を照合し、全SHA-256一致、欠落0、余分0
- remote `v0.1.2` tagの380 blobと公開ZIP展開物をpathおよびGit blob単位で照合し、欠落0、余分0、差0
- 公開ZIP展開物でrelease audit 380ファイル・問題0、Python 298、Ruby 46、相互検査49に合格
- GitHub Pagesはtag commit `e34d203837ddc6bbd3ac1262d0b0c72d69c68af1`からHTTPS強制で構築済み。
  日本語版／英語版ViewerのSHA-256はtag側とそれぞれ完全一致：
  `8994161f5d83f39b194d658698ba211283ceab839a6d9d539a5e5ca56d89f853`、
  `ed5f6a61b16b3f2bc86f11cc378f8547fb9c9dd8938fa61de6e56d54571b27c8`
- 公開後のGitHub secret-scanning alertsはopen 0、Dependabot alertsはopen 0
- この最終監査記録をmainへ追加する前に、remote `main`と`v0.1.2`が同じrelease commitを指すことを確認。
  tagとrelease assetは変更しない履歴証拠として保存

本監査はMIN0 CORE FORTHだけを対象とし、MSX0-FORTHを変更または公開しません。
