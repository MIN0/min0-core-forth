# MIN0仮想assembler RP2350 backend R0

この文書のregister、function frame、ARM命令、ABIはRP2350固有の実装profileである。CPUやFPGAに
共通して維持する契約と変更判断は、[MIN0 CORE FORTH 移植可能backend開発原則](PORTABLE_BACKEND_PRINCIPLES_JP.md)
を参照する。

## 現在の段階

R0は検査済み仮想assemblerをRP2350 Arm Cortex-M33向けbackend planへ変換し、安全に確定できる
Thumb機械語とrelocationを生成する。独立逆解析をpublication gateへ接続し、W^Xの`rw,nx` stagingから
封印済み`rx` snapshotを作るhost reference実装まで完了した。runtime helper実装、外部ARM disassembler、
target固有のcache／MPU処理、実機試験が完了するまでは、生成したmachine fragmentの実行を許可しない。
encoderと実装を共有しない内部decoderによる逆解析は完了したが、外部ARM disassemblerによるsecond opinionは
まだ行っていない。

## Register対応

| 仮想register | RP2350 plan register |
|---|---|
| `V0` | `r4` |
| `V1` | `r5` |
| `V2` | `r6` |
| `V3` | `r7` |

`r8`はexecution context、`r9/r10`は最後に実行した仮想`CMP`の左右値を保持する。planは開始時に
`r4`から`r10`と`lr`を保存し、終了時に復元する。仮想assemblerの実行中にFORTH DATA
stack pointerを移動する命令は生成しない。

## ARMを初めて読む人のための関数入口と復帰

### lrとBL

`lr`はlink register、つまりARMの`r14`である。呼出し元が`BL`（branch with link）で生成関数を
呼ぶと、CPUは呼出し元へ戻る位置を`lr`へ設定する。生成関数もruntime helperを`BL`で呼ぶため、
そのたびに`lr`はhelperから戻る位置へ更新される。このため、最初に受け取った本来の戻り先は関数入口で
CPU stackへ保存する。

### 32 byteの関数frame

`r4-r7`は仮想register `V0-V3`、`r8`はexecution context、`r9/r10`は比較値のsnapshotに使用する。
呼出し元の値を壊さないよう、入口の`STMDB`で`r4-r10,lr`を保存し、出口の`LDMIA`で復元する。
32-bit registerが8個なので合計は32 byteであり、8-byte alignmentも維持する。

```text
CPU stack上の関数frame
  lr   呼出し元への戻り先
  r10  CMP右値を保持する前の値
  r9   CMP左値を保持する前の値
  r8   呼出し元の値
  r7   V3が使用する前の値
  r6   V2が使用する前の値
  r5   V1が使用する前の値
  r4   V0が使用する前の値
       合計 8 x 4 = 32 byte
```

これはCPUの関数呼出し用stackであり、FORTH DATA stackとは別である。この保存と復元によって
FORTH DATA stack pointerは移動しない。

### execution contextをr8へ置く理由

生成関数は`r0`でexecution contextへのpointerを受け取る。このcontextは、入力／出力frame、memory
capability、未確定write、statusなど、今回のFORTH処理をruntime helperが扱うための基準点になる。
`r0-r3`はhelperが破壊できる一時registerなので、関数入口で`MOV r8,r0`を実行し、処理中は保存対象の
`r8`で同じpointerを保持する。helperを呼ぶ直前には必要に応じて`MOV r0,r8`として渡し直す。

### BX lrによる復帰

関数出口は`r4-r10`と本来の`lr`を復元した後、`BX lr`を実行する。`BX`はregisterに入っているaddressへ
分岐する命令であり、ここでは`lr`が示す呼出し元へ戻る。全体の順序は次のとおりである。

```text
BLで生成関数を呼ぶ
  -> r4-r10,lrを32 byte保存
  -> MOV r8,r0でcontextを保持
  -> 仮想assembler本体とruntime helperを実行
  -> r4-r10,lrを復元
  -> BX lrで呼出し元へ戻る
```

## Helper ABI 0.2

