# 新規FORTH 開発チェックポイント（2026-08-26）

## 作業範囲

- このディレクトリは新規FORTH（MIN0 CORE FORTH）の開発用。
- リリース済みMSX0-FORTHとは独立しており、MSX0-FORTHは変更していない。

## 実装済み

- Pythonを先行実行仕様、Rubyを独立した第二実装として維持。
- 32ビットセル、リトルエンディアン、32ビット論理アドレスのReference32。
- データ／リターン／ループスタックと、上限・下限エラー検査。
- ラベル対応簡易アセンブラとMIN0 CORE FORTH中間コードVM。
- 実行時辞書、外部インタープリタ、対話的な `:`／`;` コンパイル。
- 条件分岐、通常ループ、カウントループ。
- `CONSTANT`、`VARIABLE`、`CREATE`、セル／文字データ操作。
- `FlatMemory` による従来互換の64 KiB参照プロファイル。
- `RegionMemory` によるCODE/RAM等の名前付き分割領域と、read/write/execute/program権限。
- 命令フェッチ、データ読出し、データ書込み、ホスト側プログラミングを分離。
- 領域境界またぎ、未配置アドレス、権限違反を決定的なメモリエラーとして検出。

## 最新の確認結果

- Python: 170 tests passed.
- Ruby: 24 test files passed.
- Python/Ruby cross-checks: 27 passed.
- RegionMemory試験では、`rx` CODEから6命令を実行し、`rw` RAMへ
  `0x12345678` を保存・再読出しした。
- CODE通常書込み、RAM命令実行、領域境界またぎ、未配置領域の4エラーを
  Python/Rubyの双方で確認した。

## 決定した設計方針（未実装を含む）

- 64 KiBはMIN0 CORE FORTHの必須制限ではなく、Reference32-Flat64Kの設定値。
- 同名ワードの再定義を許し、以後の名前検索では最新定義を優先する。
- コンパイル済みの直接呼び出し先は自動変更しない。
- 動的変更は将来 `DEFER`／`IS` による明示的な実行ベクタで提供する。
- 無対話起動 `MFORTH -z xxx.fth` を想定し、将来Monitor Profileから
  安全停止、状態確認、差し替え、`CONTINUE` を可能にする。
- 標準的な `[`／`]`（解釈／コンパイル切替）と、停止中アプリケーションへ
  接続する機能は別概念・別ワードとして設計する。
- 未完成の辞書定義は公開せず、完成時にだけ原子的に公開する。
- image addressingは、runtimeでは解決済み絶対論理アドレスを使用し、build/link時に
  型付きrelocation manifestでtarget配置へ変換するハイブリッド方式をR0推奨とする。
- 普通の数値、`LIT` operand、生の`,`で保存されたcellをアドレスだと推測しない。

## 次回の安全な開始点

1. 辞書ヘッダ、実行コード、`CREATE`／`VARIABLE`本体を別々のallocatorから割り当てる。
2. CODE=Flash/ROM、DICTIONARY=EEPROM/FRAM、DATA=SRAMを模した試験を
   Python/Rubyで一致させる。
3. 分割辞書が安定した後、`DOES>` の表現を、コードとbodyの非隣接配置を前提に設計する。

## 再開後の追記

- 辞書と外部インタープリタの直接メモリアクセスを廃止し、VMの
  `read_u8`／`write_u8`／`read_bytes`／`write_bytes`／`fill_bytes` へ移行した。
- CODE=`0x0000..0x7FFF`、DICTIONARY=`0x8000..0xFFFF` の分割構成で、
  `: SQUARE DUP * ; 5 SQUARE` の対話コンパイル、辞書検索、実行を確認した。
- 次の作業点は、辞書ヘッダとデータ本体が隣接するという現在の前提を
  allocatorによって取り除くことである。

## 三領域分割の追記

- 従来配置を既定値として完全互換のまま残し、オプションで辞書ヘッダと
  Forth data spaceを独立した上向きallocatorへ分けられるようにした。
- 分割時の `HERE`、`,`、`C,`、`ALLOT`、`ALIGN` はbody allocatorを使用する。
- `CREATE` と `VARIABLE` のpayloadをbodyの正式な論理アドレスとし、
  `XT + 8` による隣接推測を不要にした。
- CODE=`0000..3FFF`、DICTIONARY=`4000..7FFF`、DATA=`8000..FFFF` で、
  TABLE二セル、FLAG変数、SUM-TABLEのコンパイル・実行を確認した。
- header HERE、data HERE、LATESTの三値を同時にロールバックする。
- 次の設計候補は、この非隣接payloadを前提にした `DOES>` metadataである。

## DOES実行モデルの追記

- 固定8バイトXTを維持したまま、kind 5 (`KIND_DOES`) を追加した。
- kind 5のpayloadはDICTIONARY領域内の2セル記述子を指し、記述子は
  bodyアドレスと動作コードアドレスを保持する。
- `CREATE COUNTER 41 ,` のbodyをDATA、`@ 1 +` の動作をCODE、両者を結ぶ
  記述子をDICTIONARYへ置き、直接実行とコロン定義内呼出しがともに42を返す
  ことをPython/Rubyで確認した。
- 非CREATEワード、実行不可コード、辞書容量不足は変更前のXTとallocator位置を
  保存したまま拒否する。
- 現段階は表現・実行基盤であり、ソース上の `DOES>` と定義ワード内部で動く
  `CREATE` は次の追記で実装した。

## ソースCREATE/DOES>の追記

- kind 6 (`KIND_DEFINER`) と、constructor／behaviorの2コードアドレスを持つ
  定義ワード記述子を追加した。
- `: MAKER CREATE 7 + DOES> 1 + ;` をコンパイルし、`5 MAKER CHILD` が
  実行時に名前を読み取ってhidden状態の子を作り、constructorを実行してから
  KIND_DOESへ変換・公開するようにした。
- `CHILD` の直接実行とコンパイル済み `USE-CHILD` はともに、DATA領域のbodyと
  CODE領域のbehaviorを使用する。
- 名前不足、辞書容量不足、構文不正では、辞書・code HERE・三つのスタックを
  復元し、未完成の子や定義ワードを公開しない。
- 現v0.1では `CREATE` は定義本体の先頭に限定し、constructor内の `,`、`C,`、
  `ALLOT`、`ALIGN` はこの時点では未接続だった。次の追記で `,` を接続した。

## constructor planとVALUE:の追記

- kind 6の記述子先頭セルをconstructor planアドレスとし、planをDICTIONARY領域へ
  `CPLN` magic、step数、CODEアドレス／action IDの組として格納した。
- action 0をEND、action 1をCOMMAとし、VMコード断片の実行後に外部辞書層が
  allocator操作を行う。最小VMへ `,` opcodeは追加していない。
- `: VALUE: CREATE , DOES> @ ; 123 VALUE: ANSWER ANSWER` を実行し、DATA領域
  `0x8000`へ123が保存され、data HEREが`0x8004`へ進み、ANSWERが123を返すことを
  Python/Ruby双方で確認した。
- 初期値なしの `VALUE: EMPTY` はstack underflowとなり、未完成の子、body割当て、
  HERE、LATEST、スタックを復元する。
- 次はplan実行境界へバージョン付き観測イベントを追加し、Guided Viewerの
  実測トレース基盤を作る。次の追記で初版を実装した。

## Guided Viewer実測トレース基盤の追記

- `min0-core-forth-trace/0.1` 形式を追加し、各イベントへ連番、意味名、詳細、IP、
  VM step数、三スタック、header HERE、data HERE、LATESTを記録する。
- `VALUE:` のplan公開、子のhidden作成、二つのCODE断片、COMMA、DOES接続、
  公開、生成完了、DOES実行を13個の意味イベントとして観測した。
- COMMAイベントはDATA=`0x8000`、値=123、data HERE=`0x8004`を実測値として
  保持し、Python/Rubyでイベント、snapshot、基本解説が一致した。
- `VALUE: EMPTY` の失敗では復元後にrollbackイベントを記録する。
- payloadを `observed-data-not-instructions` と明示し、将来AIが利用者のワード名や
  コメントを命令として扱わないための境界を形式へ組み込んだ。
- observerが例外を発生させてもFORTH実行を継続し、observer側の故障だけを別記録
  する試験を追加した。
- 次はこの実測JSONを段階表示する最小Viewerを作り、AIなしの基本解説を体験可能にする。

## 最小Guided Viewerの追記

- Python版の実際の `VALUE:` 実行から13イベントを採取し、自己完結型の
  `viewer/value-trace.html` を生成する `build_trace_viewer.py` を追加した。
- 前後移動、スライダー、自動再生、キーボード操作により一イベントずつ観察できる。
- 各段階で基本解説、対応するFORTHソース行、CODE／DICTIONARY／DATA、三スタック、
  IP、VM steps、header HERE、data HERE、LATESTを同時表示する。
- 段階6でDATA `0x8000`への123の保存とdata HERE=`0x8004`、段階13で
  DATA stackの123を実ブラウザー上でも確認した。console errorは発生していない。
- ネットワークとAIには接続せず、トレース由来文字列をtext nodeとしてのみ表示する。
  生JSONは必要時だけ展開し、観測データを命令として扱う経路を持たない。
