# MIN0 CORE FORTH runtime DICTIONARY capability R0

## 目的

DICTIONARYにはword名やlinkだけでなく、XT kind、colon code pointer、DOES descriptor、constructor plan、DEFER
targetが入る。DATAと同じ通常`rw`として扱うと、Forthの`!`が意味を知らないまま実行先を変更できる。

一方、DICTIONARY全体を物理的read-onlyにすると、認証済みMonitorによる意図的なDEFER切替えも失われる。
R0では次の三層を重ねる。

```text
Memory region   通常write／programをopaque capabilityなしでは拒否
Dictionary API header・allocator・descriptor等の構造変更を一方向凍結
Monitor gate    停止点、認証、型検査、audit後のDEFER payload 4 byteだけ更新
```

## 公開時の状態遷移

```text
image load中
  DICTIONARY rw / structure mutable
       |
       | load完了、全entryとdescriptorを検証
       v
safe-runtime publish
  DICTIONARY rw / write-protected / structure sealed
  DATA       rw / ordinary ! allowed
  CODE       rx / sealed
```

DICTIONARYの表示permissionが`rw`なのは、Monitor gateが限定書込みを行うためである。ただし通常write pathとloader
program pathには、permissionに加えて非公開のidentity capabilityが必要になる。Forth stackへ同じ数値を置いても
capabilityにはならない。

## 構造凍結

`seal_runtime_structure`後は次を拒否する。

- `:`による新headerとXTの追加
- `CONSTANT`、`VARIABLE`、`CREATE`、`DEFER`の追加
- hidden flagの公開／変更
- `DOES>` descriptorとconstructor planの追加
- `,`、`C,`、`ALLOT`、`ALIGN`によるallocator前進
- component imageの再loadとdictionary rollback／clear
- Forthの生`!`、host通常write、loader programによるDICTIONARY変更

development buildではこのsealを行わないため、従来どおり対話的にwordを作成・再定義できる。凍結対象は
safe-runtimeへpublishされた実行用dictionaryである。

## Monitor DEFER gate

runtime seal直後は通常の`IS`を拒否する。Monitor接続時にopaqueな論理authorizationをdictionaryへ登録する。
Monitorは停止点で次を確認する。

1. sessionがMonitor profileであり、observerや失効sessionではない。
2. VMがwatchdog中ではなく、承認済みpause状態である。
3. source側がDEFER word、target側が実行可能なcolon wordである。
4. resume sealに対するout-of-band変更がない。

確認後、dictionary内部だけが物理write capabilityを短時間開き、DEFER XTのpayload cellを書き換える。終了時には
scopeが必ず閉じられ、変更内容をauditへ記録する。一般source、observer、偽のhost tokenはこのscopeを開けない。

## 実働確認

```powershell
python -m unittest -v test_dictionary_capability.py
ruby test_ruby_dictionary_capability.rb
python cross_dictionary_capability_check.py
```

実際の公開済みimageで次を確認した。

- `123 CELL ! CELL @`は123を返し、DATA更新は維持される。
- headerおよびDEFER payloadへの生`!`を拒否し、DICTIONARY全体が不変である。
- `: INTRUDER 1 ;`、`1 ,`、一般sourceの`' TARGET-B IS ACTION`を拒否する。
- loader program、二重seal、FlatMemoryでのseal、偽capability、observerによる切替えを拒否する。
- 認証済みMonitorは`ACTION`を`TARGET-A`から`TARGET-B`へ切替え、`USE`は9を返す。
- Monitor前後の差分は、対象DEFER payloadの4-byte範囲内だけである。

## R0の限界

- 同processでprivate fieldやhost objectを自由に改変できる攻撃者に対するsandboxではない。
- capability scopeはsingle-threaded reference VMを前提とする。並行runtimeではthread／coreごとのscopeが必要になる。
- runtimeで新しいwordを対話定義する場合は、safe-runtimeを解除せず、別のdevelopment/build環境でimageを作り直し、
  検証済みA/B slotとして再publishする方針である。
- 将来、統計counterなどDICTIONARY内で正当な可変metadataが必要になれば、DEFERとは別capabilityと領域を定義する。
