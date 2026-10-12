# MIN0 小容量環境でも安全に失敗するための移植原則

## 目的

MIN0は、利用者の間違いをすべて禁止するのではなく、危険な影響が出る前に停止し、原因を観察して
修正と再試行へ進めるFORTHを目指す。この性質はRasPi 5やPCだけの機能にせず、Pico 2 W、将来の
小容量CPU、未知のCPU、FPGAでも、対象の資源に応じた形で維持する。

中心原則は、安全に停止して戻る機構と、詳しく説明して学習を助ける機構を分離することである。
容量が不足したときに削減するのは説明の長さ、履歴量、表示能力であり、安全境界そのものではない。

> 詳しい説明を載せられない小さなCPUでも、失敗の事実と復旧結果だけは失わない。  
> 説明は後から取り戻せても、壊れた状態は取り戻せない。

## 安全に失敗できたと呼ぶ条件

失敗は、次の条件を満たすときに学習可能な結果として扱える。

1. 危険なmemory、IO、分岐操作を実行する前に不合格を検出する。
2. FORTH DATA stack、実行frame、未確定writeを、定められた復旧状態へ戻す。
3. 稼働中の旧wordを壊さず、新しい定義だけを破棄できる。
4. 何を試し、どこで止まり、何が保全されたかを診断recordへ残す。
5. 利用者が一つ修正して、同じ条件から再試行できる。

外部機器への出力、flash消去、network送信など、実行後に完全には戻せない操作は別に扱う。実行前の
確認、出力上限、時間制限、watchdog、緊急停止などをtarget profileで定める。

## 値を作る自由と使用許可を分離する

stack上のcellは、作成時点で整数、address、index、XTのいずれかへ固定しなくてよい。利用者は値を自由に
計算できる。その値を`@`、`!`、`LD32`、`ST32`、間接分岐、IO操作へ使用する瞬間に、用途に対応する
capability、範囲、alignment、権限、entry条件を検査する。

数値であることは、任意のmemoryや実行位置へアクセスする権限を意味しない。静的に確定できるlabelと
分岐範囲はlink時、動的なaddressと間接分岐先は実行直前に検査する。通常演算や検証済み直接分岐を毎回
再監査せず、危険な境界を越える操作だけをruntime helperまたはtarget固有の検査経路へ通す。

## 配列と構造体を支える最小descriptor

将来の配列と構造体は、重い型システムを必須にせず、次のような小さなdescriptorから始める。

```text
object-id
base
length
element-size または field-layout-id
permissions
generation
```

利用者は名前付きの検査済みaccess wordを使用できる一方、実験profileでは手計算したaddressも扱える。
検査時には、indexとbyte offsetの混同、範囲外要素、未整列、古いgeneration、read／write権限違反を
区別して記録する。名前や長いfield説明はViewer側へ置き、target側は数値IDだけを保持できる。

## targetに残すcompact diagnostic record

小容量targetは長い説明文ではなく、固定長または上限付きの診断recordを残す。

```text
error-code
word-id
operation-id
program-position
observed-value
expected-lower
expected-upper
stack-depth
recovery-result
hint-id
```

recordは直近数件のring bufferへ保存できる。UART、USB、Wi-Fi、保存領域のいずれかで取り出し、PCや
iPhoneのViewerがerror-code、word-id、hint-idを詳しい説明、修正候補、source位置へ展開する。

target単体でも、短い形式で事実を確認できるようにする。

```text
E-MEM-003 WORD=17 OP=LD32 ADDR=20030148
RANGE=20030100..2003013F ACTION=ABORT STACK=RESTORED HINT=02
```

少数の頻出hintだけはtarget内へ置ける。詳細説明を外部Viewerへ移しても、エラー番号、観測値、許可範囲、
復旧成否は省略しない。

## 容量に応じたprofile

### Learning profile

- 詳しい説明、修正候補、source対応、stack表示を有効にする。
- 複数件のtraceと診断履歴を保持する。
- red zoneや追加の整合検査を使用する。

### Normal profile

- 同じ安全検査とrollbackを維持する。
- 表示を短縮し、必要なときだけ詳細をViewerから参照する。
- publication済みcodeは再監査せず、動的な危険操作だけを検査する。

### Constrained profile

- compact diagnostic recordと少数の短いhintを残す。
- 履歴件数、source保持量、rollback世代数を減らす。
- editor、compiler、assemblerは対象に必要な最小機能だけを組み込む。
- 詳細説明と可視化を外部Viewerへ移す。

### Raw Laboratory profile

- 制限解除は通常命令と異なる明示的な操作にする。
- watchdog、復旧image、実験領域、緊急停止を必須条件としてtargetごとに定める。
- 保証できないrollbackや外部副作用を、保証済みであるかのように表示しない。

## 稼働中更新と容量不足時の限界

安全なlive更新では、稼働中の旧wordを維持したまま、新wordを一時領域でcompile、link、auditする。
成功後だけ検索対象またはentryを新版へ切り替え、失敗時は新wordだけを破棄する。追記型dictionaryは
この方式と相性がよい。

新旧の定義とscratch領域を同時に保持できないtargetでは、完全なlive更新とrollbackを保証しない。
対象機能を一時停止して更新する、再起動時に既知の保存imageへ戻す、外部loaderを利用するなど、容量に
合った方式へ段階的に落とす。資源不足を理由に、安全性を黙って無効化しない。

## 実装を三層に分離する

### Safety kernel

capability検査、abort、rollback、transaction、compact diagnostic recordを担当する。最小targetでも
維持すべき共通核である。

### Target adapter

CPUのmemory保護、call／return、watchdog、IO、保存領域、通信手段へ共通契約を対応付ける。保証できる
復旧範囲と外部副作用をtarget profileへ明記する。

### Learning interface

Viewer、Monitor、詳細説明、修正候補、source対応、履歴比較を担当する。target内、RasPi 5、PC、iPhoneの
いずれに置いてもよく、安全核と同じ診断recordを解釈する。

この分離により、RasPi 5では豊かな説明を提供し、Pico 2 Wでは単体診断と外部Viewerを併用し、さらに
小さなCPUでは安全核とcompact recordだけを残せる。

## 新しい機能とtargetを評価する問い

1. target単体で、失敗した操作と復旧結果を確認できるか。
2. 詳細説明がなくても、安全な停止と旧状態の保全は成立するか。
3. Viewerはtargetが実際に記録した事実だけを説明しているか。
4. 配列、構造体、memory、間接分岐の検査を、値の自由な計算と分離できているか。
5. 検査をcompile、link、publication、runtimeの適切な段階へ配置しているか。
6. 容量不足時に何を削り、何を保証し続けるかが明記されているか。
7. live更新不能なtargetで、その制限を利用者へ正直に示しているか。
8. 失敗後に同じ条件から修正と再試行へ進めるか。

この原則は、機能を固定して将来の実験を狭めるためのものではない。自由な値、実験profile、未知のtargetを
受け入れながら、容量や実装方法が変わっても「安全に止まり、事実を残し、次の試行へ戻る」というMIN0の核を
見失わないための判断基準である。