生成関数は`r0`でexecution context pointerを受け取り、prologueでcallee-savedの`r8`へ保存する。
`r4`から`r7`は仮想register専用、`r8`はcontext専用、`r9/r10`は比較snapshot専用であり、helperは
これらを保存する。ABI 0.2では異常終了時に復元するfunction frameを32 byteへ拡張した。

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

prologueは`r4-r10`と`lr`を保存して`CONTEXT_BIND r8, r0`を行い、epilogueで復元する。
backend verifierはこの並びとclobber分離を検査する。

`min0_abort_transaction`は通常のC helperではなく、生成関数から異常終了するprivate tail ABIである。
入口では`r0=status`、`r8=context`、CPU stack先頭には生成関数が保存した`r4-r10,lr`の32 byteがある。
このtail helperは未確定writeを破棄し、その32 byteを復元して生成関数の呼出し元へ戻る責任を持つ。
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

最初のemitterは、低registerだけで確定できる`MOV/ADD/SUB/AND/XOR/OR/MUL/NOT`と
`LSL/LSR/ASR`を16-bit little-endian machine halfwordへ変換する。`CMP`は比較値snapshot、
`ROL/ROR`は検査済み2命令列へ変換する。

helper、stack frame操作、定数load、分岐など未解決の操作には4 byteのrelocation slotを
確保し、slot全体を2個の`UDF`命令で埋める。この状態のfragmentは`executable=false`であり、
誤って実行しても未解決箇所で停止する。0やNOPをplaceholderには使用しない。

labelはbyteを生成せず、その時点のmachine offsetとしてsymbol tableへ記録する。分岐linkerは
relocation解決時に範囲とconditionを検査する。仮想`CMP`の比較結果は後続命令から独立している。

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

`PROLOGUE_SAVE`は`r4-r10,lr`をCPU stackへ32 byte保存する`STMDB`、`CONTEXT_BIND`は`MOV r8,r0`、
`EPILOGUE_RESTORE`は同じ32 byteを復元する`LDMIA`、`RETURN`は`BX lr`へ変換する。32は8の倍数なので、
関数内およびhelper call時のCPU stack alignmentを維持する。ここでもFORTH DATA stack pointerは変更しない。

`FRAME_LOAD`と`RESULT_STAGE`は生のcontext memory accessへ変換せず、それぞれ`min0_frame_load`と
`min0_result_stage`を呼ぶ検査付きout-of-line thunkにする。入力index／出力indexは明示的な32-bit即値、
値は仮想register `r4-r7`との間で受け渡す。status非0は他のhelperと同じ異常終了経路へ進む。

分岐、rotate、memory accessを含まない最小の`IN`／`OUT` CODEは、明示的なhelper address表を与えると
全relocationを解決できる。これはmachine fragmentのlink完了を意味するだけであり、runtime helper実装、
外部ARM disassembler、W^X publication、RP2350実機試験が完了するまでは実行を許可しない。

## Rotate emitter R0

Thumbの16-bit `RORS`は回転量をregisterから受け取るため、仮想assemblerの即値`ROL/ROR`を次の
4-byte命令列へ変換する。

```text
ROR V0, 4
  -> MOVS r0,#4
  -> RORS r4,r0

ROL V0, 8
  -> MOVS r0,#24
  -> RORS r4,r0
```

左rotateは32-bit値を反対方向へ`32-count`だけ回すことで実現する。`r0`はhelper ABIで破壊可能な
一時registerであり、execution contextは`r8`に保持されている。後続helperは必ず`MOV r0,r8`でcontextを
渡し直すため、rotateによる`r0`使用はcontextを失わない。

回転量0は`MOV Rd,Rd; NOP`とし、ほかのrotateと同じ4 byteを維持する。`MOVS`と`RORS`はAPSRを変更するが、
仮想比較は`r9/r10`に保存され、条件分岐直前に`CMP r9,r10`を再実行するため意味は変わらない。

## Internal branch linker R0

仮想`CMP Va,Vb`は、その時点の左右値を`r9/r10`へ`MOV`して保存する。`ADD`、`SUB`、helper callなどが
その後にAPSR condition flagsを変更しても、仮想比較の意味は変わらない。条件分岐slotでは
`CMP r9,r10`を再実行してから、対応する16-bit Thumb条件分岐を行う。次の仮想`CMP`を実行するとsnapshotを
更新する。

