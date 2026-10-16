# Mobile Learning入力queue R0

## 目的

Phase Cでは、実行中のFORTHへiPhone／PC画面から文字を渡す。最初のR0では、入力を直接DOMから
読み取らず、Viewerと実行器の間に上限付きUTF-8 byte queueを置く。Blob Worker版とmain-thread互換版は
同じqueue、同じ検査、同じword意味論を使う。

## R0境界

- queue容量はsessionごとに最大256 UTF-8 byteとする。
- `input` command 1回の`text`も1～256 UTF-8 byteに限定する。
- 容量超過、空文字列、未知fieldは、現在sessionを変更せず拒否する。
- queueはVMのtransactional stateに含める。Abortでは実行開始時のqueueへ戻す。
- 表示済み出力と同様に、画面側ですでに確定した人間の入力操作そのものは消さない。
- R0はbyte queueであり、1文字queueではない。たとえば`A`は1 byte、`あ`はUTF-8で3 byteである。

## `KEY?`

```forth
KEY?  ( -- flag )
```

queueに1 byte以上あればtrue（32-bit cellの`-1`）、空ならfalse（`0`）を積む。queue内容は消費しない。
したがって、何度`KEY?`を実行しても、別のwordが読むまでは同じ入力を検出できる。

## Worker command

protocol `min0-mobile-monitor/0.2`へ次を追加する。

```text
input { text: string }
```

`running`、`pause-requested`、`paused`、`stepping`で受理できる。受理時はUTF-8 byteをqueueへ追加し、
`input-enqueued` updateを返す。入力追加だけでPause中の処理を勝手に再開しない。

## 次段階

次は`KEY`を「queueが空ならWorkerをblockせず、`waiting-input`停止点へ入る」wordとして設計する。
画面に入力欄と送信buttonを追加するのは、この待機・再開規則と監査表示を試験で固定した後に行う。

