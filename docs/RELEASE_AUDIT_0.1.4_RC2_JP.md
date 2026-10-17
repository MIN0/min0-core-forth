# MIN0 CORE FORTH 0.1.4-rc.2 候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.4_RC2.md)

候補版：`0.1.4-rc.2`

状態：準備中。tagとReleaseはまだ公開していません。

## Gate前に完了した証拠

- Phase C Mobile入力制御のPC画面評価：合格
- GitHub Pagesを使ったPhase C iPhone Safari評価：合格
- Mobile Python集中試験：10件成功
- Mobile JavaScript集中試験群：成功
- iPhone評価後にMobile HTMLのbuild識別を更新
- 準備差分の`git diff --check`：合格

## Gate A―未実施

- 利用者の通常Windows PowerShellで`python tools/run_all_checks.py`を実行する。
- Python suite、Ruby test file、Python／Ruby相互試験の全成功を必須とする。
- release allowlist監査を行い、問題0件を必須とする。
- 候補packageを2回作成し、ZIPのbyte一致を確認する。
- 最終commit、収録file数、byte数、SHA-256をplaceholderなしで記録する。

## Gate B―まだ許可しない

Gate A完了と利用者の明示的な公開確認まで、`v0.1.4-rc.2` tagとassetを公開しない。既存tagとassetは
変更しない。

## Gate C―未実施

公開後、新しいdirectoryへ公開ZIPとchecksumを取得し、hashとmanifestを検証する。展開artifact上の試験と
公開Pages buildも確認する。
