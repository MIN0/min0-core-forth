# FORTHの設計と学習のための参考資料

[英語版はこちらです](REFERENCES.md)

FORTHの重要な説明は、古い書籍、archive、現在も動く実装に分散しているため、資料名がわからないと
探しにくいことがあります。このページは、各資料が何を知るために役立つかを示し、出版社やprojectが
管理するページへ案内する短い道しるべです。

> [!NOTE]
> MIN0 CORE FORTHは、ここで紹介する書籍や第三者実装を収録していません。リンクは読書案内であり、
> 外部資料が本リリースの一部であることや、同じワードと動作を持つことを意味しません。

## 最初に読む順番

| 知りたいこと | 最初の資料 |
| --- | --- |
| 理論より先にFORTHを体験したい | Guided Viewer、その次に[ワード・ポケットリファレンス](WORD_REFERENCE_JP.md) |
| 通常のFORTH programmingを学びたい | *Starting FORTH*、その次に*Thinking FORTH* |
| 辞書とinterpreterの仕組みを知りたい | FIG-Forth、CF、*eForth and Zen* |
| なぜFORTHがこの形なのかを考えたい | *Programming a Problem-Oriented Language* |
| 小規模MPUへの移植を考えたい | 430eForth資料と小さなVM実装 |

## FORTH設計

- [Forth Interest Group（FIG）](https://www.forth.org/) — 教育資料、reference、各種実装、FORTH
  communityのarchiveへ進むための歴史的な入口です。
- [FIG-Forth implementations](https://www.forth.org/fig-forth/contents.html) — 多数のprocessor向け実装を
  scanまたは文字化して公開しています。OCRには誤りがあり得ると明記されているため、重要なprogram
  listingは画像と照合する必要があります。
- [CF FORTH](https://github.com/CCurl/cf) — primitiveとinner／outer interpreterを見通せる、小さなC版
  FORTH VMです。小さなVMとsourceで定義するワードの境界を比べる資料になります。
- [RETRO FORTH](https://retroforth.org/) — 理解しやすい小さなvirtual machineを中心とする、移植性を
  意識した現代的なForthです。言語環境をhost CPUから分けるもう一つの実例です。

これらはMIN0 CORE FORTHの設計を考えるための参考資料であり、source codeの親ではありません。本projectは
独自のPython版とRuby版および試験を使用しています。VMの形、辞書構造、primitive、解釈、compile、移植性の
選択を比較するために紹介しています。

## FORTHを学ぶための書籍

### まず言語を学ぶ

- [『標準FORTH』井上外志雄 著―国立国会図書館サーチ](https://ndlsearch.ndl.go.jp/books/R100000002-I000001755527)
  — FORTHの初歩から応用までを扱う1985年の日本語書籍です。catalogにはデジタル化済みとありますが、閲覧には
  国立国会図書館の登録利用者向け個人送信や図書館送信などの条件があります。
- [*Starting FORTH*―FORTH, Inc.公式online版](https://www.forth.com/starting-forth/)
  — Leo Brodieによる図解入りの定番入門書です。stack、定義、条件判断、loopを順に学ぶ最初の一冊に向きます。
- [*Thinking FORTH*―FORTH, Inc.公式書籍ページ](https://www.forth.com/forth-books/)
  — Leo Brodieによる、問題をワードへ分解し、FORTHの長所を保ったprogramを書くための本です。出版社の
  ページから公開版へ進めます。

### 実装と設計を深く知る

- [*eForth and Zen*―FIGが保存する第2版PDF](https://www.forth.org/OffeteStore/1013_eForthAndZen.pdf)
  — Dr. Chen-Hanson Tingによる、小さなeForth実装の解説です。ほかの版も存在するため、codeやarchitectureを
  比較するときは版を確認してください。
- [*Zen and the Forth Language: eForth for the MSP430 from Texas Instruments*―430eForth資料](https://forth-ev.de/wiki/en%3Aprojects%3A430eforth%3Astart)
  — 制約のあるmicrocontrollerへeForthを組み立てる具体例です。共通のFORTH coreから、実機固有の子systemを
  育てる方法を考える際に特に参考になります。
- [*Programming a Problem-Oriented Language: Forth — how the internals work*―Charles H. Mooreによるonline本文](https://colorforth.github.io/POL.htm)
  — 問題に合わせて言語を育てる考え方と、input、stack、辞書、定義、memoryを説明します。操作方法だけでなく、
  FORTHがなぜこの構造になったのかを考えるための資料です。

## 実装ごとの差を忘れないために

上の書籍とsystemは、時代、標準、cell幅、threading方式、対象機器が異なります。同じ名前のワードでも、存在しない、
または境界条件が違う場合があります。MIN0 CORE FORTHで実装している動作は、
[ワード・ポケットリファレンス](WORD_REFERENCE_JP.md)と実行可能な試験を最終的な確認先としてください。

## 元資料と外部リンクの境界

この道しるべは、[*forth-in-motionの日本語版参考資料](https://github.com/MinoruKishi/forth-in-motion/blob/main/docs/ja/REFERENCES.md)と
[英語版](https://github.com/MinoruKishi/forth-in-motion/blob/main/docs/en/REFERENCES.md)を基に、MIN0 CORE FORTH向けに
新しく説明を書いたものです。外部siteはそれぞれの所有者と利用条件の下にあり、将来URLや公開状況が変わる場合があります。
