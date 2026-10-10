# MIN0 CORE FORTH 仮想アセンブラ R0

CPUやFPGAが変わっても維持する上位契約と、backend固有実装を分離する判断基準は、
[MIN0 CORE FORTH 移植可能backend開発原則](PORTABLE_BACKEND_PRINCIPLES_JP.md)に定める。

## 目的

MIN0 CORE FORTH のワード内部へ、対象CPUに依存しない小さなアセンブラを記述する。
R0ではCPU機械語をまだ生成せず、検査可能な仮想命令として実行する。後続版で同じ命令列を
Pico 2 WなどのCPU向けbackendへ渡す。

最重要規則は、アセンブラ本体の実行中にFORTHのDATA stackをPUSH/POPしないことである。
開始時のstackを固定したentry frameとして読み、結果は一時領域へ保存し、正常終了した場合だけ
`;CODE`で一度に確定する。

## 記述例

```forth
CODE: SUM-XOR ( a b c -- sum mix )
  IN  V0, a
  IN  V1, b
  IN  V2, c
  MOV V3, V0
  ADD V0, V1
  ADD V0, V2
  XOR V3, V1
  XOR V3, V2
  OUT sum, V0
  OUT mix, V3
;CODE
```

`10 20 30 SUM-XOR`の結果は`60 0`である。

## Stack contract

`( a b c -- sum mix )`は機械可読な契約であり、単なるコメントではない。

- 入力名は左から通常のFORTH stack表示順に並ぶ。`c`がTOS、`a`がその2段下である。
- `IN V0, a`はentry frameの`a`を読むだけで、stack位置を変えない。
- `OUT sum, V0`は結果をstaging領域へ置くだけで、直ちにstackへ書かない。
- 全命令が成功し、すべての出力がちょうど1回設定された時だけ、入力3個を結果2個へ置換する。
- 検査または実行が失敗した場合、呼出し前のstackはそのまま残る。
- R0ではstackを途中で書き換える`SSET`、`PUSH`、`POP`を設けない。

内部表現では`a=S2, b=S1, c=S0`と考えられるが、sourceでは名前を使用する。

## 初めて読む人へ：3種類の名前

次の名前は役割が異なる。

1. `( address -- data io )`内の`address`、`data`、`io`は、作者が自由に付けるstack入出力名である。
2. `V0`から`V3`は仮想assemblerが予約するregister名である。
3. `[DATA: V1]`や`[IO: V1]`の`DATA`、`IO`は実行環境が登録するmemory capability名である。

例えばstack名は次のように意味が分かる名前へ変更できる。

```forth
CODE: READ-BOTH ( pointer -- ram-value device-value )
  IN V3, pointer
  LD32 V0, [RAM: V3]
  LD32 V1, [SENSOR: V3]
  OUT ram-value, V0
  OUT device-value, V1
;CODE
```

stack名とcapability名は英字で始め、以後に英数字、`-`、`_`を使用できる。stack名はCODE定義内の
対応を示す名前であり、`address`などの特別な予約語ではない。capability名は自由な綴りだが、
実行時に同じ名前のwindowが登録されていなければアクセスを拒否する。

## R0命令

仮想レジスタは`V0`から`V3`までの32-bit cellである。算術結果は32 bitに丸める。

| 分類 | 形式 | 意味 |
|---|---|---|
| 入出力 | `IN Vd, name` | 名前付きentry inputを読む |
|  | `OUT name, Vs` | 名前付きresultをstagingする |
| 転送 | `MOV Vd, Vs` | register間コピー |
|  | `LIT Vd, value` | 10進または`0x`形式の定数 |
| 算術 | `ADD/SUB/MUL Vd, Vs` | `Vd = Vd op Vs` |
| 論理 | `AND/OR/XOR Vd, Vs` | bit単位演算 |
|  | `NOT Vd` | bit反転 |
| shift | `LSL/LSR/ASR Vd, n` | 0から31 bitのshift |
| rotate | `ROL/ROR Vd, n` | 32-bit rotate |
| 比較 | `CMP Va, Vb` | 以後の分岐用に2値を比較 |
| 分岐 | `BEQ/BNE @label` | equal / not equalで分岐 |
|  | `BLT/BGE @label` | signed比較で分岐 |
|  | `BLTU/BGEU @label` | unsigned比較で分岐 |
|  | `BRA @label` | 無条件分岐 |
| label | `@label:` | 分岐先を定義 |
| memory | `LD32 Vd, [Va]` | 検査済み32-bit読出し |
|  | `LD32 Vd, [Va+4]` | 正の定数offset付き読出し |
|  | `ST32 [Va-4], Vs` | 負の定数offset付き書込み予約 |
| capability | `LD32 Vd, [DATA: Va+4]` | 名前付きmemory windowから読出し |

条件分岐の前には、その経路上で必ず`CMP`を実行しなければならない。loopは記述できるが、
基準実装は命令数上限を持ち、上限超過時にはstackを変更せず失敗する。
call、division、CPU固有命令は後続版とする。

### 分岐例

```forth
CODE: MAX ( a b -- max )
  IN V0, a
  IN V1, b
  CMP V0, V1
  BGE @a-wins
  OUT max, V1
  BRA @done

@a-wins:
  OUT max, V0

@done:
;CODE
```

`@`は「この位置」を表すMIN0仮想アセンブラの印である。推奨表示ではlabel定義を左端、
命令を2文字字下げする。ただし、小さな画面での編集ミスを避けるため、先頭空白は意味に含めない。
従来の`LABEL name`と`BRA name`形式も移行用互換構文として受理する。

## 検査付きmemory access

`LD32/ST32`がアクセスできるのは、呼出し側が明示的に渡したmemory windowだけである。
角括弧内の空白は意味を持たないため、`[V1+4]`、`[ V1+4 ]`、`[V1 + 4]`、
`[ V1 + 4 ]`はすべて同じaddressingとして扱う。
次をすべて満たさないアクセスは、CPUのload/storeを行う前に拒否する。

1. effective addressが32-bit address空間内にあり、加減算で桁あふれしていない。
2. 4-byte境界に整列している。
3. 4 byte全体が許可されたwindow内にある。
4. windowが要求されたread/write権限を持つ。

`ST32`は実行中に物理memoryを書き換えず、transaction内へ予約する。同じCODE内の後続`LD32`は
予約値を読める。すべての命令とstack contractが成功した時だけ書込みを確定し、errorや命令数超過時は
stackとmemoryの両方を開始前のまま残す。

複数のwindowを使う場合は`[DATA: V1+4]`、`[IO: V1]`のようにcapability名を付ける。
同じ数値addressを持つwindow同士でも名前によって完全に分離される。名前なしの`[V1+4]`は、
呼出し側が明示した既定capabilityだけを使用する。既定がない場合や未知の名前は拒否する。

## 静的検査

実行前に次を拒否する。

1. 未定義のinput/output名。
2. 初期化前のregister読出し。
3. outputの重複設定または未設定。
4. 未知の命令、register、operand形式。
5. 0から31の範囲外のshift/rotate量。
6. 未定義または重複したlabel、`CMP`を通らず到達できる条件分岐。
7. ある実行経路だけで欠けるoutput、同じ経路で2回設定されるoutput。

## 今後の拡張

1. R0 reference implementationでPython/Ruby相互一致を確認する。
2. 仮想命令からPico 2 W向け機械語を生成する。
3. relocation、W^X publication、実機上のFORTH stack contractを検証する。

表現力を増やす場合も、6809のaddressing modeのような便利さは仮想命令側へ追加し、
安全性検査とCPU backendを分離する。
