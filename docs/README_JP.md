# MIN0 CORE FORTH 日本語文書索引

[英語版はこちらです](README.md)

## 最初に読む文書

- [ワード・ポケットリファレンス―次期候補の全78ワード](WORD_REFERENCE_JP.md)
- [localhost Live Viewerの起動と安全境界](LIVE_VIEWER_JP.md)
- [Mobile Learningの説明](MOBILE_FORTH_JP.md)
- [GitHub PagesでMobile Learningを実行する](https://min0.github.io/min0-core-forth/viewer/mobile-forth.html)
- [GitHub Pagesで仮想アセンブラを体験する](https://min0.github.io/min0-core-forth/viewer/virtual-assembler.html)
- [iPhone用オフライン閲覧パック](IPHONE_READING_PACK_JP.md)
- [FORTHの解釈・compile・実行を理解するためのノート](FORTH_EXECUTION_PHASES_JP.md)
- [CORE wordのcompile互換性解消計画](CORE_WORD_COMPILATION_PLAN_JP.md)
- [起動時65 wordのsemantics監査表](CORE_WORD_SEMANTICS_MATRIX_JP.md)
- [直接制御構造設計](DIRECT_CONTROL_V0_3_JP.md)
- [FOR/NEXT直接loop設計](FOR_NEXT_DIRECT_V0_2_JP.md)
- [FORTHの設計と学習のための参考資料](REFERENCES_JP.md)
- [Quick Start](QUICKSTART_JP.md)
- [Windows開発環境でのPython／Ruby全体試験](WINDOWS_DEVELOPMENT_TEST_JP.md)
- [CPU・FPGAへ共通する移植可能backend開発原則](PORTABLE_BACKEND_PRINCIPLES_JP.md)
- [学習の自由と安全な失敗の設計原則](LEARNING_FREEDOM_PRINCIPLES_JP.md)
- [小容量環境でも安全に失敗するための移植原則](SAFE_FAILURE_PORTABILITY_JP.md)
- [未知の機器を安全に調べるMIN0 Device Lab初心者ガイド](DEVICE_LAB_BEGINNER_GUIDE_JP.md)
- [プロジェクトの由来](PROJECT_ORIGIN_JP.md)
- [ライセンスと安全性](LICENSE_AND_SECURITY_JP.md)
- [既知の制限](KNOWN_LIMITATIONS_0.1_JP.md)
- [0.1.4ローカル候補ノート](RELEASE_NOTES_0.1.4_JP.md)
- [0.1.4ローカル候補監査](RELEASE_AUDIT_0.1.4_JP.md)
- [0.1.3互換性改善版リリースノート](RELEASE_NOTES_0.1.3_JP.md)
- [0.1.3リリース監査](RELEASE_AUDIT_0.1.3_JP.md)
- [0.1.2リリースノート](RELEASE_NOTES_0.1.2_JP.md)
- [0.1.2リリース監査](RELEASE_AUDIT_0.1.2_JP.md)
- [0.1.1リリース監査](RELEASE_AUDIT_0.1.1_JP.md)
- [リポジトリで最初に読む案内](../FIRST_READ_JP.md)
- [日本語版Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace.html)

## 詳細設計文書の分類

このフォルダーのそのほかのファイルは、実行可能仕様を積み上げた詳細記録です。試験、議論、将来の
実機移植から正確に参照できるよう、ファイル名を安定させています。

- VMと言語：bytecode、source、辞書、対話compiler、直接制御構造、回数指定loop、data、文字列
- 仮想assembler：CPU・FPGA共通契約、対象別backend profile、適合試験
- 機器学習：Device Lab、device manifest、仮想機器、失敗例から学ぶ調査手順
- 定義ワード：`DOES>` descriptor、source `DOES>`、constructor plan
- メモリと配置：memory profile、split dictionary、relocation、linker、image envelope
- 実行時境界：出力service、実行profile、verifier、sealed execution、W^X、capability
- 更新と信頼：署名image、anti-rollback、A/B導入、recovery、trust/root rotation、外部package、loader
- 観察と制御：trace、Viewer、Monitor、`DEFER`
- 公開資料：release notes、checklist、監査計画、監査結果、threat model、既知の制限

詳細記録の一部は、開発時に使った言語をそのまま保存しています。この索引と上の入口文書は日本語の
案内層です。コード、識別子、stack effect、ファイル名は言語に依存しない技術情報として扱います。
