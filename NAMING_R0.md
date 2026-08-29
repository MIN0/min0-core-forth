# MIN0 CORE FORTH naming policy R0

## canonical names

| 用途 | canonical表記 |
| --- | --- |
| 正式表示名 | `MIN0 CORE FORTH` |
| 読み | ミノ・コア・フォース |
| repository slug候補 | `min0-core-forth` |
| Python／file prefix | `min0_core_forth` |
| Ruby namespace | `Min0CoreForth` |
| machine identifier prefix | `min0-core-forth` |
| release候補 | `MIN0 CORE FORTH 0.1` |

`MIN0`の末尾は数字のzeroである。通常text、検索語、file名、source identifierではASCIIの`0`を使う。
斜線付きzero等の装飾glyphはlogo内だけに限定し、別文字`Ø`をcanonical nameに使用しない。

## rename boundary before 0.1

- 人が読む正式表示名は`MIN0 CORE FORTH`へ統一する。
- Python moduleとfileの接頭辞は`min0_core_forth`へ統一する。
- Rubyのtop-level namespaceは`Min0CoreForth`へ統一する。
- trace、envelope、manifest等のpre-release machine IDは`min0-core-forth`接頭辞へ変更する。
- cryptographic domain separatorは`MIN0-CORE-FORTH-*`へ変更し、全fixture vectorを再生成・再監査する。
- persistent container magic `FCPKG0`はformatの一般識別子として維持する。
- released MSX0-FORTHの名称、source、artifactは変更しない。

0.1より前の実験formatとのbinary compatibilityは保証しない。0.1 release後の識別子変更は、version更新と
migration policyなしには行わない。