- 操作方法と13段階の見どころを `VIEWER_GUIDE_V0_1.md` に記録した。
- 次の候補は、失敗時rollback traceをViewerで比較表示する機能、または
  constructor planへ `C,`／`ALLOT`／`ALIGN` actionを追加する作業である。

## Viewerワード単位表示の追記

- Viewerの既定表示を、13個の大きな意味イベントから9個の完了した
  ソースワード操作へ変更した。従来の表示は `内部イベント` で残した。
- `:` と定義名、定義ワード `VALUE:` と子の名前 `ANSWER` は、FORTHのparserが
  一操作として消費するため、それぞれ「ワード＋引数名」として同時に強調する。
- ソースをワード単位で強調し、各ワードについてDATA stackの
  `実行前 → 実行後`を並べた。`123` は空から123へ、`VALUE: ANSWER` は123から
  空へ、最後の `ANSWER` は空から123への変化として確認できる。
- source-word traceは任意機能であり、既定の13イベントPython/Ruby比較形式を
  変更しない。Viewer生成時だけ有効にする。

## DOESワードstep-in表示の追記

- 最後の `ANSWER` を一操作で結果まで進めず、`ANSWERへ入る`、`body 0x8000を積む`、
  `ANSWER内の@を実行する`、`呼出し元へ戻る`の4段階に分けた。
- コンパイル時にソースワードとCODEアドレス範囲を対応付け、トレース有効時だけVMの
  完了命令位置を受け取る。説明用の推測値ではなく、実際に実行された `@` を特定する。
- `ANSWER › @` ではソース上の `ANSWER` と定義内の `@` を同時に強調し、
  DATA stack=`[32768] → [123]`、RETURN stack=`[0x3FFF]`を画面で確認した。
- ワード表示は9個のソース操作に3個のstep-in段階を加えた12段階となる。
  従来の13意味イベントは引き続き `内部イベント` 表示で確認できる。

## Viewer視線誘導の追記

- 利用時の観察から、FORTHソースの強調だけでは進行の意味が伝わりにくく、
  「今はここを見てください」の説明が理解の入口になることを確認した。
- 解説ラベルを大きな暖色バッジにし、枠の背景、緑の輪郭、影、説明本文を強調した。
- 段階変更時だけ解説枠を短く強調する。`prefers-reduced-motion` が有効な環境では
  アニメーションを無効にし、読みやすさとアクセシビリティを保つ。

## rollback観察シナリオの追記

- 同じViewerで `成功: ANSWER` と `失敗と復元: EMPTY` を切り替えられるようにした。
- 失敗例は初期値なしの `VALUE: EMPTY` を実際に実行し、constructorのCOMMA actionで
  `StackUnderflow`を発生させる。失敗したソースワードは復元後に記録する。
- rollback eventへ保存済みheader HERE、data HERE、LATESTを記録し、最終画面で
  それぞれを復元後snapshotと比較して一致記号を表示する。
- 実ブラウザーでheader HERE=`0x4244`、data HERE=`0x8000`、LATEST=`0x420C`の
  開始前／復元後一致と、三スタックがすべて空であることを確認した。
- 成功例へ戻ると復元欄は消え、通常のワード表示へ戻る。ネットワーク通信、AI接続、
  console errorはない。

## constructor C, actionの追記

- constructor plan action ID 2を `C-COMMA` とし、定義ワード内の `C,` を
  Python/Ruby双方へ接続した。VM opcodeは追加していない。
- `: BYTE: CREATE C, DOES> C@ ; 0x1AB BYTE: FLAG FLAG` を実行し、DATA
  `0x8000`へ低位1バイト`0xAB`を保存、data HERE=`0x8001`、最終stack=`[171]`
  となることを確認した。セル境界への暗黙のalignmentは行わない。
- planは`[C-COMMA, END]`となり、`constructor.c_comma` eventは保存address、
  低位8ビット値、更新後data HERE、三スタックとallocator snapshotを保持する。
- 初期値なしの `BYTE: EMPTY` はstack underflowとなり、子、header HERE、
  data HERE、LATEST、三スタックを開始前へ戻す。
- 新しいbyte constructor demoとcross-checkで、plan、メモリ、stack、13イベント、
  日本語基本解説がPython/Rubyで一致することを確認した。

## 次回の開始点（2026-08-26終了時）

1. constructor planへ `ALLOT` actionを追加し、引数消費、非負制限、容量不足時の
   stack・子・三allocator値のrollbackをPython/Rubyで一致させる。
2. 続いて引数を持たない `ALIGN` actionを追加し、`C,` 後のdata HEREが次の
   4バイト境界へ進むことを確認する。
3. `C, ALLOT ALIGN`を組み合わせた小さな構造体生成ワードを実働例とし、必要なら
   Guided Viewerの新しい観察シナリオへ追加する。
4. Viewerの成功／失敗動画は、録画用の操作順、停止位置、説明文を固定した時点で
   利用者へ録画開始を依頼する。

## constructor ALLOT actionの追記（2026-08-27）

- constructor plan action ID 3を `ALLOT` とし、定義ワード内の `ALLOT` を
  Python/Ruby双方へ接続した。VM opcodeは追加していない。
- `: BUFFER: CREATE ALLOT ; 5 BUFFER: BUF BUF` を実行し、body=`0x8000`、
  data HERE=`0x8005`、最終stack=`[0x8000]`となることを確認した。
- 予約数は非負に限定し、成功した後だけdata stackから消費する。負数では
  `0xFFFFFFFF`、容量不足では要求値3をstackへ残した状態で全体をrollbackする。
- 引数なしのstack underflow、DATA容量2バイトに対する3バイト予約でも、未完成の子、
  header HERE、data HERE、LATEST、三スタックを開始前へ戻す。
- `constructor.allot` eventは開始address、byte count、更新後data HEREとsnapshotを
  保持し、新しいdemo/cross-checkでPython/Rubyのplan、結果、基本解説が一致した。

## 次回の開始点（2026-08-27 ALLOT完了時）

1. constructor planへ引数を持たない `ALIGN` actionを追加する。
2. `C,`でdata HEREを`0x8001`へ進めた後、`ALIGN`で`0x8004`へ揃うことを確認する。
3. `C, ALLOT ALIGN`を組み合わせた小さな構造体生成ワードとrollback試験を作る。
4. 上記が安定した後、Viewerへ新しいallocator観察シナリオを加えるか判断する。

## constructor ALIGN actionと複合planの追記（2026-08-27）

- constructor plan action ID 4を引数なしの `ALIGN` とし、Python/Ruby双方へ接続した。
  これで初期allocator action `, C, ALLOT ALIGN`がすべて実行可能になった。
- `: RECORD: CREATE C, ALLOT ALIGN ; 2 0x1AB RECORD: ITEM ITEM`を実行し、
  plan=`[C-COMMA, ALLOT, ALIGN, END]`、body=`0x8000`、body bytes=
  `[0xAB, 0, 0, 0]`、最終data HERE=`0x8004`、stack=`[0x8000]`を確認した。
- data HEREはC-COMMA後`0x8001`、2バイトALLOT後`0x8003`、1バイトpadding後
  `0x8004`と変化する。各段階を独立したsemantic eventとして記録する。
- DATA上限を`0x8003`にした試験ではALIGN paddingだけが失敗し、それ以前のbyte書込み、
  予約領域、未完成の子を消去して、二入力値と三allocator値を開始前へ戻した。
- 新しい複合demo/cross-checkでaction列、body bytes、三actionのsnapshotと日本語基本解説が
  Python/Rubyで一致した。

## 次回の開始候補（2026-08-27 ALIGN完了時）

1. Guided Viewerへ`RECORD:`のallocator推移を追加し、CODE断片と三actionの境界を
   `0x8000 → 0x8001 → 0x8003 → 0x8004`として体感できるようにする。
2. Viewer化の前に、constructor plan v0.1をこの四actionで一度凍結するか判断する。
3. 凍結する場合はplan validation、破損plan拒否、永続image化に必要なversion情報を監査する。

## Viewer RECORD観察シナリオの追記（2026-08-27）

- Guided Viewerへ実測した`RECORD:`シナリオを追加した。`C,`後`0x8001`、
  `ALLOT 2`後`0x8003`、`ALIGN`後`0x8004`というdata HEREの推移を表示する。
- 表示粒度へ`構築の要所`を追加した。子の生成開始、hidden作成、三allocator action、
  公開、正常終了の7イベントだけを表示し、RECORDシナリオ選択時の既定とした。
- シナリオボタンを埋込みデータから生成する方式へ変更した。今後シナリオを増やす際に
  HTMLへ個別ボタンやイベントlistenerを追加する必要はない。
- `C,`、`ALLOT`、`ALIGN`の各段階で該当ソースワード、DATA領域、実行前後stack、
  data HEREを同時に表示する。`ALLOT`と`ALIGN`のDATA表示も専用形式にした。
- Viewer用Python試験は8件となり、実測allocator event列とdata HERE
  `[0x8001, 0x8003, 0x8004]`、三compile-token解説、自己完結HTMLを検査する。
- 自動ブラウザーによる`file:` URLの操作は安全境界で拒否されたため回避せず、
  HTML生成試験とNode.jsによる埋込みJavaScript構文検査で代替した。

## 次回の開始候補（2026-08-27 Viewer RECORD完了時）

