# MIN0 CORE FORTH bounded persistent package R0

## 目的

外部fileからFORTH image、trust bundle、root policy chainを読み込む共通入口を定める。対象は新規FORTH
のhost executable specificationであり、MSX0-FORTHには変更を加えない。

暗号署名が正しくても、署名検証へ到達する前のparserが巨大長、section重複、整数overflow、深いJSONで
停止すれば安全なloaderにはならない。本R0は、可変長dataを解釈する前に固定長headerで上限を検査する。

## file format v1

fileは次の順序を持つ。整数はすべてlittle-endian unsignedである。

```text
32-byte fixed header
N * 32-byte fixed directory entries
contiguous section payload
32-byte SHA-256 container checksum
```

### fixed header

| field | size | R0 |
| --- | ---: | --- |
| magic | 8 | `FCPKG0 CR LF` |
| version | 2 | 1 |
| kind | 2 | image=1, trust-bundle=2, root-policy-chain=3 |
| section count | 2 | kindごとの固定数 |
| flags | 2 | 0のみ |
| directory bytes | 4 | count × 32と完全一致 |
| payload bytes | 4 | configured上限以下 |
| complete file bytes | 4 | 実file長と完全一致 |
| reserved | 4 | 0のみ |

directory entryは16-byte NUL-padded ASCII section名、payload-relative offset、length、flags、reservedを
持つ。offset／length／flags／reservedは各4 byteである。

kindごとのsection名と順番は固定する。

```text
image              envelope, code, dictionary, data
trust-bundle       trust-bundle
root-policy-chain  root-chain
```

任意sectionの追加をv1 readerが推測して読み飛ばすことはしない。新sectionが必要ならformat versionまたは
kindを更新する。

## R0 host limits

```text
file total       1,048,576 bytes
section count            8
payload total      786,432 bytes
one binary section 524,288 bytes
metadata section   262,144 bytes
JSON depth              32
JSON string          4,096 characters
JSON integer            20 digits
JSON values         20,000
```

これは全targetへ1 MiBを要求する意味ではない。`ParserLimits`を小規模MPU／FPGAのmemory profileに
合わせて狭める。重要な規則は、targetごとに有限上限を持ち、file自身が要求した長さを上限にしないこと
である。

外部file APIは最大file長+1 byteだけを読む。+1 byteを読めた時点で、container headerやJSONを解析せず
oversizeとして拒否する。

## canonical metadata

envelope、trust bundle、root chainはUTF-8 canonical JSONで保存する。

- object keyを文字列昇順にする
- whitespaceを入れない
- duplicate keyを拒否する
- float／NaN／Infinityを禁止する
- depth、string、integer桁、node数を制限する
- NUL、不正UTF-8、非canonical表現を拒否する

readerはJSON parse後に再canonical化し、入力byte列と完全一致することを確認する。したがって、同じ意味に
見える複数表現や、言語ごとに解釈が異なり得る重複keyを署名検証層へ渡さない。

## 検証順序

```text
1. 読込み量上限
2. fixed header magic／version／kind／count／全length
3. complete file length
4. container checksum
5. directory名／順序／flags／連続範囲／section上限
6. bounded canonical JSON
7. root policy chain署名・epoch
8. trust bundle root署名・epoch
9. image component digest・role・generation・Ed25519署名
10. 検証済みimageだけを実行／install
```

前段が後段の代わりになることはない。container checksumは媒体破損やtorn copyの検出用であり、秘密情報を
使わないため攻撃者も再計算できる。authenticityはroot／trust／image署名が担当する。

## 実働round-trip

公開fixtureを用いて次を実行した。

1. old/new cross-signed root policy chainをpackage化・再読込・epoch 2検証
2. new root署名trust bundleをpackage化・再読込・epoch 2検証
3. image keyで署名したgeneration 7 imageを実fileへ書込み
4. bounded file APIで再読込
5. role、generation、component digest、Ed25519署名を検証
6. CODE／DICTIONARY／DATAを復元し、実際のFORTH word列を実行

最終stackは`[99, 2, 3, 3, 0, 2, 7, 32768]`となった。Python／Rubyが生成した3 packageはfile長、
全byte、SHA-256まで一致した。

## 攻撃・破損監査

次の15入力を拒否した。

- 途中切断
- 末尾への余分data
- checksum不一致
- payload declared length bomb
- section count bomb
- unknown version／unknown kind
- duplicate／reordered section
- overlapping section
- section length bomb
- duplicate JSON key
- whitespaceを含むnoncanonical JSON
- depth超過JSON
- 20桁を超えるJSON integer
- 1 MiBを超える外部file

さらにCODEを改変してcontainer checksumを正しく付け直したfileは、container構造検査を通過した後、
image component digest／署名検証で拒否された。この二段階結果を回帰試験へ固定した。
正規署名envelopeへ署名対象外の未知fieldを追加したfileも、image schemaのfield完全一致検査で拒否した。
v1 readerは未知fieldを黙って無視しない。

## R0の限界

- host modelは最大1 MiBをbufferへ読む。小規模targetでは固定buffer／streaming readerへ移植する。
- file書込みAPI単体はatomic updateを保証しない。実installは既存A/B transactionを使用する。
- filesystem path、symlink、permission、removable mediaのmount policyはhost／target依存である。
- 圧縮を許していないためdecompression bombは存在しない。将来追加時は展開後上限が必要。
- 暗号実装の計算時間budget、watchdog、loader capability分離は次段階である。
- root chainの安全なcheckpoint圧縮は未実装である。

このparser、root/trust検証、normal/recovery A/B installの結合は`LOADER_STATE_MACHINE_R0.md`へ進んだ。
次はloader操作のcapability分離と、実媒体profileでの電源断試験である。

## 実働ファイル

- `min0_core_forth_persistent.py`／`.rb`: bounded container、canonical JSON、file API
- `persistent_package_demo.py`／`.rb`: 三package round-trip、実行、攻撃監査
- `test_persistent_package.py`／`test_ruby_persistent_package.rb`: 固定vectorと回帰
- `cross_persistent_package_check.py`: Python／Ruby byte-level照合
