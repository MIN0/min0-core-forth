# MIN0 CORE FORTH 0.1.3 互換性改善版リリースノート

[英語版はこちらです](RELEASE_NOTES_0.1.3.md)

候補版：`0.1.3-rc.1`

この版は、標準FORTHおよびCFから学んだsource記法と実行モデルを取り入れ、直接入力とcolon definitionの
不必要な動作差を減らします。VMを特定の端末や実機へ結び付けず、Python版とRuby版を同じ実行可能仕様として
維持します。

## コメント

- `( ... )`は次の`)`までを読み飛ばし、interpret／compile状態とDATA stackを変更しません。
- 括弧コメントは複数の物理行にまたがれます。未終了なら入力blockを実行せず、活動中の定義をrollbackします。
- `\`は物理行末までを読み飛ばす標準的な行commentとして正式に記録しました。

## 直接制御構造

- promptでも`IF ... ELSE ... THEN`、`BEGIN ... UNTIL`、`BEGIN ... AGAIN`、
  `BEGIN ... WHILE ... REPEAT`を使用できます。
- `DO`／`?DO`から`LOOP`／`+LOOP`までを収集し、定義内と同じindex結果を与えます。
- CFの`for ... next`を基礎に、MIN0では`u FOR ... NEXT`を0始まり・`u`回の構造として採用しました。
- 複数行入力、多重構造、`I`、`J`、`LEAVE`、0回実行、buffer／実行step／loop深度上限に対応します。
- 構造不一致、未終了、上限超過、実行errorでは、開始時のDATA stackとloop stackへrollbackします。

## compile可能な出力word

- `.`, `EMIT`, `CR`, `TYPE`を直接入力とcolon definitionの両方で使用できます。
- compile済み形式は、CPU非依存の`SERVICE`境界を使用します。

| word | service | stack effect |
| --- | ---: | --- |
| `TYPE` | 1 | `( c-addr u -- )` |
| `EMIT` | 2 | `( x -- )` |
| `.` | 3 | `( n -- )` |
| `CR` | 4 | `( -- )` |

直接入力とserviceは同じhandlerを使います。未登録serviceを必要とするimageはsealed実行前に拒否されます。

## 文書と互換性監査

- `WORDS`が示す起動時全65ワードを日英ポケットリファレンスで説明します。
- 全65ワードについてinterpretation／compilation／execution semanticsと必要contextを監査しました。
- `: ... ;`、`[']`、`CREATE ... DOES>`、`UNLOOP`などが単純な直接入力pairではない理由を学習ノートにまとめました。

## 維持する境界

- 新しいterminal専用VM opcodeは追加しません。
- 実MPU、FPGA、UARTなどのtarget実装は含みません。
- API、image format、service IDは引き続き実験中の0.1 interfaceです。
- 署名seedとHMAC鍵は公開試験fixtureであり、実配備には使用できません。
- `v0.1.0`～`v0.1.2`のtagと配布物は変更しません。

ローカルGate Aの結果は[0.1.3リリース監査](RELEASE_AUDIT_0.1.3_JP.md)へ記録します。
