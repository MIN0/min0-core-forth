# MIN0 Device Lab 初心者ガイド

## このガイドの位置付け

MIN0 Device Labは、未知のセンサや周辺機器を調べ、device manifestとcapabilityを自分で定義し、
FORTHまたは仮想assemblerから安全に試すための学習環境である。この機能は現在設計中であり、本文は
今後の実装と教材作成の基準を定める。

初心者へ最初から正解の部品表だけを渡すのではなく、他人の失敗を観察し、原因を予想し、仮想機器で
安全に再現してから実機へ進む。失敗を放置せず、「どの情報を調べれば原因に近づけるか」を学ぶことを
目的とする。

## 学習の順序

1. 他人の失敗例と、判断に使った情報を読む。
2. 原因を予想し、段階的なヒントを使って調べる。
3. 仮想機器で同じ失敗を再現する。
4. manifestまたはCODEを自分で修正する。
5. Viewerで検査、access、commit／rollbackを観察する。
6. 安全条件を確認して実機で試す。
7. 自分が調べた型番、data sheet、配線、結果を探索記録へ残す。

電圧や配線を誤ると実機を破損し得る課題は、最初に仮想機器だけで行う。実機課題では、危険な失敗を
意図的に再現させない。

## 特設コラム Aさんが買ったのは本当にBME280か

### Aさんが見た情報

Aさんは販売記事で、次の説明があるmoduleを見つけた。

```text
温度・湿度・気圧センサ
BME280互換
I2C／SPI対応
Raspberry Piで使用可能
```

写真もBME280 moduleによく似ていたため、AさんはBME280だと判断して購入した。Pico 2 Wへ3.3Vで
接続すると温度と気圧は取得できたが、湿度を取得できなかった。chip ID registerからは、期待した
`0x60`ではなく`0x58`が返った。

Aさんは「MIN0のBME280処理にbugがある」と判断した。

### 考えてみよう

1. Aさんの判断には、どの確認が不足していたか。
2. 温度と気圧が得られ、湿度だけ得られない理由として何が考えられるか。
3. MIN0のbugと判断する前に、何を照合すべきか。
4. 販売記事の商品名、写真、互換という表現は、実物を確定する証拠になるか。

### ヒント1

BME280とBMP280は名前と機能の一部が似ているが、同じchipではない。

### ヒント2

販売記事の商品名よりも、実機自身が返すchip IDとICメーカーのdata sheetを強い証拠として扱う。

### 原因を整理する

BME280は温度、湿度、気圧を測定する。BMP280は温度と気圧を測定するが、湿度測定機能を持たない。
Raspberry Pi公式のBME280 SPI例は起動時にchip ID `0x60`を確認する。Raspberry Pi公式のBMP280
I2C例はBMP280の既定address `0x76`、識別register、温度・気圧register、校正値を使う。

- [Raspberry Pi公式 BME280 SPI例](https://github.com/raspberrypi/pico-examples/tree/master/spi/bme280_spi)
- [Raspberry Pi公式 BMP280 I2C例](https://github.com/raspberrypi/pico-examples/tree/master/i2c/bmp280_i2c)
- [Bosch Sensortec BMP280 data sheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp280-ds001.pdf)

この現象では、販売記事がBME280として紹介したmoduleにBMP280が搭載されている可能性を最初に調べる。
`0x58`という結果だけで偽物と断定せず、配線、読んだregister、通信誤り、module上のmarkingも確認する。

```text
販売記事の商品名       BME280互換
期待したchip           BME280
期待したchip ID        0x60
実機から読んだ値       0x58
確認すべき可能性       BMP280、誤配線、誤register、通信異常
```

### このコラムの大切な考え方

> 商品名と外観は候補を見つける情報であり、実物を確定する証拠ではない。

次の順序で根拠を強くする。

1. ICメーカーと正確な型番を確認する。
2. ICメーカーのdata sheetを取得する。
3. 電源電圧とGPIO信号電圧を分けて確認する。
4. 通信方式、address、識別register、期待するchip IDを調べる。
5. 実機からchip IDを読み、期待値と照合する。
6. 一致してから初期化や継続的な測定へ進む。

### Device Labでの安全な再現

最初はBME280として登録し、仮想機器が`0x58`を返す教材を用意する。

```text
DEVICE: ROOM-SENSOR
  MODEL    BME280
  BUS      I2C0
  ADDRESS  0x76
  ACCESS   READ WRITE
;DEVICE
```

実行結果は、単に失敗とせず根拠を表示する。

```text
DEVICE_ID_MISMATCH
expected model: BME280
expected chip ID: 0x60
actual chip ID:   0x58
physical write:   not executed
next check: wiring, ID register, data sheet, mounted chip
```

学習者は調査結果に基づいてmanifestをBMP280へ修正する。修正後に湿度機能を要求した場合は、
`FEATURE_NOT_AVAILABLE`として拒否し、温度と気圧だけを利用できることを確認する。

## 1課題で扱う失敗は一つにする

初期課題では複数の原因を同時に混ぜない。各課題を次の主題へ分ける。

- 型番：BMP280とBME280の取り違え
- 電圧：電源電圧とGPIO信号電圧の違い
- I2C：`0x76`と`0x77`のaddress違い
- 配線：SDAとSCL、電源、GNDの確認
- 権限：read-only registerへのwrite
- 範囲：存在しないregisterへのaccess
- data形式：16-bit値のbyte順序と符号
- 校正：raw値と物理量の違い
- timeout：未接続機器を待ち続けない設計
- module：同じchipを搭載する基板間の周辺回路の違い

## 各コラムの共通形式

1. 登場人物が見た記事や商品情報
2. その情報から行った判断
3. 発生した現象
4. 読者への質問
5. 段階的なヒント
6. 仮想機器での再現
7. 原因候補の絞り込みと修正
8. 今回の大切な考え方
9. 実機へ進む前の安全確認
10. 探索記録へ残す項目

解答を暗記させるのではなく、観察事実と推測を分け、次に調べる情報を自分で選べるようにする。

## 独立した教材であること

MIN0 Device LabはMIN0 CORE FORTHプロジェクトによる独立した学習教材として扱う。Raspberry Piの
公式教材または推奨を意味しない。製品名、商標、data sheet、公式exampleは各権利者に帰属し、引用元と
確認日を探索記録へ残す。
