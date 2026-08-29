# MIN0 CORE FORTH bytecode verifier R0

## 目的

relocation manifestに書かれた「このimageには何がある」という申告だけを信用せず、CODE componentの実byte列を
命令境界に沿って復号し、申告と現物を二重照合する。署名者が誤ったbuild artifactへ署名する事故も、Loaderが
slotへ書く前に検出する。

## なぜraw byte検索では不十分か

`DSET`のopcodeは`0x25`だが、次の`0x25`は数値データであって命令ではない。

```text
CODE+0: LIT
CODE+1: 25 00 00 00   <- 4-byte operand
CODE+5: EXIT
```

CODE先頭から「opcodeは1 byte、operand付きopcodeは続く4 byte」を順に復号すると、`CODE+1`は命令境界では
ないと分かる。R0 verifierは`LIT 0x25`をsafeと判定し、本物の`DSET`だけから
`compiled-defer-store` capabilityを導出する。

## 検査内容

1. CODE全体を先頭から末尾まで復号し、未知opcodeと切断operandを拒否する。
2. 各命令先頭addressをboundary集合として記録する。
3. `CALL`、`BRANCH`、`ZBRANCH`、loop系の直接CODE targetがboundaryを指すことを検査する。
4. DICTIONARY descriptorを含む全CODE向けrelocation targetもboundaryを指すことを検査する。
5. operandを必要とする命令とtyped relocationを一対一で照合する。
6. relocationがopcode byte、operand途中、operandを持たない命令へ付いていないことを検査する。
7. 実命令からcapability summaryを導出する。

主な対応は次のとおりである。

| opcode | 必須target | 許可するrelocation kind |
| --- | --- | --- |
| `CALL` | CODE | `call`, `does-call` |
| `ICALL` | DICTIONARY | `defer-slot` |
| `DSET` | DICTIONARY | `defer-store-slot` |
| `SERVICE` | relocation禁止 | 非0のnumeric service ID |
| `BRANCH` | CODE | `branch` |
| `ZBRANCH` | CODE | `zbranch` |
| `LOOP`／`PLOOP`／`QDO`／`LEAVE` | CODE | 同名のloop記録 |

`LIT`は通常数値ならrelocationを持たない。addressを積む場合だけ`xt-literal`、`action-of-slot`、
`data-literal`、`does-body`、`string-address`を許可する。

`SERVICE`の4-byte operandはaddressではない。verifierは実命令から重複のない`service_ids`と命令addressを
導出し、ID 0、切断operand、relocation付きID、operand途中へのbranchを拒否する。VM sealはこの導出結果を
target所有registryと照合し、必要handlerがなければCODEを`rx`へ移す前に失敗する。成功後は導出IDだけを
実行可能とし、registry登録も一方向に凍結する。

## capabilityと署名profileの接続

```text
実CODEにDSETなし + 対応記録なし
  -> capabilities []
  -> execution_profile safe-runtime

実CODEにDSETあり + defer-store-slotが正確に一致
  -> capabilities [compiled-defer-store]
  -> execution_profile standard-build
```

次の片側だけでは受理しない。

- CODEに`DSET`があるが記録がない。
- `defer-store-slot`記録があるが、その位置は`LIT` operandである。
- DSET operandへ別kind／別targetの記録が付いている。

導出されたexecution profileはimage envelope v5のsigned identityへ結び付く。Loaderは同じverifierを再実行し、
署名profile、実CODE、typed relocationの三者が一致した場合だけinstallへ進む。

## 実働拒否例

Python／Rubyで次を同一結果として確認した。

- `LIT 0x25`をDSETと誤認しない。
- 正しいDSETからcapabilityとaddressを導出する。
- DSET記録欠落と偽DSET記録を拒否する。
- 切断CALL operandと未知opcodeを拒否する。
- branchがLIT operand途中を指すimageを拒否する。
- dictionary colon-code entryがoperand途中を指すimageを拒否する。
- SERVICE ID 1を導出し、ID 0、切断、偽relocation、operand途中branchを拒否する。
- 必要service未登録時はCODEを封印せず、成功後のservice追加を拒否する。
- 従来の「末尾EXITをbit反転して別imageを作る」デモが、切断CALLを偶然生成していたことを検出した。

```powershell
python -m unittest -v test_bytecode_verifier.py
ruby test_ruby_bytecode_verifier.rb
python cross_bytecode_verifier_check.py
python cross_service_output_check.py
ruby test_ruby_service_boundary.rb
```

## R0の限界

本verifierは構造とtyped addressを検査するが、プログラムの意図までは証明しない。構文上正しい無限loop、
意図的な`STORE`、stack underflowへ至る制御経路、各colon definitionが必ず`EXIT`へ到達することなどはR0の
対象外である。署名鍵管理、compiler／linkerの保護、VM実行時検査も引き続き必要である。

次段階では、dictionaryからentry point集合を作ったcontrol-flow graph、到達可能命令、stack effectの静的検査を
どこまで小規模targetで負担できるか検討する。

実行中のCODE／pointer変更に対するruntime boundaryと一方向CODE sealは`SEALED_EXECUTION_R0.md`へ進んだ。
