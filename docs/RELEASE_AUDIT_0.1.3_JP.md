# MIN0 CORE FORTH 0.1.3 リリース候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.3.md)

状態：ローカルGate A合格。GitHub公開Gate Bと公開後検証Gate Cは未実施です。対象versionは
`0.1.3-rc.1`であり、まだ公式releaseではありません。

## 対象範囲

0.1.3候補は、PCとiPhone向けMobile Learning、ブラウザ仮想アセンブラViewer、移植可能な仮想命令仕様、
RP2350 Thumb backendとpublication host model、安全に失敗するための学習・移植原則を追加します。

Pico 2 Wでの生成機械語実行、実機MPU設定、target側`rx`封印、live patch、仮想アセンブラCODEの通常FORTH
dictionary登録は含みません。公式推奨版は、Gate BとGate Cが完了するまで`v0.1.2`のままです。

## Gate A：ローカル公開前検証

- 実行日：2026-10-13（日本時間）
- 対象commit：`048ee06 Fix Windows cross-check working directory`
- Windows 11の通常PowerShellで`python tools\run_all_checks.py`を実行
- Python unittest suite：合格
- Ruby：48 test fileすべて合格
- Python／Ruby相互検査：50 check fileすべて合格
- 最終表示：`ALL CHECKS PASSED`
- 一括試験工具は相互検査を`workbench`から起動し、相対pathに依存する2件も対象に含めた
- 文書、release tool、仮想アセンブラViewerの対象試験：15/15合格
- JavaScript仮想アセンブラViewer試験：合格
- release allowlist監査：442ファイル、問題0（監査記録追加前）
- `git diff --check`：問題0
- Codex sandboxでの`ruby.exe`拒否は通常PowerShellでは再現せず、製品試験は合格

監査記録を含む最終候補について、release allowlist、二回の再現可能ZIP生成、SHA-256一致を改めて確認する。
ZIPのdigestは監査記録の自己参照を避けるため、ZIP横の`SHA256SUMS.txt`へ保存する。

## Gate B：GitHub公開

未実施。次の項目を公開時に記録します。

- `v0.1.3` tagとtag commit
- GitHub ReleaseのURLと公開日時
- ZIP名、byte数、SHA-256
- draft／pre-release／latest状態
- GitHub Pagesのbuild commitとHTTPS強制状態
- secret-scanningおよびDependabotのopen alert数

## Gate C：公開後の独立検証

未実施。公開後、別directoryへZIPと`SHA256SUMS.txt`を再取得し、size、SHA-256、manifest、tag blob、
公開Pagesを照合します。PCとiPhoneでMobile Learningおよび仮想アセンブラViewerの代表例を確認し、公開物から
全体試験とrelease auditを再実行します。

本監査はMIN0 CORE FORTHだけを対象とし、MIN0 RASPI FORTHおよびMSX0-FORTHを変更または公開しません。
