# MIN0 CORE FORTH constructor plan v0.1 候補版監査 R0

日付: 2026-08-28  
状態: constructor plan metadataの候補版を凍結。

## 今回凍結した範囲

今回の凍結対象は、MIN0 CORE FORTH全体ではなく、辞書内に置かれるconstructor planの
形式と意味だけである。

```text
+0   u32  MAGIC = 0x4E4C5043  ("CPLN")
+4   u32  FORMAT-VERSION = 1
+8   u32  STEP-COUNT >= 1
+12  step[0]
     ...

各step:
+0   u32  executable CODE address
+4   u32  allocator action ID
```

action IDは次の値で固定する。

| ID | action | v0.1での意味 |
|---:|---|---|
| 0 | END | 最後のCODE断片後にconstructorを終了 |
| 1 | COMMA | cellを保存 |
| 2 | C-COMMA | 下位1バイトを保存 |
| 3 | ALLOT | 非負のバイト数を予約 |
| 4 | ALIGN | data HEREを4バイト境界へ整列 |

この表の番号、step配置、既存actionの意味を変更する場合はFORMAT-VERSIONを更新する。
未知versionを旧readerが推測して実行することは禁止する。

## 読出し監査

Python版とRuby版の双方で、次の破損を実際に辞書メモリへ書き込み、拒否を確認した。

- MAGIC不一致
- FORMAT-VERSION不一致
- STEP-COUNTが0
- STEP-COUNTがdescriptor領域を越える巨大値
- 未知action ID
- ENDが途中に存在
- 最終stepがENDではない
- planがdescriptorと重なる
- CODE addressが非実行DICTIONARY領域を指す
- definer descriptorが非整列

破損planは子の生成前に拒否される。入力stack、header HERE、data HERE、LATESTは
変化せず、hiddenの子も残らない。

## 書込み監査

plan writerへ次の不正入力を与え、辞書イメージが一バイトも変化しないことを確認した。

- 空plan
- 未知action
- ENDの欠落
- ENDの早過ぎる出現
- 非実行領域のCODE address
- VMメモリ外のCODE address

## 実行途中の失敗監査

形式上は正常なplanの最初のCODE断片を不正opcodeへ置き換え、子をhiddenで作成した後の
VM失敗を発生させた。その場合もPython/Ruby双方で次を開始前へ戻す。

- DATA、RETURN、LOOP stack
- header HERE、data HERE、LATEST
- 未完成の子とそのbody領域

既存のCOMMA/C-COMMA/ALLOT/ALIGN試験では、stack underflow、負数ALLOT、容量不足、
最後のALIGNだけが失敗する場合についても同じatomic rollbackを確認済みである。

## 回帰試験結果

- Python: 151 tests passed
- Ruby: 18 test files passed
- Python/Ruby cross-checks: 20 passed

凍結後の可搬性確認として、Python保存→Ruby読込み、Ruby保存→Python読込みの
双方向round-tripも実施した。詳細は`CONSTRUCTOR_IMAGE_ROUNDTRIP_R0.md`に記録した。

## 今回凍結していない範囲

- MIN0 CORE FORTH全体の永続image header
- CPU/MPU別のABIとbytecode変換規則
- CODE、DICTIONARY、DATAの実配置
- 新しいconstructor actionの追加方法
- constructor内の分岐・ループを含む非線形plan

したがって、今回の成果は「大樹の根」全体の凍結ではない。移植先に依存しない
constructor metadataの最初の安定した根を作った段階である。