1. 利用者の通常ブラウザーでRECORDシナリオを操作し、7段階の視認性を確認する。
2. 問題がなければconstructor plan v0.1をaction ID 0〜4で候補版として凍結する。
3. 凍結監査ではplan終端、未知action、領域越境、途中失敗rollback、image versionを扱う。

## Viewer RECORD step-in修正（2026-08-27）

- RECORDシナリオの`1ワードずつ`表示が、`RECORD: ITEM`の実行入口から完了地点へ
  直接飛び、constructor内部を表示していなかった。意味実行は正常だったが、入口の
  「中へ入ります」という解説に対して次の画面が対応せず、何もしていないように見えた。
- シナリオごとの`word_step_events`を追加し、RECORDでは生成開始、hidden作成、
  `C,`、`ALLOT`、`ALIGN`、公開、正常終了の7段階へstep-inするよう修正した。
- `DOES>`なしでもconstructorは実行する。違いは、生成された`ITEM`にCREATEの
  既定behavior（実行時にbody addressを積む）が残る点であることを手引きへ明記した。

## 休憩時点（2026-08-27）

- 利用者が修正版Viewerを確認し、RECORDの1ワード表示は情報量が多く難しいため、
  何度か眺めて理解を深める段階となった。
- 次回は表示への感想や新しい疑問を先に確認する。現時点ではconstructor plan v0.1の
  凍結監査を開始せず、Viewerの理解しやすさを確かめてから進路を決める。
- 保存済みViewerは`viewer/value-trace.html`。Python全136試験とViewer専用8試験は成功済み。

## constructor plan v0.1候補版凍結監査（2026-08-28）

- 辞書内plan headerへ明示的なFORMAT-VERSION cellを追加した。version 1の配置は
  `MAGIC, VERSION, STEP-COUNT, steps...`で、headerは12バイトとなった。
- Python/Ruby readerは、magic、version、count、descriptor境界、CODE実行権限、
  action ID、END位置を子の作成前に検査する。definer descriptorのcell整列検査も統一した。
- 破損メモリを直接作る監査試験を追加し、未知version、巨大count、未知action、
  END欠落・早期END、plan/descriptor重複、非実行CODE、非整列descriptorを拒否した。
- writerへ不正planを与えた場合は、header HERE、data HERE、LATESTと辞書bytesが
  変化しないことをPython/Ruby双方で確認した。
- 正常形式のCODE断片を不正opcodeへ変えた実行途中失敗でも、三stack、allocator、
  hidden childを開始前へ戻すことを確認した。
- 全回帰はPython 145件、Ruby 17ファイル、cross-check 19本が成功した。
- `CONSTRUCTOR_PLAN_V0_1.md`のformat version 1とaction ID 0〜4を候補版として凍結した。
  FORTH全体のpersistent image形式や移植先ABIは凍結していない。

## 次回の開始候補（2026-08-28 plan候補版凍結後）

1. MIN0 CORE FORTH全体のimage headerを急いで固定せず、まず候補planの保存・再読込みを
   小さなimage round-tripとして実証する。
2. round-tripではPythonが保存した辞書をRubyが読み、その逆も行い、version拒否も確認する。
3. ViewerのRECORD表示は現状を保ち、理解しやすさについて新しい意見があれば先に反映する。

## constructor image双方向round-trip（2026-08-28）

- raw CODE、DICTIONARY、DATA componentとallocator metadataを運ぶ、試験専用JSON
  envelope version 1をPython/Rubyへ追加した。これは最終persistent image形式ではない。
- 空辞書だけへcomponentを採用する`RuntimeDictionary.load_images`を両言語へ追加した。
  link列、definer plan、DOES descriptorを読込み後に検査し、失敗時は空状態へ戻す。
- Python保存→Ruby読込み、Ruby保存→Python読込みの両方向で`RECORD:`を復元し、
  `2 0x1AB RECORD: ITEM ITEM`を実行した。
- 両方向でplan version 1、actions `[2,3,4,0]`、stack `[0x8000]`、body
  `AB 00 00 00`、data HERE `0x8004`が一致した。writer名以外のenvelopeも一致した。
- envelope version 2と、内部plan version 2の双方をPython/Ruby readerが拒否した。
- 全回帰はPython 151件、Ruby 18ファイル、cross-check 20本が成功した。

## 次回の開始候補（2026-08-28 round-trip完了時）

1. 最終image headerを決める前に、absolute-address imageとrelocatable imageの
   どちらをMIN0 CORE FORTHの根の基本方針にするか比較する。
2. 小規模MPU/FPGAを主対象として、実装容量、起動時間、移植作業量を比較軸にする。
3. Viewerについて新しい感想や疑問があれば、image設計より先に扱う。

## image addressing実験の追記（2026-08-28）

- 絶対アドレス型、完全再配置型、ハイブリッド型を比較し、小規模system向けには
  解決済み絶対アドレスruntimeとbuild/link時manifestを組み合わせる方式を推奨した。
- 実際の`RECORD:` imageから、辞書LINK、XT payload、DOES／definer descriptor、
  constructor planのCODE参照という型付きrelocation 31件を抽出した。
- CODE `0x1000→0x2000`、DICTIONARY `0x4000→0x5000`、DATA `0x8000→0x9000`
  へ同時に移動し、移動先で`2 0x1AB RECORD: ITEM ITEM`をPython/Ruby双方で実行した。
- `ITEM`は新DATA base `0x9000`を返し、body `ab000000`、data HERE `0x9004`を確認した。
- この実験に任意のDATA cellや通常の`LIT`は含まれない。次はcompiler emit時に
  CALL・branch・loop・型付きaddress literalのrelocation recordを残す。
- 詳細は`IMAGE_ADDRESSING_R0.md`に保存した。

## compiler CODE relocationの追記（2026-08-28）

- 対話型compilerが絶対アドレスcellをemitした時点で、section、offset、target、width、kindを
  持つ型付きrelocation recordを残すようPython/Ruby双方を拡張した。
- CALL、BRANCH／ZBRANCH、?DO、LOOP／+LOOP、LEAVEをCODE参照として記録する。
  VARIABLE／CREATEのLITとDOES bodyはDATA参照、DOES behavior CALLはCODE参照とした。
- 普通の数値literalとCONSTANT値にはrecordを付けず、見かけの値からアドレスを推測しない。
- compile失敗時は、CODE、辞書、allocatorとともに、その定義中のrecordもrollbackする。
- colon CALL、条件分岐、通常loop、counted loop、VARIABLE、VALUE:／DOESを含むsourceから、
  Python/Rubyが同一の15件（CODE向け13、DATA向け2）を同じ順序で生成した。
- CODE側15件と辞書側53件を適用し、CODE `0x1000→0x2000`、DICTIONARY
  `0x4000→0x5000`、DATA `0x8000→0x9000`へ完全な小型imageを移動した。
- 移動後も全wordを実行でき、stack `[99,2,3,3,0,2,7,0x9000]`、SLOT `0x9000`、
  ANSWER body `0x9004`、保存値7、data HERE `0x9008`が両言語で一致した。
- 次はCODE／DICTIONARY recordを一つのmanifestへ統合し、不正recordをimage変更前に拒否する
  validator／transactional linkerを設計する。詳細は`CODE_RELOCATION_R0.md`に保存した。

## transactional relocation linkerの追記（2026-08-28）

- CODE 15件とDICTIONARY 53件を、format、version、Reference32-LE profileを持つ一つの
  manifestへ統合した。これは実行仕様R0でありpersistent file形式は未凍結である。
- linkerは三component、source／target base、全68 recordを先に検査し、全件成功後だけ
  private copyへpatchする。入力imageとmanifestは成功時にも失敗時にも変更しない。
- section／target、width、kind、offset、DICTIONARY cell整列、patch重複、pointer範囲、
  target領域重複、Reference32 overflowを検査する。
- version、section、width、offset、重複patch、範囲外pointer、target重複、overflow、空kindの
  9破損をPython/Ruby双方が変更前に拒否した。
- 完全image移動を手書きpatchから新linkerへ置き換え、移動後の全word実行結果が同一である
  ことを確認した。詳細は`RELOCATION_LINKER_R0.md`に保存した。
- 次はcomponent digestとallocator metadataを持つimage envelope候補により、別image用manifestの
  取り違えをpatch前に検出する。

## digest-bound image envelopeの追記（2026-08-28）

- CODE、DICTIONARY、DATAのbase、size、limit、SHA-256と、CODE-HERE、header HERE、
  data HERE、LATEST、manifest digestを一つの`identity_sha256`へ結び付けた。
- 同じ68 recordでもCODEが1 byte異なるimage、別image用envelope、allocator metadata改変、
  manifest record改変を最初のpatch前に拒否した。
- link後は各HEREを新baseと使用byte数から再計算し、LATESTをDICTIONARY差分だけ移動する。
  新component digestと新identityを持つenvelopeを生成し、移動後imageを正常実行した。
- Python/Rubyはsource identity
  `32ede0d9569201fc1cdba68baa976565eac837704b32e12f49d76c644b08e26b`まで一致した
  （当時のgenerationなしenvelope v1。現在のv2 identityは後節参照）。
- SHA-256はintegrity検査であり悪意ある改変への認証ではない。authentication schemeを明示的に
  `none`とし、認証必須policyでは未認証imageをfail-closedで拒否する入口を実装した。
