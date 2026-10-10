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
| `min0_checked_ld32` | `r0=context, r1=capability, r2=base, r3=offset` | `r0=status, r1=value` |
| `min0_stage_st32` | 上記に加え`r12=value` | `r0=status` |
| `min0_frame_commit` | `r0=context, r1=input-count, r2=output-count` | `r0=status` |

statusは0が成功、0以外が失敗である。失敗時には生成CODEを終了し、stackと未確定memory writeを
破棄する。`r12`を第5引数に使う規則はMIN0内部helperだけのprivate ABIであり、通常のC関数を
この形式で呼び出してはならない。

prologueは`r4-r8`と`lr`を保存して`CONTEXT_BIND r8, r0`を行い、epilogueで復元する。
backend verifierはこの並びとclobber分離を検査する。

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

### 次段階

1. relocation linkerでhelper call、frame操作、定数loadを解決する。
2. 条件分岐ではvirtual comparisonの寿命を保ったままThumb branchを生成する。
3. 生成byte列を独立disassemblerで逆解析してplanとの一致を検査する。
4. 既存のrelocationとW^X publicationへ接続する。
5. Pico 2 Wでは最初に生成のみを行い、その後限定されたtest CODEから実行を開始する。
