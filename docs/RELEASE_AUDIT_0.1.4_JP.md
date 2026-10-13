# MIN0 CORE FORTH 0.1.4 ローカル候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.4.md)

候補版：`0.1.4-rc.1`

状態：評価用pre-release `v0.1.4-rc.1`についてGate A、B、C合格。公開済み0.1.3系と従来のローカル
仮想アセンブラ系を統合後に改めて検証し、merge前の結果は履歴上の証拠としてだけ残します。

## 対象範囲

0.1.3互換性改善、Mobile Learning、ブラウザ仮想アセンブラViewer、移植可能な仮想命令、RP2350 Thumb
backendとpublication host model、安全に失敗するための学習・移植原則を統合します。

Pico 2 Wでの生成機械語実行、実MPU設定、target側`rx`封印、live patch、Viewer CODEの通常dictionary登録は
含みません。

## Gate A―ローカル統合検証

- 実施日：2026-10-13（Asia/Tokyo）
- 利用者の通常Windows PowerShell：`python tools\run_all_checks.py`
- Python suite：成功
- Ruby：50 test fileすべて成功
- Python／Ruby相互試験：51 check fileすべて成功
- 最終表示：`ALL CHECKS PASSED`
- Mobile Learning JavaScript試験：成功
- 仮想アセンブラbrowser JavaScript試験：成功
- release allowlist監査：465ファイル、問題0件
- `git diff --check`：問題なし
- 最終Gate A commitから独立に作った2個のZIPはbyte単位で一致。package自身のhashを自己参照させないため、
  digestは候補artifactの隣へ保存します。

制限付きCodex sandboxでは子processの`ruby.exe`が`0xC0000022`で拒否されますが、通常PowerShellでは
再現せず、製品の全試験が成功しました。

## Gate B―GitHub公開

- 公開日時：2026-10-13 21:07 JST
- tag：`v0.1.4-rc.1`、commit `c8ff554aa9b8a129ca6f4746a899954c50ed47c9`
- Release：<https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.4-rc.1>
- 状態：公開評価用pre-release。正式版ではない。
- ZIP：`min0-core-forth-0.1.4-rc.1.zip`、861703 byte
- ZIP SHA-256：`1215eaabc5d32b0cb16b03c4782d46d77710b31938cda8fd1542ffe6c51dd0d3`
- `SHA256SUMS.txt`を別assetとして公開
- GitHub Pagesはcommit `c8ff554`を正常buildし、HTTPSを強制

## Gate C―公開後の独立確認

- GitHubから二つのrelease assetを新規directoryへ再取得した。
- 再取得ZIPのbyte数とSHA-256はGate Bおよび公開checksum fileと一致した。
- manifest全465項目の存在とSHA-256一致を確認した。
- 展開後treeのrelease allowlist監査は465ファイル、問題0件。
- 公開artifact上でMobile Learningと仮想アセンブラのJavaScript試験が成功した。
- 二つのPages URLはHTTP 200。仮想アセンブラHTMLはtagged local fileと一致し、両画面に必要な
  実行scriptとcontrolが含まれる。
- iPhone実機表示は利用者による推奨確認事項であり、自動Gate Cで確認したとは主張しない。

release asset内には性質上、公開前時点の本監査が収録される。この公開後追記はimmutableなtagged artifactを
検証した後の`main`へ記録し、artifact、tag、checksumを変更しない。

この監査はMIN0 CORE FORTHだけを対象とし、MIN0 RASPI FORTHとMSX0-FORTHを変更・公開しません。
