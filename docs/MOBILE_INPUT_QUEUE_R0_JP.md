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

## `KEY`と`waiting-input`

```forth
KEY  ( -- byte )
```

queueに入力があれば先頭のUTF-8 byteを1つ取り出す。空の場合、session版は命令位置とstep数を進めず
`waiting-input`停止点へ入る。schedulerは次chunkを予約しないためbusy loopにならない。

- Runから待った場合、入力到着後はRunへ戻る。
- Stepから待った場合、入力到着後に`KEY`を1命令だけ実行してPauseへ戻る。
- 待機中もPause、Stop、Abortを受理する。
- Pause中に入力した場合は自動再開せず、ContinueまたはStepを待つ。

Viewerには入力欄、送信button、queue byte数を追加した。Enter keyまたはbuttonで1～256 UTF-8 byteを
送信できる。例題`実行中の入力（KEY）`は、`A`を送ると数値`65`と文字`A`を表示する。日本語は1文字ではなく
UTF-8の複数byteとして順番に返す。

## 次段階

次は複数回の`KEY`、Pause中入力、容量超過、Stop／AbortをPC画面で目視確認する。その後、安全な
`VARIABLE`、`@`、`!`へ進む。