- 現時点では署名済みschemeを実装していない。次は鍵方式を選ぶ前にthreat modelを整理する。
  詳細は`IMAGE_ENVELOPE_R0.md`に保存した。

## threat model R0の追記（2026-08-28）

- 守る資産、build hostからloader／runtime／Viewerまでの信頼境界、想定主体、入力経路を
  `THREAT_MODEL_R0.md`へ整理した。confidentialityと完全な物理攻撃対策はR0の保証外とした。
- 13脅威を列挙し、integrity、authenticity、availability、recoveryの現在状態と次対策を分けた。
- 実働監査ではcomponent破損、manifest改変、無限実行を拒否した。
- 攻撃者が改変imageへ新digestを付け直すT03はDevelopment Profileで受理され、古い正規imageへ
  戻すT05もgenerationがないため受理される。両者を未解決gapとして回帰試験へ固定した。
- authentication-required policyは未認証の改変再buildをfail-closedで拒否した。ただし実署名schemeは
  未実装であり、deployment可能という意味ではない。
- Development、Controlled Device、Distributed Imageの三profile候補を置いたが方式は未凍結である。
- 次は一台の実験機、複数controlled device、公開配布の三環境についてHMACと公開鍵signatureを比較する。

## HMAC-SHA256／Ed25519比較の追記（2026-08-28）

- 同一の実image identityをdomain-separated 57-byte messageにし、HMAC-SHA256 tagとEd25519
  signatureをPython／Rubyで生成した。tag、public key、signatureはbyte単位で一致した。
- 両方式とも正しいkeyだけを受理し、改変identityとwrong keyを拒否した。
- HMACは32-byte tagで実装が小さい一方、検証実機が秘密鍵を持つため、device key抽出後は
  攻撃者が改変imageへ有効tagを作れることを実働確認した。
- Ed25519は32-byte公開鍵と64-byte signatureを使い、実機の公開鍵だけでは署名を作れない。
- Developmentは`none`、Controlled Deviceはper-device HMACをoptional候補、Distributed Imageは
  Ed25519を第一候補とした。fleet共通HMAC keyは推奨しない。
- host測定はHMAC検証が数microsecond、Ed25519が数十〜百数十microsecondだったが、target性能の
  推定には使わない。ROM／RAM／時間はtarget portで別測定する。
- generationがないまま署名すると古い正規署名imageを拒否できないため、認証block統合より先に
  anti-rollback generationをidentityへ追加する。詳細は`AUTH_COMPARISON_R0.md`に保存した。

## anti-rollback generationの追記（2026-08-28）

- image envelopeをv2へ進め、unsigned 64-bit `generation`を必須化してidentityへ含めた。負数、
  `2^64`以上、bool相当を拒否し、wrapは許さない。
- loader側の最低受入generationをimage外に持つ`TrustedGeneration` host modelをPython／Rubyへ
  実装した。同値は再起動・同版再導入のため受理し、小さい値だけをrollbackとして拒否する。
- generation 6、7、8のidentityへ公開fixture鍵でEd25519署名し、全署名が正しい状態でも、最低値7が
  generation 6を拒否することを実働確認した。
- generation 8のpreflight後に導入失敗を模擬してもtrusted値は7のままであり、成功commit後だけ8へ
  進む。その後generation 7は拒否される。relocationでもgeneration 8を保持した。
- Python／Rubyは三identity、三signature、拒否結果、commit状態まで一致した。この時点では
  Flash／EEPROMへの永続化、電源断atomicity、A/B slotは未実装だった（後節でhost modelを追加）。
- 通常更新にdowngrade bypassを置かず、factory recoveryは別trust anchor・別認証経路として扱う。
  詳細は`ANTI_ROLLBACK_R0.md`に保存した。

## 後続資料として保存する依頼

- 一連のsecurity実装が落ち着いた段階で、「今回の開発での外部からの攻撃に対する防御についての
  解説」を独立資料にまとめる。
- digest、署名、鍵、generation、transactional install、recovery、Monitor／Viewer／AI境界を、
  攻撃経路、検出点、拒否動作、残る限界の順で、初心者にも実働例を追える形にする。
- 実装途中の防御を完成済みと誤認させないため、現時点では最終資料を凍結せず、この作成予定だけを
  checkpointへ保存する。

## Ed25519 signed image envelopeの追記（2026-08-28）

- authentication schemeと`key_id`をidentityへ結び付けるため、image envelopeをv3へ進めた。
  `signature_hex`自身は循環を避けてidentity外に置き、そのidentityへEd25519署名する。
- trusted public-key storeはimage外からloaderへ渡す。image内の公開鍵をそのまま信頼する方式には
  せず、unknown key ID、wrong public key、trust store欠落をfail-closedで拒否した。
- component改変、signature改変、短いsignature、key ID改変、unknown scheme、余分field、未署名
  secure mode、正規署名済みrollbackなど12ケースをPython／Ruby双方で拒否した。
- 署名後のrelocationはidentityを変えるため、実機側で署名を失ったimageへ変換する操作を拒否する。
  build hostで最終配置へlinkしてから再署名したtarget imageは正常に検証できた。
- 公開fixtureでsigned identity
  `e25c1da9f6f623b9d88d0e9822dbe22bc29f6f2356be0c4a6995c356aab6cab8`と64-byte signatureが
  Python／Rubyで一致した（当時のroleなしv3。現在のv4 identityは後節参照）。詳細は
  `SIGNED_IMAGE_R0.md`に保存した。

## A/B transactional installの追記（2026-08-28）

- active pointerを単独の真実にせず、A/B両slotを起動時に走査し、正規署名、minimum generation、
  complete markerを満たす候補からgenerationとsequenceが最大のimageを選ぶhost modelを実装した。
- candidateを事前検証してからinactive slotを消去し、CODE、DICTIONARY、DATA、envelope、staged検証、
  complete-marker本文、marker sealの順で書く。seal前のslotは起動候補にならない。
- 8 install地点すべてへ電源断を注入した。marker seal前の7地点では旧A／generation 7を起動し、
  seal後だけ新B／generation 8を起動した。
- minimum generationは二つのjournal recordへ交互に書き、古いvalid recordを残したまま新record本文を
  書き、checksum seal後だけ新値を採用する。3地点の電源断で7／7／8となることを確認した。
- 新imageのboot成功後だけgeneration 8をcommitする。boot失敗、candidate破損、torn marker、
  rollback投入ではA／generation 7へ戻った。journal最新record破損時も旧record 7を読めた。
- generation 8 commit後に唯一のgeneration 8 imageが破損すると、旧generation 7はanti-rollbackで
  起動できずrecoveryが必要になる。この限界を成功扱いせず回帰試験へ固定した。
- Python／Rubyは全power-loss行列とrecovery境界まで一致した。詳細は
  `TRANSACTIONAL_INSTALL_R0.md`に保存した。

## 独立recovery pathの追記（2026-08-28）

- `image_role`を署名identityへ追加し、normal／recoveryを別用途として固定するimage envelope v4へ
  進めた。roleだけの書換えはidentity／署名不一致になる。
- recovery imageは通常更新鍵とは別のEd25519 key、通常minimumとは別のrecovery generation journalを
  使用する。normal minimum 8でもrecovery generation 1を独立domainとして起動できた。
- normal A/Bがどちらもpolicyを満たさない時だけprotected slot Rを検証してrecovery modeへ入る。
  正常normal imageがある時のrepair API呼出しは拒否した。
- recovery modeからnormal generation 8の正規署名imageをBへtransactional repairした。8書込み地点の
  seal前7地点で電源断するとrecoveryに留まり、seal後だけnormal generation 8へ戻った。
- normal 7によるrepair、normal imageのrecovery利用、recovery imageのnormal利用、role改変を拒否した。
  recovery image自身も破損した場合はtotal boot failureとして明示した。
- Python／Rubyでv4 recovery identity、全power-loss状態、role拒否結果が一致した。詳細は
  `RECOVERY_PATH_R0.md`に保存した。

## trust bundle・key rotation・recovery更新の追記（2026-08-28）

- normal／recovery image鍵を列挙するtrust bundle v1を実装した。各entryはkey ID、role、32-byte公開鍵、
  active／revoked状態を持ち、bundle全体を別のoffline root Ed25519鍵で署名する。
- bundle epochをrollback防止値とし、bundle A/B slotのchecksum sealとminimum epochの二重journalを
  分けた。bundle書込み3地点、epoch commit 3地点への電源断で旧／新可視状態を確認した。
- epoch 2ではnormal・recoveryとも新旧鍵をactiveにするoverlap期間を作った。normal新鍵imageを検証後、
  epoch 3で旧normal鍵をrevokedにし、旧署名imageを拒否、新署名imageを受理した。
- recoveryはoverlap期間中に旧鍵generation 1から新鍵generation 2へA/B更新した。8地点の電源断で
  seal前は旧A、seal後だけ新Bとなり、boot成功後にrecovery minimumを2へ進めた。
- その後epoch 4で旧recovery鍵をrevokedにしても新Bは起動した。一方、recovery更新前に旧鍵を失効
  すると旧Aが起動不能になる危険な順序も実働で確認し、回帰試験へ固定した。
