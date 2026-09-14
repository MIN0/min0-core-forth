# MIN0 CORE FORTH `FOR ... NEXT`直接loop設計 v0.2

[English version](FOR_NEXT_DIRECT_V0_2.md)

状態：Python版とRuby版host referenceへ実装済みの実験仕様。

## 決定事項

`DO ... LOOP`は標準FORTH互換のcolon definition用構造として維持する。直接入力の回数指定loopには、
CFの考え方を基礎としてMIN0向けに拡張した`FOR ... NEXT`を使用する。直接入力とcompile済み定義は
同じ反復結果を与える。

```forth
3 FOR I NEXT
: INDEXES 3 FOR I NEXT ;
```

どちらも`0 1 2`を生成する。`0 FOR ... NEXT`は0回実行する。

ここで「直接入力」はinterpret状態のpromptまたはsource実行を意味し、`: ... ;`でcompileしたCODEの
実行時とは区別する。

## CFとの関係

CFの`for`、`i`、`next`はVM primitiveであり、loop frameへindex、count、`for`直後のCODE addressを
保存する。この方式はcompile済みCODEを自然に反復できる。一方、CFのouter interpreterは直接入力した
各tokenを小さな一時CODE slotで個別実行するため、直接入力された本体全体をbufferに保存して再実行はしない。

MIN0はCFのcount入力、0始まりindex、loop frameという考え方を採用し、直接入力については完全な本体を
token bufferへ収集する拡張を加える。したがって「CF準拠」ではなく「CF-inspiredなMIN0拡張」と位置づける。

## semantics

```forth
FOR   ( u -- )
I     ( -- index )
J     ( -- outer-index )
NEXT  ( -- )
```

- `u`はunsigned 32ビットcell一個とする。
- indexは`0`から`u-1`まで進む。
- `u=0`では本体を実行しない。
- 多重loopは既存VM loop stackを使い、`I`は最内側、`J`は一つ外側のframeを参照する。
- 直接入力とcompile済みloopの両方にVMのloop深度上限を適用する。

compile状態の`FOR`は`LIT 0`とexit patch付き`QDO`を生成し、`NEXT`は本体先頭を指す`LOOP`を生成して
exitを解決する。新しいVM opcodeやimage ABI項目は追加しない。

## 直接入力の収集

interpret状態で`FOR`を検出すると`u`を消費し、direct-loop状態へ移り、対応する`NEXT`まで解析済みtokenを
収集する。多重`FOR ... NEXT`は収集中に深度を数えて対応づける。外側の`NEXT`が存在し、本体検査が成功する
まで本体tokenは一つも実行しない。

host referenceの既定上限は次のとおり。

- token buffer：最大4096 token
- 直接実行budget：100,000 token／iteration単位
- 多重loop：VM loop stack上限。通常32 frame

対話launcherは`NEXT`待ちの間`...> `を表示する。file入力終了または対話EOFでは`finish_input`を呼び、
未完了loopをrollbackして報告する。

## 現在の直接loop本体の範囲

数値、通常の実行可能な辞書word、`I`、`J`、出力word、`."`、多重`FOR ... NEXT`を使用できる。
初期実装ではcompile構造、`DO`系構造、`UNLOOP`、source定義／allocation word、`S"`を拒否する。
本体から呼ばれるcolon wordの内部では、compile済み制御構造を通常どおり使用できる。

反復開始前に構造tokenと辞書名を検査する。収集、検査、実行に失敗した場合、DATA stackとloop stackを
direct-loop入力block開始時へ戻す。ただし、実行時errorより前に外部へ出した表示や、完了済みwordによる
任意memory書込みはtransactionalには戻さない。

## 診断

この節はv0.2時点の動作記録である。`DIRECT_CONTROL_V0_3_JP.md`では同じbuffer方式を
`DO ... LOOP`と`DO ... +LOOP`の直接入力にも拡張した。対応しない／未終了の終端、buffer超過、
実行budget超過、loop stack超過は引き続き決定的なerrorとする。
