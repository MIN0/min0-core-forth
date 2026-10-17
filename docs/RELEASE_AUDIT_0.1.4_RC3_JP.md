# MIN0 CORE FORTH 0.1.4-rc.3 候補監査

[English version](RELEASE_AUDIT_0.1.4_RC3.md)

候補版：`0.1.4-rc.3`

状態：準備中。公開前Gateを順番に記録し、合格するまでtagとreleaseを作成しない。

## 実装済み証拠

- Safe `VARIABLE`、検査付き`@`／`!`の集中試験：合格
- Pause中の安全な変数編集とAbort復旧の集中試験：合格
- `BREAK`のPause、Continue、Abort集中試験：合格
- PC Viewer実画面評価：合格
- release allowlist監査：合格

## Gate A―公開前

- [ ] iPhone SafariでSafe VARIABLE、Pause中編集、`BREAK`を確認
- [ ] 利用者の通常Windows PowerShellで`python tools\run_all_checks.py`が`ALL CHECKS PASSED`
- [ ] release allowlist監査が問題0件
- [ ] 文書／release tool集中試験が成功
- [ ] 独立した2 directoryで作ったZIPがbyte一致

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

各Gateの確定値は完了時に本書へ追記する。
