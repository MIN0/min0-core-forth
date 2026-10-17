# MIN0 CORE FORTH 0.1.4-rc.2 候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.4_RC2.md)

候補版：`0.1.4-rc.2`

状態：評価用pre-release `v0.1.4-rc.2`についてGate A、B、C合格。

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
- 候補packageを独立した2 directoryへ作成し、ZIPのbyte一致を確認した。
- 最終ZIPのbyte数とSHA-256は自己参照を避け、配布物の隣の`SHA256SUMS.txt`と公開記録へ保存する。

制限付きCodex sandboxでは子processの`ruby.exe`が終了コード`3221225506`で拒否される。Python suite内の
5失敗もすべてRuby launcher比較試験であり、利用者の通常PowerShellでは再現せず、全試験が成功した。

## Gate B―評価用pre-release公開

- 公開日時：2026-10-17 13:10 JST
- annotated tag：`v0.1.4-rc.2`、commit `60b6baa0067eed3211f03b4a2b1727656fced2e3`
- Release：<https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.4-rc.2>
- 状態：公開評価用pre-release。正式版ではなく、`Latest`ではない。
- ZIP：`min0-core-forth-0.1.4-rc.2.zip`、960281 byte
- ZIP SHA-256：`2f74f1d019876bb07aafc4a9950051748e5904c018474ed746baf3d08da7b161`
- `SHA256SUMS.txt`を別assetとして公開
- 既存tagとassetは変更していない

## Gate C―公開後の独立確認

- 公開ZIPとchecksumを新しいdirectoryへ再取得した。
- 再取得ZIPのbyte数とSHA-256はGate A候補および公開checksum fileと一致した。
- manifest全492項目の存在とSHA-256一致を確認し、欠落・不一致0件。
- 展開treeのrelease allowlist監査は492ファイル、問題0件。
- 展開artifact上でMobile Python試験と7群のMobile JavaScript試験が成功した。
- Mobile LearningとVirtual AssemblerのPages URLはHTTP 200。Mobile画面には評価済みbuild識別と
  「画面を初期化」が反映され、Virtual Assembler画面も正常に配信されている。

release asset内には公開前時点の本監査が収録される。この公開後追記はimmutableなtagged artifactを
検証した後の`main`へ記録し、artifact、tag、checksumを変更しない。
