# MIN0 CORE FORTH DEFER source words R0

## 目的

kind-7 DEFERと認証済みMonitor切替えを、FORTHらしいsource表現で操作できるようにする。本R0は標準word名と
基本的なinterpretation semanticsを採用するが、まだ完全なForth標準適合を主張しない。

## source syntax

| source | stack effect | R0の意味 |
| --- | --- | --- |
| `DEFER name` | `( -- )` | target未割当てのkind-7 wordを作る |
| `' name` | `( -- xt )` | 辞書entryの実XT addressを積む |
| `IS defer-name` | `( xt -- )` | DEFERを指定XTへ設定する |
| `ACTION-OF defer-name` | `( -- xt )` | DEFERの現在target XTを積む |

例:

```forth
: OLD-ACTION  10 ;
: NEW-ACTION  20 ;

DEFER ACTION
' OLD-ACTION IS ACTION

: USE-ACTION  ACTION ;
USE-ACTION              \ 10

' NEW-ACTION IS ACTION
USE-ACTION              \ 20
ACTION-OF ACTION         \ NEW-ACTIONのXT
```

`USE-ACTION`は切替え前にコンパイル済みである。内部には`ICALL ACTION-XT+4`があり、`IS`後もcaller codeを
再コンパイルしない。

## R0の制限

- `DEFER`、`'`、interpret-state `IS`は通常outer interpreterではinterpret state専用。
- DEFER targetはcolon definitionだけ。primitiveやconstant等の一般XT実行はまだ行わない。
- 未割当てDEFERの実行と`ACTION-OF`はerror。
- `[']`とcompiled `ACTION-OF`はsafe-runtime profileで利用できる。
- compiled `IS`はsafe-runtimeでは拒否し、明示的なstandard-build profileだけで利用できる。

compile-time semanticsを急いで追加すると、通常applicationが実行中に自分でcontrol slotを書き換える入口に
なり得る。このため`COMPILED_DEFER_R0.md`では、安全profileとimage構築profileを分離した。

## build phaseと運用phase

Monitor control planeへ接続する前は、image build phaseとして通常outer interpreterから次を使用できる。

```forth
DEFER SERVICE
' INITIAL-SERVICE IS SERVICE
```

`MonitorControlAuthority`がruntime dictionaryを受け取ると、辞書のDEFER mutation入口をopaque authorizationで
lockする。それ以後、一般outer interpreterによる`IS`は辞書cellを変更する前に拒否される。

停止中の認証済みMonitorは次の限定control sourceを受け取れる。

```forth
' NEW-SERVICE IS SERVICE
ACTION-OF SERVICE
```

一つ目は通常のtoken実行を行わず、厳密な4-token grammarを認証済み`switch_defer`へ変換する。二つ目は
observerでも利用できるread-only照会である。その他のsource、数値、任意word実行、コメントからの命令注入は
control commandとして扱わない。

## failure safety

- `IS`はDEFER entry、target XT、target kind、code実行可能性、書込み範囲を検査してから単一cellを更新する。
- Monitor lock後の一般`IS`、observerによるmutation、非DEFER source、非colon targetを拒否する。
- API外操作でstackまたは辞書が変化した場合、resume invariant sealが再開も拒否する。
- `ACTION-OF`はcode addressの代用品ではなく、辞書entryのXTそのものを返す。

## 実働確認

Python／Rubyで、未割当てerror、旧target=`10`、`ACTION-OF`と旧XTの一致、`IS`後の新target=`20`、新XTとの
一致、非colon拒否、compile-state拒否、typed relocationを完全一致確認する。

```powershell
python -m unittest -v test_defer_source.py
ruby test_ruby_defer_source.rb
python cross_defer_source_check.py
```
