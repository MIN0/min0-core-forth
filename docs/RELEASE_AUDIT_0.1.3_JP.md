# MIN0 CORE FORTH 0.1.3 互換性改善版リリース監査

[英語版はこちらです](RELEASE_AUDIT_0.1.3.md)

対象候補：`0.1.3-rc.1`

状態：Gate A、評価用pre-releaseのGate B、公開物再取得のGate Cに合格しました。正式版`0.1.3`は未公開です。

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

## Gate B：評価用pre-release公開

- [公式`v0.1.3-rc.1` pre-release](https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.3-rc.1)
- 公開日時：2026-09-14 22:18:19（日本時間）
- tag commit：`43b0881643f76c1a1daa5c06810606d6e94415fa`
- localで検査したtreeとtag commitのtree SHA-1：`98759e00d2416bde5f87cd0e5fe61ba6b86bf009`で一致
- 配布物：`min0-core-forth-0.1.3-rc.1.zip`、690780 byte
- SHA-256：`4dca02ad18d18eab23d6f49032054556f3b0441ec6e5df8d54b3740d6018895a`
- `SHA256SUMS.txt`：97 byte。ZIP digestと一致
- draftではなくpre-releaseとして公開し、正式版`v0.1.2`を置き換えない

## Gate C：公開物の独立再取得

- 公開ZIPと`SHA256SUMS.txt`を新しいdirectoryへ取得し、sizeとSHA-256が公開前候補と一致
- ZIP内401 fileを`RELEASE_MANIFEST.txt`と照合し、全SHA-256一致、欠落0、余分0
- 展開した公開物自身のrelease audit：401 file、問題0、VERSION=`0.1.3-rc.1`
- 展開した公開物でPython 336 test、Ruby 48 test file、Python／Ruby間49 checkがすべて合格
- GitHub Release metadata：`prerelease=true`、`draft=false`、asset 2個

これらは評価候補をFORTH2020などへ案内できる状態にした証拠であり、正式版`0.1.3`の公開完了を意味しません。
試用結果を受けて必要な修正を行い、改めて正式版のGate A～Cを実施します。

本監査はMIN0 CORE FORTHだけを対象とし、MSX0-FORTHを変更または公開しません。
