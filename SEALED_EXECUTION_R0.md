# MIN0 CORE FORTH sealed execution R0

## 設計原則

> Forthの自由さを失わせず、危険な力を使うときだけ本人がはっきり自覚できる設計にする。
> 通常利用者に安全な道と、理解した開発者が明示的に開く道を分ける。

警告を読んだ利用者だけが安全になる設計にはしない。説明、分かるerror、実行境界の三段を重ねる。

```text
理解の支援    Viewer／資料で何が起きるか示す
失敗の説明    operation、address、region、理由を示す
技術的強制    safe-runtimeでは危険な操作を成功させない
```

## 問題

Forthの`!`は値の意味を知らず、指定addressへ1 cellを書き込む。CODEが書込み可能なら、次のsourceはopcodeや
operandを変更できる。

```forth
0x25 0x1000 !
```

また、CODEが読出し専用でも、DICTIONARY内のcolon payloadやDEFER targetを`!`で壊し、間接呼出しを
operand途中へ向ける可能性がある。静的bytecode verifierだけでは実行中の変更を扱えない。

## 封印sequence

```text
development build artifact
  -> staging rw,nx
  -> envelope・digest・relocation・bytecode再検証
  -> 別runtime CODE rxへprivileged publish
  -> 固定primitive dispatchを一度だけprogram
  -> instruction boundary policy
  -> seal: rx / programmable=false / sealed=true
```

既存interactive compilerを直接封印する開発用demonstrationも残すが、通常runtime向けには
`W_X_PUBLICATION_R0.md`の分離経路を使う。stagingにはexecute permissionがなく、runtime CODEには通常write
permissionがない。同じ物理領域を`writable`かつ`executable`にする瞬間を作らない。

封印は一方向である。同じregionの再seal、`program`による再書込み、全memory clearは拒否する。更新は封印を
解除せず、別のinactive slotへ構築・検証して切り替える。

## 実行時boundary policy

bytecode verifierが返す全命令先頭addressをVMへ導入する。次の全経路は実行可能permissionだけでなく、
verified boundaryであることを確認する。

- `resume`の開始address
- 各`step`の現在IP
- `CALL`と直接branch／loop
- `EXIT`のreturn address
- `ICALL`が辞書XTから得たcolon payload
- `DSET`へ登録するtarget XTのcolon payload

return trampolineのHALTと固定primitive dispatchなど、CODE component外の正規入口はtrusted hostが内容を
検査してextra entryとして明示する。

## 封印後の対話primitive

旧方式は、interpret-stateでprimitiveを一つ実行するたび、共通trampolineの先頭byteをそのopcodeへ書き換えて
いた。この方式はCODE sealと両立しない。

現在は起動時に、各operandなしprimitiveについて`opcode, HALT`の2-byte固定slotを一度だけ作る。たとえば`+`を
実行するときは対応slotへ入るだけで、runtime CODEは変更しない。slotのopcode位置とHALT位置はどちらも実行境界
として登録される。封印後に実際のouter interpreterで`2 3 +`が5になることをPython／Rubyで確認した。

## `!`に対する結果

`STORE`／`!`はstackからargumentを消費する前にregionの`w` permissionを確認する。

| destination | seal後の結果 |
| --- | --- |
| DATA `rw,nx` | 通常どおり保存可能 |
| DICTIONARY `rw,nx` | 開発用直接sealでは保存可能。safe-runtime publish後はcapabilityなしのwriteを拒否 |
| CODE `rx` | `MemoryFault`、CODE不変 |
| DATAを実行 | `InvalidExecutionTarget`またはexecute permission fault |
| CODE operand途中へjump | `InvalidExecutionTarget` |

値`0x25`自体は禁止しない。DATAへ保存したり`LIT 0x25`として使うことは正しい。危険性は値ではなく、
書込みdestinationと実行entryの組合せで判断する。

## 実働確認

実sourceへ`0x25 0x1000 !`を含む`CODE-WRITE`をcompileした。seal前のverifierはこれを正しい命令列として扱うが、
seal後の実行はCODE write permissionで拒否し、先頭4 byteが不変であることを確認した。

同じimageで次も確認した。

- `LIT 0x25`は37を返す。
- DATA変数への`!`と`@`は123を返す。
- 正常なDEFERは7を返す。
- outer interpreterのprimitive `2 3 +`は封印後も5を返す。
- colon payloadを`LIT` operand途中へ書き換えた後のICALLを拒否する。
- operand途中への直接resume、DATA実行、再program、再seal、sealed clearを拒否する。
- protected RegionMemoryを持たないFlatMemoryではseal API自体を拒否する。

```powershell
python -m unittest -v test_sealed_execution.py
ruby test_ruby_sealed_execution.rb
python cross_sealed_execution_check.py
```

## R0の限界と次段階

- 同processのhost objectを直接変更できる相手に対する強いsandboxではない。
- DICTIONARYはMonitor DEFER gateのため表示上`rw`だが、safe-runtime publisherは追加のwrite capability層と
  structure sealを導入する。詳細は`DICTIONARY_CAPABILITY_R0.md`を参照する。
- 固定dispatchは現在のoperandなしprimitive集合を対象とする。将来host serviceを追加するときは、同じ検証済み
  entry設計または明示的service gateが必要である。
- W^X publisherは連続した3-region reference layoutを対象とするR0である。実Flashのerase block、A/B slot、cache
  同期、MPU permission変更はtarget adapterで実装する必要がある。
- control-flow reachability、stack effect、無限loop、正しい意図までは証明しない。

次候補は、entry pointからのcontrol-flow graph、到達可能性、stack effect静的検査の負担と効果の比較である。