- 偽root署名bundle、署名後のkey status改変、古いepoch bundleを拒否した。Python／Rubyはroot key、
  四bundle署名、全power-loss状態、rotation結果まで一致した。詳細は`TRUST_ROTATION_R0.md`に保存した。

## pinned root rotationの追記（2026-08-28）

- ROM等に固定するbootstrap rootから、hash-linked root policy chainを検証するhost modelを実装した。
  policyはepoch、直前policy digest、root ID／公開鍵／active・retired状態、署名集合を持つ。
- transition署名者を「直前active rootsと新active rootsの和集合」とした。新root追加と旧root退役には
  old／new双方の署名を要求し、退役確定後の次policyからnew root単独署名へ移行した。
- 既存root IDの公開鍵交換とentry削除を禁止し、retired rootは再有効化できない。bootstrap policyは
  image外にpinした最初のroot集合と完全一致しなければならない。
- root policy chain全体をA/B stateへ書き、checksum seal後だけ新chainを可視化した。minimum root epochは
  別の二record journalへcommitし、各3地点の電源断で旧／新状態を実働確認した。
- overlap中にold／new root署名trust bundleを両方検証し、new root bundle導入後にold rootをretiredへ
  進めた。逆順ではold root署名bundleが使えなくなることを危険例として回帰試験へ固定した。
- 新root署名欠落、署名改変、chain link改変、root公開鍵交換、retired再有効化、rollback、commit済み
  chain破損を拒否した。Python／Rubyは4 policyのdigest／全署名／電源断／拒否結果まで一致した。
- cross-signは侵害済みold rootを救済する判定ではない。threshold／緊急root、chain圧縮、persistent
  parser、実媒体試験は未実装である。詳細は`ROOT_ROTATION_R0.md`に保存した。

## bounded persistent packageの追記（2026-08-28）

- external fileの共通container v1を実装した。32-byte固定header、kindごとの固定section directory、
  contiguous payload、32-byte SHA-256 checksumからなり、整数はlittle-endianとした。
- image、trust bundle、root policy chainの三kindを定義した。R0 host上限はfile 1 MiB、8 section、
  payload 768 KiB、binary section 512 KiB、metadata 256 KiBで、target profileごとに縮小できる。
- file APIは上限+1 byteだけを読み、oversizeならheader／JSON解析前に拒否する。declared length、実file長、
  section offset／length／順番を固定幅整数の範囲内で照合し、gap、overlap、duplicateを許さない。
- metadataをcanonical UTF-8 JSONにした。duplicate key、float、NUL、非canonical表現を拒否し、depth 32、
  string 4096文字、integer 20桁、20,000 nodeの上限を置いた。
- root chain package epoch 2、new-root署名trust package epoch 2、generation 7 signed image packageを順に
  再読込・検証した。imageは実一時fileへ書いてbounded APIで読み、FORTH word列を実行して期待stack
  `[99, 2, 3, 3, 0, 2, 7, 32768]`を得た。
- 途中切断、trailing data、checksum、長さ／count bomb、unknown version／kind、duplicate／overlap、
  malformed JSON、oversize fileなど15入力を拒否した。
- CODE改変後にcontainer checksumを攻撃者が付け直す例では構造parserは通過したが、image digest／
  Ed25519署名層が拒否した。checksumをauthentication扱いしない境界を回帰試験へ固定した。
- 正規署名envelopeへ署名対象外の未知fieldを追加する入力も拒否するため、image envelope、component
  descriptor、allocator、manifest、relocation recordのfield集合を完全一致検査へ強化した。
- Python／Rubyはimage 8321 byte、trust 538 byte、root chain 1364 byteの全byteとSHA-256、実行結果、
  15拒否結果まで一致した。詳細は`PERSISTENT_PACKAGE_R0.md`に保存した。

## integrated loader state machineの追記（2026-08-28）

- bounded package parser、cross-signed root policy、root-signed trust bundle、normal／recovery A/B imageを
  一つのloaderへ結合した。対象は新規FORTHだけで、MSX0-FORTHには変更を加えていない。
- loader phaseは外部fileやRAM pointerから受け取らず、各domainのchecksum seal済みvisible値と
  commit済みminimum値から`stable`または`*-awaiting-commit`を導出する。同時に複数domainがpendingなら
  fail-closedとした。
- root候補を書き込む前に現在のtrust bundleが候補root集合で検証可能か確認し、trust候補を書き込む前に
  現在のnormal／recovery両imageが候補鍵集合で検証可能か確認するordering guardを実装した。
- root overlap、trust overlap、normal／recovery generation 2、旧image鍵失効、旧root退役の完全sequenceを
  実packageで実行し、root/trust epoch 3、normal/recovery generation 2のstable状態へ到達した。
- premature root retirement、premature key revocation、root overlap前のnew-root bundle、role confusion、
  image rollback、切断package、root history差替えをslot書込み前に拒否した。
- candidate boot失敗では旧normalへ戻り、normal全損時には独立recoveryへ移ることを確認した。
- root stage／minimum commitの各三地点へ電源断を注入し、seal前は旧stable、root-state seal後はpending、
  journal seal後だけ新stableとなった。再開phaseは永続状態だけから再発見できる。
- loader用Python 5 test、Ruby test、cross-language完全結果照合を追加した。全回帰はPython 202件、
  Ruby 32 suite、Python／Ruby 36比較がすべて成功した。詳細は`LOADER_STATE_MACHINE_R0.md`に保存した。
- 次はloader capability分離、watchdog／health check、外部path policy、実Flash／EEPROM profileである。

## loader capability boundaryの追記（2026-08-28）

- 通常FORTH runtime、authenticated Monitor候補、recovery、physical provisionerの4 profileを定義した。
  runtimeは観察のみ、Monitorはnormal更新のみ、recoveryはrecovery mode中のnormal修復のみ、provisionerは
  normal／recovery／trust／rootを操作できる。
- profile文字列を権限として受け取らず、trusted hostが発行・registry登録したsession objectだけを受理する
  capability modelをPython／Rubyへ実装した。未発行、profile文字列、revoke済みsessionを拒否した。
- stage開始session、domain、image slotをownerとして結び付け、別Monitorのcommit横取り、異なるslotのcommit、
  ownerが残る間の別stageを拒否した。
- ownerはvolatileとし、再起動後は永続phaseを対象domainの権限が明示的にadoptする。runtimeによる引継ぎを
  拒否し、Monitorによるnormal pendingの引継ぎとcommitを確認した。
- normal全損時に通常installerがactive slotを選べない問題を実働で発見した。integrated loaderへ専用の
  `stage_normal_repair_package`を追加し、recovery capabilityから空slot Bへnew generationを修復した。
- 15の無許可／偽造／横取り操作を拒否し、normal generation 2へのrecovery修復、再起動引継ぎ、最終stableを
  Python／Rubyで一致確認した。詳細は`CAPABILITY_BOUNDARY_R0.md`に保存した。
- 全回帰はPython 207件、Ruby 33 suite、Python／Ruby 37比較がすべて成功した。
- host object capabilityは同process内の強いsandboxではない。次はMonitor control plane、safe point、
  budget／watchdogを実働化し、その後targetの物理的な権限分離を選ぶ。

## MIN0 CORE FORTHへの正式改名（2026-08-28）

- プロジェクト正式表示名を`MIN0 CORE FORTH`（ミノ・コア・フォース）と決定した。`MIN0`末尾は英字Oで
  なく数字0であり、開発者が以前から使用していたニックネームと、ゼロから育つ共通母体を表す。
- README最上部へGitHub IMPORTANT形式の「まずは必ず最初にお読みください！」を追加し、公開目的、教育・
  実験用という位置付け、fixture鍵、Forkと公式版の区別を`FIRST_READ.md`へまとめた。
- canonical表記、repository slug、source namespace、machine ID、暗号domain separator、改名しないcontainer
  magicを`NAMING_R0.md`へ定めた。`FCPKG0`は一般package形式のmagicとして維持した。
- 人向け正式表示名を`MIN0 CORE FORTH`、Python／file prefixを`min0_core_forth`、Ruby namespaceを
  `Min0CoreForth`、machine IDを`min0-core-forth`へ変更した。34 module file、190 text fileを移行した。
- cryptographic domain separatorも`MIN0-CORE-FORTH-*`へ変更した。0.1前の実験vector互換性は維持せず、
  image／trust／root signature、identity、persistent package hashを新名称で再生成した。
- Guided Viewerを実traceから再生成し、画面表示とtrace formatを`MIN0 CORE FORTH`／
  `min0-core-forth-trace/0.1`へ統一した。
- local workspace folderも`work/min0-core-forth`へ改名し、旧開発名を含むpathへの依存がないことを
  新しいfolderからの回帰試験で確認する。
- 全回帰はPython 207件、Ruby 33 suite、Python／Ruby 37比較がすべて成功した。MSX0-FORTHには一切変更を
  加えていない。
- 1st release前の未決定事項はsource license、公式repository URL、artifact構成、release checksum／署名、
  Forth標準word set対応表である。

## Monitor safe pointと実行watchdog（2026-08-28）

- bytecode VMの外側へ独立したMonitor control planeを追加した。pause要求は命令途中ではなく、一命令が完全に
  終了して次opcodeをfetchする前のsafe pointだけで受理する。
