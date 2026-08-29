# MIN0 CORE FORTH compiled DEFER profiles R0

## 目的

colon definition内でexecution tokenを取得・観察・変更するsource semanticsを、標準との近さだけで一括許可
せず、運用時の安全性に応じて二つのprofileへ分ける。

| profile | `['] name` | compiled `ACTION-OF name` | compiled `IS name` |
| --- | --- | --- | --- |
| `safe-runtime`（既定） | 可 | 可 | 拒否 |
| `standard-build` | 可 | 可 | 可 |

`standard-build`は正式なForth標準適合宣言ではない。image構築時にcompile semanticsを検証するための実験profile
であり、通常運用imageの権限ではない。

## read-only compile semantics

```forth
: XT-OF-NEW      ['] NEW-ACTION ;
: CURRENT-ACTION ACTION-OF ACTION ;
```

`['] name`は実行時にnameの辞書XTを積む。

```text
LIT name-XT
```

compiled `ACTION-OF defer-name`は、実行時にDEFER slotを読み、その時点のtarget XTを積む。

```text
LIT defer-XT+4
FETCH
```

どちらも辞書を書き換えないためsafe-runtimeで利用できる。compilerはそれぞれ`xt-literal`と
`action-of-slot`というDICTIONARY型relocationを記録する。

## compiled IS

```forth
: SWITCH  ['] NEW-ACTION IS ACTION ;
```

standard-build profileでは次を生成する。

```text
LIT  NEW-ACTION-XT
DSET ACTION-XT+4
```

`DSET`は単なる`STORE`ではない。次をすべて検査してから一cellだけを変更する。

1. VMが`allow_defer_store`付きimage-build構成である。
2. destination直前のkind cellが7、つまり本物のDEFER slotである。
3. DATA stack上のXTが非zeroでkind 1のcolon wordである。
4. XT payloadのcode addressが実行可能である。
5. slotが書込み可能である。

失敗時はtarget XTをpopせず、slotも変更しない。relocation kindは`defer-store-slot`である。

## 二重の運用境界

safe-runtime profileはcompiled `IS`をsource compile時に拒否する。さらに、standard-buildで既に`DSET`を含む
wordがimageへ存在していても、通常VMの`allow_defer_store=false`により実行時に拒否する。

`MonitorControlAuthority`接続時には必ずVMのDEFER-store bitをfalseへlockする。このbitもresume invariant sealへ
含め、後から有効化された場合は再開を拒否する。したがって辞書API lockとVM opcode gateの二段になる。

```text
一般source IS          -> dictionary authorizationで拒否
precompiled DSET word   -> VM profile gateで拒否
bitの外部再有効化       -> resume invariantで拒否
認証済みMonitor source  -> switch_defer transactionだけ許可
```

## 実働確認

safe-runtimeでは`[']`がNEW-ACTION XTを返し、compiled `ACTION-OF`が現在のOLD-ACTION XTを返す一方、compiled
`IS`をrollback付きで拒否した。standard-buildでは同じcompiled `IS`によりACTIONの結果が10から20へ変化した。
そのwordをMonitor接続後に実行すると`DeferStoreDenied`となり、targetは旧値のまま残った。

Python／RubyでXT、結果、拒否理由、relocationを一致確認する。

```powershell
python -m unittest -v test_compiled_defer.py
ruby test_ruby_compiled_defer.rb
python cross_compiled_defer_check.py
```

## imageへの引継ぎ

このprofile分離は`IMAGE_EXECUTION_PROFILES_R0.md`で署名imageとLoaderへ引き継いだ。compiled `IS`の
`defer-store-slot`から`standard-build`を自動導出し、safe-runtime Loaderはslot書込み前に拒否する。

## 次の検討

- 標準word setとの対応表でinterpretation／compilation semanticsの差を明示する。
- authenticated Monitor transactionからcolon semanticsを安全に実行する必要が本当にあるかを検討する。
