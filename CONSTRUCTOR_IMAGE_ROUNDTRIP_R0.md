# MIN0 CORE FORTH constructor image相互読込み R0

日付: 2026-08-28  
状態: Python/Ruby間の双方向round-trip実証済み。

## 目的

候補版として凍結したconstructor plan format version 1が、作成した言語や
プロセスに依存せず再読込みできることを確認する。

今回使うJSON envelopeは試験用の搬送容器であり、MIN0 CORE FORTH全体の最終的な
persistent image形式ではない。内部のCODE、DICTIONARY、DATA bytesは実物であり、
readerは新しいVMメモリへ配置してから辞書を再検証する。

## 搬送する情報

- envelope formatとversion
- memory size
- CODE base、code HERE、CODE bytes
- DICTIONARY base/limit、header HERE、LATEST、DICTIONARY bytes
- DATA base/limit、data HERE、DATA bytes
- 監査対象`RECORD:`のplan address
- writer名（診断表示のみ）

アドレス値とbytes長が一致しないimage、16進文字列でないbytes、未知envelope
versionは、メモリへ取り込む前に拒否する。

## component loader

`RuntimeDictionary.load_images`をPython/Rubyへ追加した。このAPIは次の制約を持つ。

- 新しく作成した空辞書だけが読込み可能。
- CODE bytesは先にVMの実行領域へ配置する。
- DICTIONARYとDATAの長さ・上限・LATESTを検査する。
- 読込み後に辞書linkを走査する。
- KIND_DEFINERのdescriptorとconstructor planを再検証する。
- KIND_DOESのdescriptorとbehavior addressを再検証する。
- 検査失敗時は読込んだbytesを消去し、空辞書へ戻す。

これはraw componentを安全に採用するためのAPIであり、ファイルheaderや移植先ABIを
決めるものではない。

## 双方向試験

保存対象は次の定義である。

```forth
: RECORD: CREATE C, ALLOT ALIGN ;
```

相手言語で読み込んだ後、次を実行する。

```forth
2 0x1AB RECORD: ITEM
ITEM
```

両方向で一致した結果:

```text
plan version: 1
actions:      [2, 3, 4, 0]
stack:        [0x8000]
ITEM body:    0x8000
body bytes:   AB 00 00 00
data HERE:    0x8004
```

確認した方向:

1. Pythonで保存 → Rubyで読込み・実行
2. Rubyで保存 → Pythonで読込み・実行

writer名だけを除いたenvelope payloadも一致した。

## version拒否

次の二種類をPython/Ruby両readerが拒否することを確認した。

- JSON搬送容器のversionを1から2へ変更
- DICTIONARY bytes内のconstructor plan versionを1から2へ変更

後者はcomponent loaderによる辞書再検証中に拒否され、loaderはHERE、LATEST、
data HEREと読込み領域を空状態へ戻す。

## 回帰試験結果

- Python: 151 tests passed
- Ruby: 18 test files passed
- Python/Ruby cross-checks: 20 passed

## 次の境界

round-tripによってconstructor metadataの可搬性は確認できた。しかし、次の項目は
まだ最終決定していない。

- binary image headerとchecksum
- 複数memory regionの格納順序
- absolute addressのまま保存するか、relocation情報を持つか
- MPUごとのcell幅・endianness変換
- 起動entry pointと静粛実行オプション

次段階では、すぐに最終image形式を決めるより、absolute address imageと
relocatable imageのどちらをMIN0 CORE FORTHの根に置くかを先に検討する。
