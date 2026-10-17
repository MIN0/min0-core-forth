# MIN0 CORE FORTH 0.1.4-rc.3 候補監査

[English version](RELEASE_AUDIT_0.1.4_RC3.md)

候補版：`0.1.4-rc.3`

状態：Gate A合格。評価用pre-releaseのtagとreleaseを作成できる。

## 実装済み証拠

- Safe `VARIABLE`、検査付き`@`／`!`の集中試験：合格
- Pause中の安全な変数編集とAbort復旧の集中試験：合格
- `BREAK`のPause、Continue、Abort集中試験：合格
- PC Viewer実画面評価：合格
- release allowlist監査：合格

## Gate A―公開前

- [x] iPhone SafariでSafe VARIABLE、Pause中編集、`BREAK`を確認
- [x] 利用者の通常Windows PowerShellで`python tools\run_all_checks.py`が`ALL CHECKS PASSED`
- [x] release allowlist監査が問題0件
- [x] 文書／release tool集中試験が成功
- [x] 独立した2 directoryで作ったZIPがbyte一致

実施日：2026-10-17（Asia/Tokyo）。iPhone Safariではsource build `5772353`を使用し、Safe VARIABLEの
正常終了、Pause中の変数表示・編集、`BREAK`の8 steps一時停止と継続後13 steps正常終了を確認した。
通常PowerShellの全体試験はPython suite 1、Ruby 50 files、言語間51 checksがすべて成功し、
`ALL CHECKS PASSED`となった。集中試験18/18、Mobile JavaScript 7/7、allowlist監査496ファイル・問題0件。
独立した2 directoryで生成した候補ZIPはbyte数とSHA-256が一致した。

Codex sandboxでは子processの`ruby.exe`が終了コード`3221225506`で拒否されるため、Rubyを含む最終Gate Aは
利用者の通常PowerShellで行う。この制約は製品codeの失敗と区別する。

## Gate B―評価用pre-release公開

- [ ] annotated tag `v0.1.4-rc.3`を作成
- [ ] pre-releaseとして公開し、`Latest`にしない
- [ ] ZIPと`SHA256SUMS.txt`をassetとして添付
- [ ] 既存tagとassetを変更しない

## Gate C―公開後

- [ ] 公開assetを新しいdirectoryへ再取得
- [ ] ZIP byte数、SHA-256、manifest全項目を候補と照合
- [ ] 展開treeのallowlist監査とMobile集中試験を実行
- [ ] Mobile LearningとVirtual AssemblerのPages配信を確認

Gate BとGate Cの確定値は完了時に本書へ追記する。
