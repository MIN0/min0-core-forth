# MIN0仮想assembler RP2350 backend R0

## 現在の段階

R0は機械語を生成または実行しない。検査済み仮想assemblerを、RP2350 Arm Cortex-M33を対象とする
監査可能なbackend planへ変換する。次段階のmachine emitterは、このplanだけを入力にする。

## Register対応

| 仮想register | RP2350 plan register |
|---|---|
| `V0` | `r4` |
| `V1` | `r5` |
| `V2` | `r6` |
| `V3` | `r7` |

planは開始時に`r4`から`r8`と`lr`を保存し、終了時に復元する。仮想assemblerの実行中にFORTH DATA
stack pointerを移動する命令は生成しない。

## Helper ABI 0.1

生成関数は`r0`でexecution context pointerを受け取り、prologueでcallee-savedの`r8`へ保存する。
`r4`から`r7`は仮想register専用、`r8`はcontext専用であり、helperはこれらを保存する。

helperが破壊できるのは`r0`から`r3`、`r12`、APSR condition flagsである。

| helper | 入力 | 出力 |
|---|---|---|
| `min0_frame_load` | `r0=context, r1=input-index` | `r0=status, r1=value` |
| `min0_result_stage` | `r0=context, r1=output-index, r2=value` | `r0=status` |
| `min0_checked_ld32` | `r0=context, r1=capability, r2=base, r3=offset` | `r0=status, r1=value` |
| `min0_stage_st32` | 上記に加え`r12=value` | `r0=status` |
| `min0_frame_commit` | `r0=context, r1=input-count, r2=output-count` | `r0=status` |

statusは0が成功、0以外が失敗である。失敗時には生成CODEを終了し、stackと未確定memory writeを
破棄する。`r12`を第5引数に使う規則はMIN0内部helperだけのprivate ABIであり、通常のC関数を
この形式で呼び出してはならない。

prologueは`r4-r8`と`lr`を保存して`CONTEXT_BIND r8, r0`を行い、epilogueで復元する。
backend verifierはこの並びとclobber分離を検査する。

`min0_abort_transaction`は通常のC helperではなく、生成関数から異常終了するprivate tail ABIである。
入口では`r0=status`、`r8=context`、CPU stack先頭には生成関数が保存した`r4-r8,lr`の24 byteがある。
このtail helperは未確定writeを破棄し、その24 byteを復元して生成関数の呼出し元へ戻る責任を持つ。
したがってhelper thunkは自分自身の8 byteだけを復元してから、この入口へ`B.W`する。

## Stack contractのlowering

- `IN V0, source`は`FRAME_LOAD r4, input-index`になる。
- `OUT result, V0`は`RESULT_STAGE output-index, r4`になる。
- 最後に`FRAME_COMMIT input-count, output-count`を1回だけ置く。
- `PUSH_DATA`と`POP_DATA`はbackend verifierが拒否する。

これにより、入力3個・出力2個のCODEでも、本体実行中のDATA stack位置は変わらない。

## Memory accessのlowering

```forth
LD32 V0, [DATA: V1+4]
ST32 [IO: V2], V0
```

は次のplanになる。

```text
CHECKED_LD32 r4, DATA, r5, 4
STAGE_ST32 IO, r6, 0, r4
```

生の`LDR/STR`は生成しない。`CHECKED_LD32`はcapability、境界、整列、read権限を検査する。
`STAGE_ST32`はwrite権限を検査してtransactionへ保存し、`FRAME_COMMIT`成功時だけ反映する。
backend verifierは`RAW_LDR`、`RAW_STR`、未知のbackend opcodeを拒否する。

## 次段階

## Thumb emitter R0

最初のemitterは、低registerだけで確定できる`MOV/ADD/SUB/AND/XOR/OR/MUL/NOT/CMP`と
`LSL/LSR/ASR`を16-bit little-endian machine halfwordへ変換する。

helper、stack frame操作、定数load、分岐、rotateなど未解決の操作には4 byteのrelocation slotを
確保し、slot全体を2個の`UDF`命令で埋める。この状態のfragmentは`executable=false`であり、
誤って実行しても未解決箇所で停止する。0やNOPをplaceholderには使用しない。

labelはbyteを生成せず、その時点のmachine offsetとしてsymbol tableへ記録する。分岐linkerは
relocation解決時に範囲とconditionを検査する。仮想`CMP`の比較結果は後続命令から独立しているため、
将来のlinkerはCMPと分岐の間でAPSRが変化する場合、比較結果を再生成しなければならない。

