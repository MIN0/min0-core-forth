# MIN0 CORE FORTH quick start

This release candidate provides equivalent Python and Ruby host launchers. Start in this directory.

## Requirements

- Python 3.12 and `cryptography` 50.0.0, or
- Ruby 4.0 with OpenSSL 3.x.

For Python, install the pinned dependency into your own virtual environment:

```powershell
python -m pip install -r requirements.txt
```

## Five-minute path

Open `viewer/value-trace.html` directly in a browser. It is self-contained and offline.

Then run the included output example:

```powershell
python min0_forth.py -z examples/hello.fth
ruby min0_forth.rb -z examples/hello.fth
```

Both commands print only:

```text
Hello from MIN0 CORE FORTH
```

`-z FILE` suppresses the banner, prompt, and final stack. Output produced by the FORTH program is still
written exactly. This is suitable for unattended host experiments. Errors go to standard error and
return a nonzero process status.

## Interactive path

```powershell
python min0_forth.py
```

or:

```powershell
ruby min0_forth.rb
```

Try:

```forth
WORDS
2 3 +
2 3 4 * + .
: SQUARE DUP * ;
WORDS
5 SQUARE .
: GREET ." Hello" ;
GREET CR
BYE
```

The first `WORDS` shows the vocabulary available at startup. After `SQUARE` is
defined, the second `WORDS` shows it below the visible separator
`ここから先はユーザーが : で定義したワードなどです`. Only the newest searchable
definition of a name is shown; hidden, failed, and rolled-back definitions are omitted.

The host prints the DATA stack after each successful input. `BYE` and `EXIT` are launcher commands for
leaving this reference REPL; they are not frozen CORE words.

## File mode with diagnostics

Without `-z`, the launcher identifies the candidate and shows the final DATA stack:

```powershell
python min0_forth.py examples/basic.fth
ruby min0_forth.rb examples/basic.fth
```

The older `run_source.py/.rb` tools exercise the smaller raw bytecode compiler and are retained for
cross-language experiments. New users should prefer `min0_forth.py/.rb`.

## Safety

Read `FIRST_READ.md` before using the security demonstrations. All included signing keys are public test
fixtures. Edited Viewer source is not executed inside the Viewer; copy or save it and use one of the host
launchers above.
