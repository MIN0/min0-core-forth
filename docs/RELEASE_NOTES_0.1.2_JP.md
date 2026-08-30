# MIN0 CORE FORTH 0.1.2 リリースノート

[英語版はこちらです](RELEASE_NOTES_0.1.2.md)

この文書整備版は、`0.1.1`公開後に追加した初心者向け／上級者向け学習経路を正式な配布物へ収録します。
FORTH言語の意味、VM命令集合、辞書動作、image format、安全modelの実験は変更しません。

## 日英それぞれの入口

- README、Quick Start、最初に読む案内、安全方針、projectの由来、既知の制限、監査、文書索引に、
  独立した英語版と日本語版の経路を用意しました。
- Guided Viewerは、同じ測定済みtrace dataから生成する英語版と日本語版を持ちます。
- 英語の入口文書へ日本語が混入していないことと、各READMEが同じ言語の経路へ進むことを自動検査します。

## 学習資料

- `WORDS`が表示する起動時の全61ワードを説明するワード・ポケットリファレンスを追加しました。stack effect、
  使用場所、現在の制限、`CREATE ... DOES>`、`DEFER ' ['] IS ACTION-OF`による動的切替えを含みます。
- READMEとQuick Startからポケットリファレンスへ目立つ導線を追加しました。
- FORTH設計と学習のための参考資料では、FIG-Forth、CF FORTH、RETRO FORTH、入門書、実装解説書、
  小規模MPU資料へ目的別に進めます。
- 参考資料は`forth-in-motion`の日英source listを出典として示し、第三者の書籍や実装を収録しません。

## 変更しない境界

- `v0.1.0`と`v0.1.1`のtagおよび配布物は変更しません。
- MSX0-FORTHは独立しており、本リリースでは変更しません。
- MIT Licenseは利用許諾であり、安全性の認証ではありません。
- repository内の署名seedとHMAC鍵は、引き続き公開された決定的試験用fixtureです。

## 検証対象

- Python 298テスト
- Ruby 46テストファイル
- Python／Ruby相互検査49ファイル
- 公開allowlist 380ファイル
- バイト単位で一致する再現可能package

公開前から公開後までの証拠は[`RELEASE_AUDIT_0.1.2_JP.md`](RELEASE_AUDIT_0.1.2_JP.md)に記録します。
