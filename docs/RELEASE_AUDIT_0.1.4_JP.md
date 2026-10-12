# MIN0 CORE FORTH 0.1.4 ローカル候補監査

[英語版はこちらです](RELEASE_AUDIT_0.1.4.md)

候補版：`0.1.4-rc.1`

状態：統合監査中。公開済み0.1.3系と従来のローカル仮想アセンブラ系を統合したため、merge前の試験結果は
履歴上の証拠として残しますが、本候補の合格証拠としては扱いません。

## 対象範囲

0.1.3互換性改善、Mobile Learning、ブラウザ仮想アセンブラViewer、移植可能な仮想命令、RP2350 Thumb
backendとpublication host model、安全に失敗するための学習・移植原則を統合します。

Pico 2 Wでの生成機械語実行、実MPU設定、target側`rx`封印、live patch、Viewer CODEの通常dictionary登録は
含みません。

## Gate A―ローカル統合検証

未完了です。統合後treeに対して、Python、通常PowerShellのRuby、言語間相互試験、JavaScript Viewer、
文書試験、release allowlist監査、`git diff --check`、独立した2回の再現可能ZIP生成を確認します。

## Gate B―GitHub公開

未実施です。`v0.1.4-rc.1` tag、GitHub Release、配布asset、Pages公開は作成していません。

## Gate C―公開後の独立確認

未実施です。公開物を新しいdirectoryへ再取得し、digest、manifest、tag内容、Pages動作、代表的な
ブラウザ例題、全試験commandを確認します。

この監査はMIN0 CORE FORTHだけを対象とし、MIN0 RASPI FORTHとMSX0-FORTHを変更・公開しません。
