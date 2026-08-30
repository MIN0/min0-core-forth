# MIN0 CORE FORTH 0.1.2 文書整備版リリース監査

[英語版はこちらです](RELEASE_AUDIT_0.1.2.md)

状態：Gate A合格。公開と公開後の独立検証は未実施です。

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

未実施です。

## Gate C：公開後

未実施です。公開ZIP、checksum、tag付きsource、日英経路、Viewer、安全alertを公開後に再取得または
再照合します。

本監査はMIN0 CORE FORTHだけを対象とし、MSX0-FORTHを変更または公開しません。
