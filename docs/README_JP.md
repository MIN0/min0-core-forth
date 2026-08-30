# MIN0 CORE FORTH 日本語文書索引

[英語版はこちらです](README.md)

## 最初に読む文書

- [ワード・ポケットリファレンス―起動時の全61ワード](WORD_REFERENCE_JP.md)
- [FORTHの設計と学習のための参考資料](REFERENCES_JP.md)
- [Quick Start](QUICKSTART_JP.md)
- [プロジェクトの由来](PROJECT_ORIGIN_JP.md)
- [ライセンスと安全性](LICENSE_AND_SECURITY_JP.md)
- [既知の制限](KNOWN_LIMITATIONS_0.1_JP.md)
- [0.1.2リリースノート](RELEASE_NOTES_0.1.2_JP.md)
- [0.1.2リリース監査](RELEASE_AUDIT_0.1.2_JP.md)
- [0.1.1リリース監査](RELEASE_AUDIT_0.1.1_JP.md)
- [リポジトリで最初に読む案内](../FIRST_READ_JP.md)
- [日本語版Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace.html)

## 詳細設計文書の分類

このフォルダーのそのほかのファイルは、実行可能仕様を積み上げた詳細記録です。試験、議論、将来の
実機移植から正確に参照できるよう、ファイル名を安定させています。

- VMと言語：bytecode、source、辞書、対話compiler、条件分岐、loop、data、文字列
- 定義ワード：`DOES>` descriptor、source `DOES>`、constructor plan
- メモリと配置：memory profile、split dictionary、relocation、linker、image envelope
- 実行時境界：出力service、実行profile、verifier、sealed execution、W^X、capability
- 更新と信頼：署名image、anti-rollback、A/B導入、recovery、trust/root rotation、外部package、loader
- 観察と制御：trace、Viewer、Monitor、`DEFER`
- 公開資料：release notes、checklist、監査計画、監査結果、threat model、既知の制限

詳細記録の一部は、開発時に使った言語をそのまま保存しています。この索引と上の入口文書は日本語の
案内層です。コード、識別子、stack effect、ファイル名は言語に依存しない技術情報として扱います。
