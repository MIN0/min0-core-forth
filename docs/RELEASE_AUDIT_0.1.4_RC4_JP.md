# MIN0 CORE FORTH 0.1.4-rc.4 候補監査

[English version](RELEASE_AUDIT_0.1.4_RC4.md)

候補版：`0.1.4-rc.4`

状態：Gate A合格。Ruby 3.4.11、JSON 2.9.1、OpenSSL 3.6.4で一括試験に成功した。

## 候補差分

- 評価済みSafe `VARIABLE`、検査付き`@`／`!`、Pause中編集、`BREAK`実装を保持する。
- Quick StartのRuby 4.0をrelease基準のRuby 3.4系へ訂正する。
- Windows Gate A interpreterとしてRuby 3.4.11 x64-mingw-ucrtを記録する。
- 機器別利用案内とCapability Tour方針を追加する。
- 既存`v0.1.4-rc.3` tagは変更せず、未公開のまま保持する。

## Gate A―公開前

- [x] 利用者の通常PowerShellでRuby 3.4.11 x64-mingw-ucrtを確認
- [x] 利用者の通常PowerShellでJSON 2.9.1／OpenSSL 3.6.4を確認
- [x] Ruby 3.4.11環境で`python tools\run_all_checks.py`を実行し`ALL CHECKS PASSED`（Python 1、Ruby 50、言語間51）
- [x] release allowlist監査が500ファイル、問題0件
- [x] 文書／release tool集中試験が14/14成功
- [x] 独立した2 directoryで作ったZIPがbyte一致（外部`SHA256SUMS.txt`に最終値を記録）

## Gate B―評価用pre-release公開

- [x] annotated tag `v0.1.4-rc.4`を作成
- [x] pre-releaseとして公開し、`Latest`にしない
- [x] ZIPと`SHA256SUMS.txt`をassetとして添付
- [x] 既存tagとassetを変更しない

公開先：<https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.4-rc.4>

## Gate C―公開後

- [ ] 公開assetを新しいdirectoryへ再取得
- [ ] ZIP byte数、SHA-256、manifest全項目を候補と照合
- [ ] 展開treeのallowlist監査とMobile集中試験を実行
- [ ] Mobile LearningとVirtual AssemblerのPages配信を確認
