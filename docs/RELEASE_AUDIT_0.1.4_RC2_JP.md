# MIN0 CORE FORTH 0.1.4-rc.2 候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.4_RC2.md)

候補版：`0.1.4-rc.2`

状態：Gate A合格。tagとReleaseはまだ公開していません。

## Gate前に完了した証拠

- Phase C Mobile入力制御のPC画面評価：合格
- GitHub Pagesを使ったPhase C iPhone Safari評価：合格
- Mobile Python集中試験：10件成功
- Mobile JavaScript集中試験群：成功
- iPhone評価後にMobile HTMLのbuild識別を更新
- 準備差分の`git diff --check`：合格

## Gate A―合格

- 実施日：2026-10-17（Asia/Tokyo）
- 利用者の通常Windows PowerShell：`python tools\run_all_checks.py`
- Python suite：成功
- Ruby：50 test fileすべて成功
- Python／Ruby相互試験：51 check fileすべて成功
- 最終表示：`ALL CHECKS PASSED`
- release allowlist監査：492ファイル、問題0件
- 文書／release tool集中試験：14/14成功
- 候補packageを独立した2 directoryへ作成し、ZIPのbyte一致を確認する。
- 最終ZIPのbyte数とSHA-256は自己参照を避け、配布物の隣の`SHA256SUMS.txt`と公開記録へ保存する。

制限付きCodex sandboxでは子processの`ruby.exe`が終了コード`3221225506`で拒否される。Python suite内の
5失敗もすべてRuby launcher比較試験であり、利用者の通常PowerShellでは再現せず、全試験が成功した。

## Gate B―まだ許可しない

利用者の明示的な公開確認まで、`v0.1.4-rc.2` tagとassetを公開しない。既存tagとassetは
変更しない。

## Gate C―未実施

公開後、新しいdirectoryへ公開ZIPとchecksumを取得し、hashとmanifestを検証する。展開artifact上の試験と
公開Pages buildも確認する。