- 停止理由を`pause-requested`、`budget-exhausted`、`watchdog-expired`、`halted`に分け、IPとDATA／RETURN／
  LOOP stackを維持したまま再開できるようにした。
- budgetは一回のsliceで許可する決定的な命令数とした。watchdogはhost health checkの接続点とし、作動後は
  Monitorが明示的にlatchを解除するまで再開を拒否する。
- observerとmonitorの非直列化sessionを分離した。observerはcopyされた状態の観察だけが可能で、pause、
  run／resume、watchdog解除はできない。profile文字列、偽造、未発行、revoke済みsessionを拒否した。
- 6命令の実例を`ADD`後の要求pause、budget 1、watchdog、解除後HALTへ分割し、stack `[3]`を保ったまま
  累計6命令で完了した。Python／Rubyの結果は完全一致した。詳細は`MONITOR_CONTROL_R0.md`に保存した。
- 全回帰はPython 213件、Ruby 34 suite、Python／Ruby 38比較、Viewer 8件がすべて成功した。

## pause-time観察と認証済みDEFER切替え（2026-08-28）

- dictionary kind 7をDEFER entryとして追加し、固定8-byte XTのpayloadを現在のcolon-code targetとした。
  未割当て0、非実行address、colon以外のtargetをfail-closedとした。
- VM opcode `ICALL`を追加した。compiled callerは現在targetを通常`CALL`へ固定せず、`ICALL XT+4`で呼出し時に
  slotを読む。通常のcompiled `CALL`と同名word再定義の意味は変更していない。
- observerへIP、三stack、辞書entry、監査記録のcopyを公開した。observerはpause、resume、DEFER切替えを
  実行できない。
- pause時にIP、step、HALT、三stack、辞書HERE／data HERE／LATEST、live dictionary SHA-256をsealした。
  再開前に上限、実行address、辞書LINK、DEFER target、seal一致を検査し、API外のstack／辞書変更を拒否した。
- 認証済みMonitorの`switch_defer`は、acknowledged pause中だけ、旧target検証、単一cell更新、監査record、
  新sealの順で実行する。監査にはDEFER名、旧／新target、address、step、IPを記録した。
- 同じcompiled `APPLICATION`を二回呼び、一回目は旧targetでstack `[10]`、停止切替え後の二回目は新targetで
  `[10, 20]`となった。Python／Rubyのentry、audit、typed relocation、最終状態が完全一致した。
- source-level `DEFER`／`IS`／`ACTION-OF`と署名付き永続auditは次段階以降とした。詳細は
  `MONITOR_PATCH_R0.md`に保存した。
- 全回帰はPython 217件、Ruby 35 suite、Python／Ruby 39比較、Viewer 8件がすべて成功した。

## source-level DEFER／IS／ACTION-OF（2026-08-28）

- DEFER payloadをraw code addressではなく実際のdictionary XTへ精密化した。`ICALL`はslotからtarget XTを読み、
  kind 1とcode payloadを検証してから呼び出す。`ACTION-OF`も同じXTを返す。
- interpret-state source wordとして`DEFER name`、`' name`、`IS defer-name`、`ACTION-OF defer-name`をPython／
  Rubyへ追加した。未割当て実行、非colon target、compile-state使用を拒否した。
- build phaseでは`' INITIAL IS SERVICE`で初期化できる。Monitor接続時に辞書のDEFER mutation入口をopaque
  authorizationでlockし、以後の一般outer interpreterによる`IS`をcell更新前に拒否した。
- 認証済みcontrol sourceは厳密な`' target IS defer`の4-tokenだけをmutationへ変換する。observerは
  `ACTION-OF defer`だけをread-only照会でき、任意sourceをcontrol commandとして実行しない。
- compiled `USE-ACTION`を変更せず、旧targetで10、新targetへ`IS`後に20となり、`ACTION-OF`はそれぞれのXTと
  一致した。DEFER target XT relocationもdictionary型として扱った。詳細は`DEFER_SOURCE_R0.md`に保存した。
- 全回帰はPython 221件、Ruby 36 suite、Python／Ruby 40比較、Viewer 8件がすべて成功した。

## compiled DEFERのsafe／build profile分離（2026-08-29）

- source profileを既定`safe-runtime`と明示的`standard-build`へ分けた。safe-runtimeでは`[']`とcompiled
  `ACTION-OF`を許可し、compiled `IS`をcompile rollback付きで拒否する。
- `['] name`はdictionary XTの`LIT`、compiled `ACTION-OF defer`はslot addressの`LIT`と`FETCH`を生成し、
  `xt-literal`／`action-of-slot`というDICTIONARY型relocationを記録する。
- standard-build専用opcode `DSET`を追加した。VM permission、kind-7 destination、kind-1 target XT、実行可能code、
  書込み範囲を検査してから一cellだけを更新する。通常VMではopcode自体を拒否する。
- `: SWITCH ['] NEW-ACTION IS ACTION ;`によりstandard-buildでは結果が10から20へ変化した。同じwordをMonitor
  接続後に実行すると`DeferStoreDenied`となり、targetは変化しなかった。
- Monitor接続時にVM permissionを強制disableし、そのbitもresume invariant sealへ含めた。辞書authorization、
  VM opcode gate、resume invariantの三段でruntime mutationを防ぐ。詳細は`COMPILED_DEFER_R0.md`に保存した。
- 全回帰はPython 226件、Ruby 37 suite、Python／Ruby 41比較、Viewer 8件がすべて成功した。

## signed image execution profileとLoader事前拒否（2026-08-29）

- `reference32-le`というmachine image形式profileとは別に、署名対象の`execution_profile`をimage envelope
  v5へ追加した。値は`safe-runtime`または`standard-build`である。
- profile文字列をcallerへ任せず、relocation manifest内の`defer-store-slot`から必要profileをPython／Rubyの
  image builderが自動導出する。compiled `IS`を含むimageは必ず`standard-build`となる。
- `execution_profile`をcomponent／allocator／manifest digest、generation、roleと同じsigned identityへ結合した。
  profileだけをsafeへ書き換える改ざんと、profile申告とrelocation要件の不一致を拒否する。
- `TransactionalInstaller`と統合Loaderの既定policyを`safe-runtime`とした。standard-build imageはinactive slotの
  erase／writeより前に拒否し、明示的なstandard-build環境だけがsafe／build両imageを受理する。
- 最後の復旧経路へ構築時権限を持ち込まないため、recovery roleはbuild時・load時とも常にsafe-runtimeへ制限した。
- 実compiled `IS`を含む署名imageで、profile自動導出、pre-write拒否、slot無変更、standard-buildでのslot B導入、
  profile改ざん拒否、recovery拒否を実働確認した。詳細は`IMAGE_EXECUTION_PROFILES_R0.md`に保存した。
- envelope v5化に伴い、image identity、Ed25519署名、HMAC、persistent image packageの固定vectorをPython／Rubyで
  再生成した。persistent image packageは8356 byteとなった。
- 全回帰はPython 229件、Ruby 38 suite、Python／Ruby 41比較、Viewer 8件がすべて成功した。MSX0-FORTHには
  一切変更を加えていない。

## bytecode verifierとcapability二重照合（2026-08-29）

- CODE componentを先頭から「1-byte opcode＋必要時4-byte operand」として完全復号するPython／Ruby verifierを
  追加した。未知opcode、切断operand、CODE末尾の半端な命令をimage build／load時に拒否する。
- 命令先頭addressをboundary集合として作り、CALL、条件／無条件branch、loop target、およびDICTIONARY
  descriptorを含む全CODE向けrelocationがoperand途中を指さないことを検査する。
- opcodeごとにtyped relocationのtarget／kindを一対一照合する。実DSETと`defer-store-slot`の片側だけ、
  CALLと別kind、opcode byteや無関係operandへの偽relocationを拒否する。
- raw byte検索は採用しない。`LIT 0x25`のoperand中にあるDSETと同じbyteを命令と誤認せず、本物のDSETだけから
  `compiled-defer-store` capabilityを導出した。
- image execution profileはmanifest文字列検索ではなくverifier capabilityから導出するよう変更した。Loaderも
  pre-write時に同じverifierを再実行し、実CODE、typed relocation、signed profileの三者一致を要求する。
- DSET記録欠落、偽記録、切断CALL、未知opcode、LIT operand途中へのbranch、辞書colon entryのoperand途中を
  Python／Rubyで拒否した。従来デモの末尾EXIT 1-bit反転が切断CALLを作っていたことも実際に検出し、
  構文上有効なNOP変更へ修正した。
- 詳細は`BYTECODE_VERIFIER_R0.md`に保存した。次候補はentry pointからのcontrol-flow graph、到達可能性、
  stack effect静的検査の負担と効果の比較である。
- 全回帰はPython 232件、Ruby 39 suite、Python／Ruby 42比較、Viewer 8件がすべて成功した。MSX0-FORTHには
  一切変更を加えていない。

## 一方向CODE sealと実行時命令境界（2026-08-29）

- 設計原則を「Forthの自由さを失わせず、危険な力を使うときだけ本人がはっきり自覚できる設計」「通常利用者に
  安全な道と、理解した開発者が明示的に開く道を分ける」として`SEALED_EXECUTION_R0.md`へ固定した。
- `RegionMemory`へ一方向`seal_executable_region`を追加した。検証後のCODEはbuild `rwx`からruntime `rx`へ
  移り、`programmable=false`、`sealed=true`となる。通常write、host program、clear、再sealを拒否する。
