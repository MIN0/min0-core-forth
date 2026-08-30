# MIN0 CORE FORTH transactional relocation linker R0

## 目的

CODEとDICTIONARYで別々に生成した型付きrelocation recordを一つのmanifestへまとめ、
すべてのrecordを検査してからimageを再配置する。検査途中で失敗した場合、入力componentと
manifestを一切変更しない。

このR0 manifestはPython／Ruby間の実行仕様であり、persistent file形式の凍結ではない。

## manifest envelope

R0 envelopeは次を持つ。

- `format`: `min0-core-forth-relocation-manifest`
- `version`: 1
- `profile`: `reference32-le`
- `records`: CODE／DICTIONARY双方の型付きrecord列

recordのfieldは`CODE_RELOCATION_R0.md`で定めた`section`、`offset`、`target`、`width`、
`kind`を用いる。今回の実imageではCODE 15件とDICTIONARY 53件、合計68件を一つの列として
処理した。

## transaction

linkerは次の順序で動く。

1. 入力CODE、DICTIONARY、DATAを変更不能なsource imageとして読む。
2. source／target baseと三componentのReference32範囲・相互重複を検査する。
3. manifest headerと全recordを検査し、patch予定値をメモリ上の作業列へ作る。
4. 一件でも不正なら、patchを一度も適用せず失敗する。
5. 全件が正しければ三componentのprivate copyを作り、copyだけへpatchする。
6. 完成した三つの新しいbyte列を返す。実機memoryへのinstallは呼出し側の別transactionとする。

これにより、後半のrecordが壊れていても、前半だけ書き換わった半端なimageは生じない。

## R0 validator

次を拒否する。

- manifest format、version、profileの不一致
- 未知のpatch sectionまたはtarget section
- Reference32以外のwidth
- 空のkind
- component外のoffset
- DICTIONARY内でcell境界に揃わないpatch
- 同一section内で重なるpatch
- source target component外を指すcell値
- target component同士の重複
- base、component末尾、patch結果の32ビット範囲越え

DATA addressだけは、割当て前の空bodyを指すCREATE系wordを表現できるよう、使用済みDATAの
末尾と等しいone-past addressを許す。CODEとDICTIONARYでは末尾そのものを許さない。

## 破損試験

Python／Rubyで同じ小型componentを使い、正常な3 recordをlinkした。CODE内の
`0x1004`は`0x4004`へ、DATA参照`0x3000`は`0x6000`へ、DICTIONARY内のCODE参照
`0x1000`は`0x4000`へ変換された。record対象外の`0xDEADBEEF`とDATA bytesは変化しない。

続いて次の9種類を意図的に壊し、両言語がすべて拒否し、source componentとmanifestが
呼出し前のままであることを確認した。

1. 未知version
2. 未知section
3. width 8
4. component外offset
5. 重複／交差patch
6. source target外pointer
7. target component重複
8. Reference32 overflow
9. 空kind

## 完全image確認

`full_image_relocation_demo.py`／`.rb`を手書きpatch loopから本linkerへ切り替えた。統合68件を
検査・適用した後、CODE `0x2000`、DICTIONARY `0x5000`、DATA `0x9000`のimageをloadし、
CALL、条件分岐、loop、VARIABLE、DOES wordを再実行した。結果は従来の個別patch実験と一致した。

## 未凍結・次の課題

- target profileが持つ領域容量・権限まで含む配置検査
- `LATEST`、CODE-HERE、header HERE、data HEREなどimage envelope metadataの統合
- manifest checksum、component digest、record canonical order
- persistent binary表現と後方互換規則
- link完了componentをruntime memoryへ原子的にinstallするloader transaction

この次段階は`IMAGE_ENVELOPE_R0.md`で実装した。allocator metadata、component digest、manifest
digestを一つのidentityへ結び付け、「別のimageに対する正しいmanifest」の取り違えをpatch前に
検出する。次は認証方式を選ぶ前のthreat modelを整理する。
