# MIN0 CORE FORTH image addressing検討 R0

## 目的

新規FORTHを小規模MPU、FPGA、その他の異なる実装へ移植するとき、同じimageを
どこまで別のメモリ配置へ移せるようにするかを決める。ここで扱うアドレスは
Reference32の32ビット論理byte addressであり、物理メモリの種類やバス配線そのもの
ではない。

constructor plan v0.1の形式は凍結済みだが、この文書は完全な永続image形式を
凍結するものではない。

## 三つの方式

### A. 絶対アドレスimage

CODE、DICTIONARY、DATAの論理baseをbuild時に決め、実行時はimage中の値をそのまま
利用する。

- loaderとruntimeが最小で、起動が速い。
- branch、CALL、XT、body参照を実行時に変換する必要がない。
- 小容量ROM/RAMのsystemに適する。
- 配置が異なるtargetには再buildまたはlinkし直したimageが必要になる。

### B. 完全再配置可能image

loaderが起動時に全アドレス参照を見つけ、配置差分を加えてから実行する。

- 一つのimageを複数配置へ持ち運びやすい。
- relocation table、loader code、書換え可能領域、起動時間が必要になる。
- FORTHの通常cellには型がないため、単なる数値とアドレス候補をbyte列だけから
  区別できない。
- `LIT`のoperandも、普通の数値かアドレスかはcompile後の命令列だけでは確定しない。

したがって「出来上がったbyte列を走査すれば完全に再配置できる」という仕様には
できない。compiler、辞書allocator、image linkerが、アドレスを書いた時点で
relocation recordを残す必要がある。

### C. ハイブリッド方式（R0推奨）

runtimeは解決済みの絶対論理アドレスを使う。一方、build/link段階では型が判明して
いる参照についてrelocation manifestを生成し、target profileの論理配置へ変換できる
ようにする。

- targetごとにCODE、DICTIONARY、DATAのbaseと容量をprofileで指定する。
- image linkerはmanifestに記録された参照だけを再配置する。
- 実機起動時は原則として再配置済みimageを読み、runtimeの負担を増やさない。
- RAMへloadするtargetでは、同じmanifestをloaderが使用して起動時再配置してもよい。
- 生の`,`で保存した利用者cellは、明示的に「アドレス」と指定されない限り数値として
  扱い、自動変更しない。

これにより、小規模systemでは絶対アドレス方式と同じ単純なruntimeを保ちつつ、
開発時には異なる配置へ安全にlinkできる。

## 実働実験

`constructor_relocation_demo.py`と`constructor_relocation_demo.rb`は、実際に生成した
`RECORD:`辞書imageから型付き参照を列挙し、三領域を同時に`+0x1000`移動する。

| 領域 | 元のbase | 移動後base |
| --- | ---: | ---: |
| CODE | `0x1000` | `0x2000` |
| DICTIONARY | `0x4000` | `0x5000` |
| DATA | `0x8000` | `0x9000` |

今回manifestへ記録した場所は次のとおりである。

- 辞書headerのLINK
- word kindで意味が確定するXT payload
- DOES descriptorのbody／behavior参照
- definer descriptorのconstructor plan／behavior参照
- constructor plan各stepのCODE参照

31件（CODE向け4件、DICTIONARY向け27件、DATA向け0件）を再配置した後、移動先imageを
`RuntimeDictionary.load_images`で再検証した。さらに
`2 0x1AB RECORD: ITEM ITEM`を実行し、`ITEM` bodyが`0x9000`に作られ、
`ab 00 00 00`が保存され、data HEREが`0x9004`になることをPython/Ruby双方で確認した。

DATA向けが0件なのは、保存した元imageに生成済みchildやVARIABLEが含まれないためで
ある。これは「任意のDATA cellも再配置できた」という証明ではない。

## relocation recordの最小意味

R0では、各recordは少なくとも次の意味を持つ。

- patch section: 書換え対象が存在する領域
- patch offset: その領域baseからのbyte offset
- target region: 値がCODE、DICTIONARY、DATAのどれを指すか
- width/profile: Reference32ではlittle-endian 32ビットcell

最初のconstructor実験ではpatch sectionがDICTIONARYだけだったため、offsetとtarget region
だけを保持した。続くcompiler実験ではCODE section、offset、target、width、kindを明示した。

## compiler／辞書層の責任

- 辞書層はLINK、XT payload、descriptor、constructor planなど、型が確定した参照を記録する。
- compilerは`CALL`、branch target、loop targetなどのCODE参照をemit時に記録する。
- アドレスをpushする`LIT`は、元のsource operationがアドレスを生成した場合だけ記録する。
- 普通の数値literalと、生の`,`／`C,`で作ったdataは自動推測しない。
- 将来、利用者がアドレスcellをimageへ保存するための明示wordまたは型付きimage APIを設ける。

## R0の判断

新規FORTHの推奨方針をハイブリッド方式とする。ただし、まだ永続image file format、
manifestのbyte表現、target profile形式は凍結しない。runtimeの意味論は解決済み絶対論理
アドレスのままとし、再配置はbuild/link責任を基本とする。

この次段階は`CODE_RELOCATION_R0.md`で実装した。compilerがCALL、branch、loop、DATA address
literalを15件記録し、辞書側53件と合わせて、colon word、条件分岐、VARIABLE、DOES wordを
含むimageを別baseで実行した。次は両sectionのrecordを統合して検査するlinker transactionを
設計する。