- bytecode verifierのinstruction boundary一覧をVMへ導入した。各stepのIP、resume、CALL、branch／loop、EXIT、
  ICALL、DSET targetがverified boundaryまたは明示extra trampolineに一致しなければ実行しない。
- 値`0x25`自体は禁止しない。`LIT 0x25`、DATA変数への`!`／`@`、正常DEFERは封印後も37、123、7を返した。
  一方、実source `0x25 0x1000 !`はCODE write permissionで拒否し、CODE byte不変を確認した。
- DICTIONARYがまだ`rw`である限界を実験した。colon payloadをLIT operand途中へ`!`で変更すること自体は起きるが、
  その後のICALLはruntime boundaryで拒否した。DATA実行、operand途中resume、FlatMemory sealも拒否した。
- R0 buildは既存interactive compilerのためまだ`rwx`である。次はstaging `rw,nx`からruntime `rx`への完全W^X、
  固定primitive dispatch、DICTIONARY structural write capabilityを設計する。
- 全回帰はPython 235件、Ruby 40 suite、Python／Ruby 43比較、Viewer 8件がすべて成功した。MSX0-FORTHには
  一切変更を加えていない。

## 固定primitive dispatchと完全W^X公開経路（2026-08-29）

- 設計原則の二文を`FIRST_READ.md`の名称説明直後へ配置し、初めて触れる利用者が安全機構の技術詳細より先に
  プロジェクトの意図を読めるようにした。
- interpret-state primitiveの実行時opcode書換えを廃止した。operandなしprimitiveごとに`opcode, HALT`の固定
  2-byte slotを起動時に一度だけ作り、そのaddressを選択して実行する。slot内容を封印直前に照合し、opcodeと
  HALTの双方をverified extra entryへ登録する。
- CODE封印後も実outer interpreterで`2 3 +`が5になることをPython／Rubyで確認した。従来のCODE write、
  operand途中実行、改変ICALL等の拒否は維持した。
- `min0_core_forth_publish.py/.rb`へsafe-runtime publisherを追加した。imageをまず別storageの`rw,nx` stagingへ
  配置して再検証し、別の`rx` runtime CODEへloader権限でprogramして直ちに一方向sealする。runtime CODEが
  通常write可能になる瞬間はない。
- 公開後にstaging CODEを変更してもruntime bytesと実行結果が変わらないこと、staging fetch、runtime write、
  seal後program、事前改変imageを拒否することを実働確認した。詳細は`W_X_PUBLICATION_R0.md`に保存した。
- 次候補はDICTIONARY structural writeを、通常DATA更新、allocator、compiler、Monitor DEFER変更などの能力へ
  分解することである。
- 全回帰はPython 238件（Viewer 8件を含む）、Ruby 41 suite、Python／Ruby 45比較がすべて成功した。
  MSX0-FORTHには一切変更を加えていない。

## runtime DICTIONARY capability分離（2026-08-29）

- `RegionMemory`へregion単位のwrite protectionを追加した。保護後は通常writeだけでなくhost-side `program`と
  全memory clearも拒否し、opaque identity capabilityを持つ短時間scope内だけwriteを許可する。
- safe-runtime publisherはimage loadと検証の完了後に`seal_runtime_structure`を呼ぶ。header、XT、flag、DOES
  descriptor、constructor plan、allocator、image reload／rollbackを一方向凍結する。development buildは凍結せず、
  従来の対話的な定義と再定義を維持する。
- runtime seal直後は一般sourceの`IS`も拒否する。Monitor接続後は既存のsession authorization、pause、型検査、
  resume seal、auditに加え、dictionary内部の物理write capabilityを短時間だけ使用してDEFER payloadを更新する。
- 実imageでDATAの`123 CELL ! CELL @`が123を返す一方、header／DEFER slotへの生`!`、`: INTRUDER`、`1 ,`、
  一般`IS`、loader program、偽capability、observer切替えを拒否した。拒否群の後もDICTIONARY全体は不変だった。
- 認証済みMonitorによる`ACTION`の切替え後は`USE`が9を返した。前後byte差分が対象DEFER payloadの4-byte範囲内
  だけであることもPython／Rubyで確認した。詳細は`DICTIONARY_CAPABILITY_R0.md`に保存した。
- 全回帰はPython 241件（Viewer 8件を含む）、Ruby 42 suite、Python／Ruby 46比較がすべて成功した。
  MSX0-FORTHには一切変更を加えていない。

## 初心者向けstack Viewerと実機への橋渡し（2026-08-29）

- Python／Ruby outer interpreterへ解釈状態専用の`.`を追加した。VM opcodeは増やさず、DATA stack最上段を
  signed decimal文字列としてhost output列へ記録する。`2 3 4 * + .`は14、`2 3 * 4 + .`は10、
  `0 1 - .`は-1を出力し、underflow時は出力を変更しない。
- Viewerへ上記二例の実測トレースを追加した。初心者例はprimitive内部入口を重複表示せず、ソース上の
  6ワードだけを`実行前 → 実行後`で追う。VALUE／ANSWER例のstep-in表示は維持した。
- Viewerに端末出力欄と「例題FORTHソース（コピー・編集できます）」を追加した。編集文字列はViewerで
  実行せず、明示的なコピーまたは`.fth`保存だけを許す。実画面で14／10、編集、clipboard copy、
  実測結果が編集で変わらないことを確認した。
- 文字列表示は未実装で、`EMIT`、`CR`、`TYPE`、`."`を1st release候補へ記録した。文字コード、保存領域、
  Flash／EEPROMからの読出しを決めてから凍結する。
- 全回帰はPython 246件（Viewer 10件を含む）、Ruby 42 suite、Python／Ruby 46比較がすべて成功した。
- MSX0-FORTHには一切変更を加えていない。

## 文字出力EMIT／CRとhost端末境界（2026-08-30）

- Python／Ruby outer interpreterへ解釈状態専用の`EMIT ( x -- )`と`CR ( -- )`を追加した。
  VM opcodeは増やさず、`EMIT`はセル下位8bit、`CR`は論理LFをhost output collectorへ記録する。
- `65 EMIT 66 EMIT CR`が正確なAB＋LFのstreamとなり、`0x141 EMIT`が`A`、
  `0x1FF EMIT`がU+00FFになることを両言語で確認した。underflowは出力を変更しない。
- Windows CP932端末ではU+00FFを診断表示できないことを実際に検出した。cross-language runnerを
  UTF-8入力・ASCII escape診断へ変更し、host localeに依存せず比較できるようにした。
- 任意byteにはESC等も含まれるため、coreは自動的に実terminalへprintしない。raw serial、escaped教材表示、
  restricted protocolの選択を将来のtarget adapterへ明示的に委ねる。
- 次の`TYPE`は、読み出し範囲全体を先に検証し、fault時にstackとoutputを一切変更しない仕様とする。
  quoted stringの`S-quote`／`dot-quote`はparser、配置領域、relocation、Flash／EEPROM読出しを決めてから進める。
- 詳細は`TERMINAL_OUTPUT_V0_1.md`へ保存した。全回帰はPython 250件（Viewer 11件を含む）、
  Ruby 42 suite、Python／Ruby 46比較がすべて成功した。MSX0-FORTHには一切変更を加えていない。

## 範囲検証付き文字列出力TYPE（2026-08-30）

- Python／Ruby outer interpreterへ解釈状態専用の`TYPE ( c-addr u -- )`を追加した。VM opcodeは増やさず、
  指定byte列をhost output collectorへ一つの順序付きfragmentとして記録する。
- 非0長では、指定範囲全体のread permissionとregion境界を出力・stack変更より先に検証する。範囲外、
  permission違反、region跨ぎでは部分出力を行わず、二つのstack引数と既存outputを完全に保存する。
- 0長はaddressをdereferenceせず、二引数だけを消費する。読み取り専用のpreloaded Flash／EEPROM相当regionから
  `FORTH`を表示できることも両言語で確認した。byteからhost文字への写像は`EMIT`と同じU+0000〜U+00FFである。
- Viewer traceへ`emit-string` actionを追加した。利用者には、`TYPE`が指定範囲全体を検査してから一度だけ
  端末へ送ったことを1ワードの出来事として説明する。観測文字列を命令やHTMLとして扱わない原則は維持した。
- `character_demo.py/.rb`と相互比較に`TEXT 5 TYPE`を追加し、両実装のstack、exact output、辞書image、code、
  step数が一致した。詳細は`TERMINAL_OUTPUT_V0_1.md`へ保存した。
- 全回帰はPython 256件（Viewer 12件を含む）、Ruby 42 suite、Python／Ruby 46比較がすべて成功した。
  MSX0-FORTHには一切変更を加えていない。

## 引用文字列S-quote／dot-quote（2026-08-30）

- Python／Ruby tokenizerを引用対応へ拡張した。通常wordは従来どおりcase-insensitiveだが、`S"`／`."`内では
  大文字小文字、追加空白、backslashをそのまま保存する。backslash commentは引用外だけで働く。
- 解釈状態`S" ( -- c-addr u )`はU+0000〜U+00FFを1文字1byteとしてdictionary DATAへ保存する。
  stack 2セル、全書込み範囲、allocator容量を変更前に検査し、成功後だけaddressとlengthを積む。
