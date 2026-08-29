# MIN0 CORE FORTH image execution profiles R0

## 何を区別するのか

`reference32-le`はcell幅、endian、address表現を示すimage形式profileである。一方、
`safe-runtime`／`standard-build`は、そのimageを実行してよい環境を示す。両者は別の軸である。

| image execution profile | 内容 | 実行できる環境 |
| --- | --- | --- |
| `safe-runtime` | runtime専用変更命令を必要としない | safe-runtime、standard-build |
| `standard-build` | compiled `IS`の`DSET`を含み得る構築用image | standard-buildだけ |

通常配布・正式運用するnormal imageと、最後の復旧経路であるrecovery imageは`safe-runtime`とする。
`standard-build`は構築・検証中のartifactであり、そのまま実機配布するrelease imageではない。

## profileを誰が決めるか

callerが文字列だけを指定する方式にはしない。compilerがcompiled `IS`を生成すると、relocation manifestへ
`defer-store-slot`を記録する。image builderはこの署名対象記録を調べ、次のように必要profileを自動導出する。

```text
defer-store-slotなし  -> safe-runtime
defer-store-slotあり  -> standard-build
```

導出結果はimage envelope v5の`execution_profile`へ保存され、component digest、allocator、manifest digest、
generation、roleなどと共に`identity_sha256`とEd25519署名へ結び付く。

## Loaderの検査順序

```text
bounded package parse
  -> envelope v5／role／generation
  -> execution_profileとLoader policyの互換性
  -> component／allocator／manifest整合性
  -> relocation記録からprofileを再導出して申告と照合
  -> identity／署名／rollback検証
  -> inactive slotへ書込み
```

safe-runtime Loaderへstandard-build imageを渡すと、inactive slotを消去・書込みする前に拒否する。
standard-build Loaderはsafe-runtime imageとstandard-build imageの両方を検査できる。recovery roleへ
standard-build imageを作ることは、build時とload時の双方で常に拒否する。

## 改ざんに対する意味

署名済みstandard-build imageの`execution_profile`だけを`safe-runtime`へ書き換えても、relocation要件との
不一致およびsigned identity不一致になる。manifestから`defer-store-slot`だけを消してもmanifest digestと
identityが変わり、正規鍵で再署名しない限り受理されない。

ただしprofileは権限そのものではない。standard-build環境でもVMの`allow_defer_store`、`DSET`のdestination／
target検査、Monitor接続時のpermission lockが引き続き必要である。

## bytecode verifierによる二重照合

`BYTECODE_VERIFIER_R0.md`で、typed relocationだけでなく実CODEを命令境界に沿って復号する検査を追加した。
`DSET`実命令と`defer-store-slot`記録が一対一で一致した場合だけ`standard-build`を導出する。immediate data中の
`0x25`は命令境界ではないためDSETと誤認しない。

compiler／linker／signerは引き続きtrusted build boundaryだが、署名者の単純なbuild取り違えや、CODEとmanifest
の片側だけを偽装する誤りはLoaderのpre-write検査でも拒否できる。

## 実働確認

Python／Rubyの両方で、実際にcompiled `IS`を含む署名imageを生成した。profile自動導出、safe Loaderの
pre-write拒否、standard-build環境でのslot B導入、profile改ざん拒否、recovery拒否を一致確認する。

```powershell
python -m unittest -v test_image_execution_profile.py
ruby test_ruby_image_execution_profile.rb
python cross_image_execution_profile_check.py
```
