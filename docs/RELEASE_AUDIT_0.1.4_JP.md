# MIN0 CORE FORTH 0.1.4 ローカル候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.4.md)

候補版：`0.1.4-rc.1`

状態：ローカルGate A合格。GitHub公開Gate Bと公開後の独立確認Gate Cは未実施です。公開済み0.1.3系と
従来のローカル仮想アセンブラ系を統合後に改めて検証し、merge前の結果は履歴上の証拠としてだけ残します。

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

未実施です。`v0.1.4-rc.1` tag、GitHub Release、配布asset、Pages公開は作成していません。

## Gate C―公開後の独立確認

未実施です。公開物を新しいdirectoryへ再取得し、digest、manifest、tag内容、Pages動作、代表的な
ブラウザ例題、全試験commandを確認します。

この監査はMIN0 CORE FORTHだけを対象とし、MIN0 RASPI FORTHとMSX0-FORTHを変更・公開しません。