- 解釈状態`." ( -- )`は同じbyte制約を検査してからhost outputへ一つのfragmentを追加し、DATAを消費しない。
  `S" Hello World" TYPE CR ." Done"`のexact streamが両言語で一致した。
- 未終端quoteはtokenize時、U+00FF超の文字は実行前、容量不足とstack overflowはallocation前に拒否する。
  いずれもstack、output、data HEREを変更しない。入力全体を実行前にtokenizeするため、未終端quoteより前に
  同じ入力へ書かれた`65 EMIT`も実行されない。
- 現在の`S"`はtransient bufferではなくdevelopment imageのDATAを永続的に消費する。sealed safe-runtimeでは
  新規allocationを拒否するが、image化済みbyte列はread-only Flash／EEPROM相当regionから`TYPE`で読める。
- v0.1はsame-line quote、埋込みdouble quoteのescapeなし、1byte文字だけである。日本語文字、compiled `S"`／`."`、
  immutable image sectionへの配置、typed relocation、target output serviceは明示的に次段階へ残した。
- Viewer traceへ`push-string-literal`と`emit-string-literal`を追加し、引用内容自体を命令やHTMLとして扱わず、
  word単位で保存byte数と出力byte数を説明する。詳細は`STRING_LITERALS_V0_1.md`へ保存した。
- 全回帰はPython 266件（Viewer 13件を含む）、Ruby 43 suite、Python／Ruby 46比較がすべて成功した。
  MSX0-FORTHには一切変更を加えていない。

## compiled S-quote relocationとread-only DATA（2026-08-30）

- Python／Ruby interactive compilerでcolon定義内の`S"`を実装した。非空文字列をimage DATAへ置き、CODEには
  `LIT relocated-address`と`LIT byte-length`を生成する。address cellは`string-address`／`target=data`の
  typed relocation recordとしてmanifestへ記録する。
- `: MESSAGE S" Compiled" ; MESSAGE`がaddressと8を積み、続くinterpret-state `TYPE`が`Compiled`を表示した。
  複数文字列と空文字列も動作し、空文字列はDATA offset zero＋length zeroとしてallocationなしで表現する。
- 文字列配置後に未知word、compiled `."`、U+00FF超文字で失敗させ、CODE、header、DATA bytes、data HERE、
  source mapping、relocation manifestが定義開始前へ戻ることを両言語で確認した。
- 専用relocation実験で文字列addressを`0x8000`から`0x9000`へlinkした。移動先DATAを新しい一方向
  `seal_read_only_region`で`r`へ封印後も`TYPE`は`Relocated`を表示した。通常write、host program、memory clearは
  すべて拒否され、Python／Rubyのaddress、bytes、permission、拒否matrixが一致した。
- compiled `."`は端末専用VM opcodeではなく、verified generic `SERVICE <u32 id>`で実現する方針を選んだ。
  trusted targetがimmutable allowlistを所有し、後続実装ではsigned CODEをverifierが復号して必要IDを導出する。
  image dataやMonitorからcallback登録・差替えはできない。詳細は`OUTPUT_SERVICE_BOUNDARY_R0.md`へ保存した。
- 全回帰はPython 272件（Viewer 14件を含む）、Ruby 44 suite、Python／Ruby 47比較がすべて成功した。
  MSX0-FORTHには一切変更を加えていない。

## verified SERVICE境界とcompiled dot-quote（2026-08-30）

- Python／Ruby VMへgeneric `SERVICE <u32 id>`（opcode `0x26`）を追加した。IDはaddressではなく非0の数値で、
  relocationを持たない。R0の`terminal-type-v0.1`をID 1へ割り当てた。
- trusted targetだけが実行policy seal前にhandlerを登録できる。同一ID、無効ID、seal後の追加／差替えを拒否する。
  verifierが実CODEから必要ID集合を導出し、VM sealは全IDの登録を確認してからexact allowlistとregistryを凍結する。
  必要serviceがなければCODE permissionを変更せずに失敗する。
- interactive compilerでcolon定義内の`."`を実装した。文字列をDATAへ配置し、`LIT string-address`、
  `LIT byte-length`、`SERVICE 1`を生成する。`: HELLO ." Hello" ;`を入れ子のcallerから実行し、CODE=`rx`、
  DATA=`r`の封印後にexact stream `Hello Service`を出力した。
- terminal handlerは既存`TYPE`と同じ`( c-addr u -- )`、全range事前検証、0長非dereference、失敗時stack／既存output
  保存を使う。これはtrusted host codeでありVM自体がhandler内部をsandboxするわけではないため、将来serviceを
  増やす際は個別contractとthreat reviewが必要であることも仕様へ明記した。
- verifierはSERVICEの切断operand、ID 0、偽relocation、operand途中branchを拒否する。Python／Rubyで未登録実行、
  重複登録、必要ID欠落、seal後登録、文字列range fault、0長、definition rollback、Viewer traceを確認した。
- `service_output_demo.py/.rb`と`cross_service_output_check.py`を追加した。全回帰はPython 279件（Viewer 15件を含む）、
  Ruby 45 suite、Python／Ruby 48比較がすべて成功した。MSX0-FORTHには一切変更を加えていない。
- offline Viewerへ`: GREET ." Hello from compiled Forth" ; GREET`の実測シナリオを追加し、compile時の
  DATA配置／SERVICE生成説明と、実行時の端末出力を1ワードずつ確認できるようにした。

## 1st release準備とfail-closed配布入口（2026-08-30）

- candidate identityを`0.1.0-rc.1`として`VERSION`へ記録し、`QUICKSTART.md`、release notes、known limitations、
  `SECURITY.md`、三段階checklistを追加した。正式licenseだけは利用者判断が必要なため未選択である。
- Python／Ruby双方へ利用者用`min0_forth` launcherを追加した。対話REPL、通常file実行、`-z FILE`を備え、quiet
  modeはbanner／prompt／最終stackを出さずFORTH自身の出力だけを返す。両実装でhelloのexact LF streamが一致した。
- release allowlistと監査／packagingを`release_tool.py`へ実装した。DOCX会話記録、`document_work/`、`__pycache__/`を
  除外し、個人path、内部参照、PEM private key、代表的token形、Viewer network APIをscanする。
- 公開fixture seed／HMAC keyの宣言名をすべて`TEST`付きへ統一し、各宣言fileへ「実運用禁止」を明記した。
- deterministic ZIPはsorted path、固定timestamp／permission／compressionで生成し、staged file manifestと
  `SHA256SUMS.txt`を作る。二回構築のhash一致をunit testで確認した。
- 暫定Gate Aはlicense欠落だけでfail-closed停止した。選択対象353 file、除外はcache、document work、会話DOCXで、
  secret／privacy／Viewer scanには他の問題がなかった。詳細は`RELEASE_AUDIT_0.1.md`へ保存した。
- 全回帰はPython 287件、Ruby 46 suite、Python／Ruby 49比較がすべて成功した。これはdevelopment treeの結果で、
  license決定後にclean stagingから再実行する。MSX0-FORTHには一切変更を加えていない。

## 主要資料

- `README.md`
- `FIRST_READ.md`
- `NAMING_R0.md`
- `MEMORY_PROFILE_V0_1.md`
- `DICTIONARY_V0_1.md`
- `DATA_DEFINITIONS_V0_1.md`
- `INTERACTIVE_COMPILER_V0_1.md`
- `COUNTED_LOOPS_V0_1.md`
- `SPLIT_DICTIONARY_V0_1.md`
- `DOES_DESCRIPTOR_V0_1.md`
- `SOURCE_DOES_V0_1.md`
- `CONSTRUCTOR_PLAN_V0_1.md`
- `IMAGE_ADDRESSING_R0.md`
- `CODE_RELOCATION_R0.md`
- `RELOCATION_LINKER_R0.md`
- `IMAGE_ENVELOPE_R0.md`
- `THREAT_MODEL_R0.md`
- `AUTH_COMPARISON_R0.md`
- `ANTI_ROLLBACK_R0.md`
- `SIGNED_IMAGE_R0.md`
- `TRANSACTIONAL_INSTALL_R0.md`
- `RECOVERY_PATH_R0.md`
- `TRUST_ROTATION_R0.md`
- `ROOT_ROTATION_R0.md`
- `PERSISTENT_PACKAGE_R0.md`
- `LOADER_STATE_MACHINE_R0.md`
- `CAPABILITY_BOUNDARY_R0.md`
- `MONITOR_CONTROL_R0.md`
- `MONITOR_PATCH_R0.md`
- `DEFER_SOURCE_R0.md`
- `COMPILED_DEFER_R0.md`
- `IMAGE_EXECUTION_PROFILES_R0.md`
- `BYTECODE_VERIFIER_R0.md`
- `SEALED_EXECUTION_R0.md`
- `W_X_PUBLICATION_R0.md`
- `DICTIONARY_CAPABILITY_R0.md`
- `TRACE_V0_1.md`
- `VIEWER_GUIDE_V0_1.md`
- `TERMINAL_OUTPUT_V0_1.md`
- `STRING_LITERALS_V0_1.md`
- `OUTPUT_SERVICE_BOUNDARY_R0.md`
- `RELEASE_SECURITY_AUDIT_PLAN.md`