| 仮想分岐 | Thumb condition |
|---|---|
| `BEQ` | EQ |
| `BNE` | NE |
| `BLT` | LT、signed |
| `BGE` | GE、signed |
| `BLTU` | CC／LO、unsigned |
| `BGEU` | CS／HS、unsigned |

`BRA`は16-bit無条件分岐と`NOP`へ変換する。R0の4-byte relocation slot内で比較再生成と分岐を完結させる
ため、条件分岐targetはbranch命令から-256..254 byte、無条件分岐targetは-2048..2046 byteの範囲に
制限する。範囲外を切り詰めずlink errorとして拒否し、将来はwide branchまたはveneerで拡張する。

この方式により、`CMP`と条件分岐の間に算術命令や検査付きhelperがあっても、reference VMと同じ
virtual comparisonを使用できる。分岐を含む最小の`MAX` CODEは、明示的なhelper address表を与えると
全relocationを解決できる段階に達した。ただし、これは実機実行を許可するものではない。

## Independent disassembly audit R0

`min0_rp2350_disassembler.py`はemitter／linkerのencoding関数をimportせず、生成byte列を逆方向から
Thumb命令へ戻す検査専用moduleである。link済みmain bodyをbackend planと順番に照合し、次を確認する。

- `STMDB/LDMIA`の保存・復元registerと32-byte frame
- execution contextの`MOV r8,r0`
- ALU、shift、rotate、比較snapshotのregisterと即値
- literal load先の32-bit値
- label offsetと条件／無条件分岐target
- mainから各helper thunkへの`BL` target
- epilogueの`BX lr`

out-of-line helper thunkについても、8-byte CPU stack frame、引数設定、private helperへの`BL`、status比較、
正常経路、`min0_abort_transaction`への`B.W`をthunk planと照合する。memory helperではcapability ID、base、
offset、`r12`のwrite値受渡しも逆解析対象になる。

検査用testは、ALU、literal、rotate、分岐を含むCODEと、`LD32/ST32`を含むCODEのmain／thunk全体を照合する。
生成byte列のfunction prologueを`NOP`へ改変したtestでは、plan不一致として拒否することも確認した。

これはencoderと同じ誤りをそのまま見逃さないための別実装だが、同じrepository内のPython decoderである。
実行許可前にはARM対応の外部disassemblerでもbyte列を確認し、さらにRP2350実機で限定testを行う。

## RP2350 publication gate R0

`min0_rp2350_publication.py`は、link完了したfragmentをそのまま実行許可とせず、次の順序で処理する。

```text
仮想assemblerのbackend plan
  -> emitter / relocation / helper thunk / branch link
  -> rw,nx stagingへcopy
  -> mainと全helper thunkを独立disassemble監査
  -> literal poolとalignmentを含む全byte coverage確認
  -> code、label、base、symbol表をSHA-256 receiptへ固定
  -> 監査時と同じsnapshotだけをsealed rxへcopy
```

policyはarchitecture、image base／limit、承認済みhelper symbol addressを固定する。未解決relocation、planとの
命令不一致、未監査byte、範囲外配置、helper address違い、監査後の1 byte変更、policy変更のいずれかがあれば
公開を拒否する。mainだけでなく、out-of-line helper thunkの改変も拒否試験で確認する。

公開結果は`permissions=rx`、`programmable=false`、`sealed=true`だが、R0では
`execution_authorized=false`を維持し、`execute`操作を持たない。ここでのpublicationは監査済みbytesを
変更不能な候補へ進める境界であり、RP2350実機で呼び出す許可ではない。

### 次段階

1. ARM対応の外部disassemblerでsecond opinionを取得する。
2. runtime helperのC実装と異常終了時rollbackをreference testする。
3. RP2350向けcache同期、MPUまたは実行領域切替をtarget adapterで定義する。
4. Pico 2 Wでは最初に生成と監査receiptの表示だけを行い、その後限定されたtest CODEから実行を開始する。
