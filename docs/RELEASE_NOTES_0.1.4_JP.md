# MIN0 CORE FORTH 0.1.4 ローカル候補ノート

[英語版はこちらです](RELEASE_NOTES_0.1.4.md)

候補版：`0.1.4-rc.1`（公開済み評価用pre-release）

本候補は、公開済み0.1.3互換性改善と、ブラウザ学習、移植可能な仮想アセンブラ、RP2350機械語生成・
監査実験を統合します。

## ブラウザ学習

- Mobile Learningでは、PCとiPhoneでFORTHの学習用subsetを編集・実行し、端末出力、最終stack、
  wordごとのstack遷移を観察できます。`( ... )`コメントと`RECURSE`を含みます。
- 仮想アセンブラViewerでは、演算、条件分岐、検査付きmemory accessをreference実行し、仮想register、
  実行前後のstack、commit／abort結果を表示します。
- どちらもブラウザ内で動作し、実memory、IO、Pico 2 Wを操作しません。

## 仮想アセンブラとRP2350 backend

- 固定entry frame、名前付き仮想register、staged output、label、分岐、四則・論理演算、shift／rotate、
  名前付きmemory capabilityを扱います。
- `LD32`と`ST32`は、無検査の直接memory命令ではなく検査付きhelperへloweringします。
- link済みRP2350 imageを独立decoderで確認し、監査receiptへ結び付けます。
- publication host modelで`rw,nx`から`sealed rx`への一方向遷移を確認します。

## 互換性の基準

0.1.3のコメント、直接制御構造、`FOR ... NEXT`、compile可能な`. EMIT CR TYPE`を保持します。
統合後の語彙は文書と試験で一致を確認します。

## 明確に含めない範囲

- 生成したRP2350機械語をPico 2 Wでは実行しません。
- 実MPU設定、target側`rx`封印、live patchは将来作業です。
- ViewerのCODE定義は通常のFORTH dictionaryへ登録しません。
- 配列・構造体descriptorは設計方向であり、0.1.4実装には含みません。

制限付きCodex sandboxでは`ruby.exe`が拒否される場合があるため、最終Ruby gateは利用者の通常の
PowerShellでも実行します。
