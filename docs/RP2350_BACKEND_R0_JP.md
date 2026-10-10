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

planは開始時に`r4`から`r7`を保存し、終了時に復元する。仮想assemblerの実行中にFORTH DATA
stack pointerを移動する命令は生成しない。

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

1. backend planをThumb-2 machine instructionへ符号化するemitterを追加する。
2. helper呼出しのABI、使用register、clobber集合を固定する。
3. relocation情報を生成し、既存のW^X publicationへ接続する。
4. 生成byte列を逆解析してplanとの一致を検査する。
5. Pico 2 Wでは最初に生成のみを行い、その後限定されたtest CODEから実行を開始する。
