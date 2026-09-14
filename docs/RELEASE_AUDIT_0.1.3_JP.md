# MIN0 CORE FORTH 0.1.3 互換性改善版リリース監査

[英語版はこちらです](RELEASE_AUDIT_0.1.3.md)

対象候補：`0.1.3-rc.1`

状態：ローカルGate A合格。tag、GitHub Release、公開assetはまだ作成していません。

## 対象範囲

コメント、直接制御構造、`FOR ... NEXT`、compile可能な`. EMIT CR TYPE`、起動時65ワードの監査と学習文書を
対象とします。`v0.1.0`～`v0.1.2`のtagと配布物は変更しません。基本除算、double-cell演算、rotate、
byte-order変換、実通信targetはこの候補へ含めません。

## Gate A：ローカル公開前検証

- VERSION：`0.1.3-rc.1`
- 公開allowlist：401 file、問題0
- Python：336 test合格
- Ruby：48 test file合格
- Python／Ruby相互検査：49 check合格
- 起動時65ワード：日英ポケットリファレンスおよびsemantics matrixと一致
- local Markdown link：93 fileを検査、切れ0
- release audit：PASS、個人path・秘密情報・内部会話記録などの公開blocker 0
- 再現可能ZIP：同一sourceから独立した2回の生成がbyte単位で一致

## Gate B／Gate C

未実施です。利用者の明示的な公開判断後に限り、tag／Release／assetを作成し、公開物を別directoryへ
再取得して検証します。Gate A合格だけで正式リリース済みとは扱いません。

本監査はMIN0 CORE FORTHだけを対象とし、MSX0-FORTHを変更または公開しません。
