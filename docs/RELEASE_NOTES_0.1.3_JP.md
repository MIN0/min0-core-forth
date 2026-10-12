# MIN0 CORE FORTH 0.1.3 リリースノート

[英語版はこちらです](RELEASE_NOTES_0.1.3.md)

この対話学習・仮想アセンブラ版は、PCとiPhoneのブラウザでFORTHを試す入口と、対象CPUに依存しない
仮想アセンブラのreference実行を追加します。同時にRP2350向けThumb機械語の生成、link、独立逆解析、
publication監査までを収録しますが、生成機械語をPico 2 Wで実行する許可は含みません。

## ブラウザで体験する二つの環境

- Mobile Learningでは、FORTH sourceを編集して実行し、端末出力、最終stack、ワードごとのstack変化を
  PCとiPhoneで確認できます。`( ... )`コメントと`RECURSE`を含む学習用サブセットです。
- 仮想アセンブラ体験Viewerでは、sourceと入力stackを変更し、加算、条件分岐、検査付きmemory accessを
  reference modelで実行できます。命令ごとの仮想register、実行前後のstack、commit／abortを表示します。
- 範囲外memory accessの例では、未確定writeを破棄し、入力stackを開始前へ戻す動作を観察できます。
- どちらもブラウザ内の学習環境であり、実memory、IO、Pico 2 Wを操作しません。

## 仮想アセンブラとRP2350 backend

- 4個の仮想register、固定entry frame、staged output、label、比較、条件分岐、算術、論理、shift、rotate、
  名前付きmemory capabilityを実装しました。
- `LD32`と`ST32`は生のload／storeにせず、範囲、alignment、権限を検査するhelperへloweringします。
- main CODE、helper thunk、private ABI veneerを一つの連続imageへlinkし、独立decoderとSHA-256 receiptで
  全byteを監査します。
- RP2350内部SRAMを対象とするtarget publication host modelは、`rw,nx`から`sealed rx`までの一方向手順と
  順序違反、改変、再書込みの拒否を試験します。

## 安全に失敗する学習方針

- 値を作る自由と、その値をmemory、IO、間接分岐へ使う許可を分離します。
- 安全に停止するSafety kernel、CPU固有のTarget adapter、説明を展開するLearning interfaceを分けます。
- 小容量targetでは長い説明を外部Viewerへ移せますが、error code、観測値、許可範囲、復旧結果はtargetに
  残す設計原則を記録しました。
- 初心者が間違いを観察して修正でき、熟練者が説明を短縮して進めることを両立する方針です。

## 明示する未実装範囲

- 生成したRP2350機械語はPico 2 Wで実行しません。
- 実機MPUの設定、実機上の`rx`封印、live patchは次段階です。
- 仮想アセンブラViewerのCODEは、まだ通常FORTH dictionaryへwordとして登録されません。
- 配列と構造体のdescriptorは設計候補であり、0.1.3の実装には含みません。

## リリース前確認

Python、Ruby、両実装の相互検査、JavaScript Viewer、release audit、再現可能ZIPを確認します。完了した
件数、checksum、公開後の再取得結果は、0.1.3 release auditへ記録します。

Windows一括試験工具は、相互試験を正しい`workbench` directoryから起動するよう修正しました。Codexの
制限付きsandboxでは`ruby.exe`が`0xC0000022`で拒否されるため、Rubyを含む最終判定は通常PowerShellで
行います。