## Relocation linker R0

`LIT`から生成された`MOV_IMM32`は、末尾の4-byte aligned literal poolへ32-bit little-endian値を置き、
予約枠を16-bitの`LDR literal`と`NOP`へ置換する。同じ32-bit値は1個のpool cellを共有する。
PCからpoolまでが正方向、4-byte単位、Thumb 16-bit literal loadの範囲内でなければ拒否する。

`CHECKED_LD32`、`STAGE_ST32`、`FRAME_COMMIT`は、それぞれ次のprivate ABI symbolへbindする。

```text
min0_checked_ld32
min0_stage_st32
min0_frame_commit
```

この時点では引数設定とcallを行うout-of-line thunkをまだ生成しないため、relocation slotの`UDF`は
維持され、fragmentは実行不可のままである。symbol addressを得ただけで安全検査済みと扱ってはならない。

## Helper thunk plan R0

helper relocationごとに、次の監査可能なout-of-line thunk planを生成する。

1. CPU stackへ`r12, lr`の8 byteを保存する。FORTH DATA stackには触れない。
2. `r0=r8`としてexecution contextを渡す。
3. capability名を、呼出し側が明示した32-bit numeric IDへ変換する。未知名は拒否する。
4. ABIに従ってbase、offset、valueを設定し、bind済みhelperを1回だけ呼ぶ。
5. statusが非0ならCPU stack frameを8 byte戻して`min0_abort_transaction`へ進む。
6. 成功時は必要な結果を仮想registerへ戻し、8 byteを復元して呼出し元へ戻る。

CPU stackを8 byte単位にするのはhelper call中のalignmentを保つためであり、DATA stack不変規則とは
別の層である。

## Helper thunk emitter R0

planからout-of-line Thumb thunkを生成し、各thunkの開始位置を4-byte境界へ揃える。命令自体をすべて
4-byte境界へ揃えるわけではなく、16-bit命令は2-byte境界に連続して配置する。元の4-byte `UDF`
slotはthunkへの`BL`へ置換される。

thunkは`r12, lr`をCPU stackへ8 byte保存し、引数設定、helper call、status検査を行う。失敗経路は
8 byteを復元してから`min0_abort_transaction`へ`B.W`し、成功経路は`r12, pc`を復元する。
32-bit即値は既存literal linkerを再利用する。

helperとabort先の最終addressが未指定の間、対応する4-byte slotは2個の`UDF`のままである。
最終image baseと明示的なsymbol address表を受け取ったときだけ、signed 25-bit範囲を検査して
`BL`または`B.W`へ置換する。関数pointerのbit 0はThumb-state bitとして除外して分岐距離を計算する。
prologue、frame操作、分岐などには未解決relocationが残るため、この段階でもfragment全体は実行不可である。

## Function frame linker R0

`PROLOGUE_SAVE`は`r4-r8,lr`をCPU stackへ24 byte保存する`STMDB`、`CONTEXT_BIND`は`MOV r8,r0`、
`EPILOGUE_RESTORE`は同じ24 byteを復元する`LDMIA`、`RETURN`は`BX lr`へ変換する。24は8の倍数なので、
関数内およびhelper call時のCPU stack alignmentを維持する。ここでもFORTH DATA stack pointerは変更しない。

`FRAME_LOAD`と`RESULT_STAGE`は生のcontext memory accessへ変換せず、それぞれ`min0_frame_load`と
`min0_result_stage`を呼ぶ検査付きout-of-line thunkにする。入力index／出力indexは明示的な32-bit即値、
値は仮想register `r4-r7`との間で受け渡す。status非0は他のhelperと同じ異常終了経路へ進む。

分岐、rotate、memory accessを含まない最小の`IN`／`OUT` CODEは、明示的なhelper address表を与えると
全relocationを解決できる。これはmachine fragmentのlink完了を意味するだけであり、独立逆解析、runtime
helper実装、W^X publication、RP2350実機試験が完了するまでは実行を許可しない。

### 次段階

1. 条件分岐ではvirtual comparisonの寿命を保ったままThumb branchを生成する。
2. rotateを検査済みThumb命令列へ変換する。
3. 生成byte列を独立disassemblerで逆解析してplanとの一致を検査する。
4. 既存のrelocationとW^X publicationへ接続する。
5. Pico 2 Wでは最初に生成のみを行い、その後限定されたtest CODEから実行を開始する。
