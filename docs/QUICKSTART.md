# MIN0 CORE FORTH quick start

This release provides equivalent Python and Ruby host launchers. The commands below run on files stored
on your PC; viewing this page on GitHub does not download those files automatically.

## 0. Get the source and open the repository root

For the simplest Windows setup:

1. On the [repository page](https://github.com/MIN0/min0-core-forth), select **Code → Download ZIP**.
2. Extract the ZIP. The resulting folder is normally named `min0-core-forth-main`.
3. In File Explorer, open the folder named exactly `min0-core-forth-main`. Do **not** open its
   `viewer`, `docs`, or `workbench` subfolder yet.
4. Click File Explorer's address bar, type `powershell`, and press Enter. This opens PowerShell in the
   folder currently shown by File Explorer. You may also use **Open in Terminal** if it opens in the
   same folder.
5. Confirm that PowerShell is in the repository root:

```powershell
Get-Location
Split-Path -Leaf (Get-Location)
Test-Path .\requirements.txt
Test-Path .\workbench\min0_forth.py
```

The last three results should be `min0-core-forth-main`, `True`, and `True`. All commands in this guide
are run from this repository root.

If it prints `False`, do not run the installation command yet. Move to the extracted
`min0-core-forth-main` folder first. An error such as
`Could not open requirements file: No such file or directory` means that PowerShell is still in a
different folder; it does not mean that `pip` or MIN0 CORE FORTH is damaged.

For example, if `Get-Location` ends in `min0-core-forth-main\viewer`, you are one level too deep. Return
to the repository root and confirm again:

```powershell
Set-Location ..
Get-Location
Test-Path .\requirements.txt
```

## Requirements

- Python 3.12 and `cryptography` 50.0.0, or
- Ruby 4.0 with OpenSSL 3.x.

For Python, confirm the interpreter and install the pinned dependency into your own virtual environment:

```powershell
python --version
python -m pip install -r .\requirements.txt
```

For Ruby, confirm both Ruby and its OpenSSL library:

```powershell
ruby --version
ruby -ropenssl -e 'puts OpenSSL::OPENSSL_VERSION'
```

The expected major versions are Ruby 4.0 and OpenSSL 3.x. The Ruby implementation uses libraries
included with the Ruby installation and does not require a separate `bundle install` or additional Gem
installation for this release.

## Five-minute path

Open the **[English Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace-en.html)**.
The same page is stored in `viewer/value-trace-en.html`; it is self-contained and does not send traces
or edited source over the network.

Then run the included output example:

```powershell
python workbench/min0_forth.py -z workbench/examples/hello.fth
ruby workbench/min0_forth.rb -z workbench/examples/hello.fth
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
python workbench/min0_forth.py
```

or:

```powershell
ruby workbench/min0_forth.rb
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

The first `WORDS` shows the vocabulary available at startup. After `SQUARE` is defined, the second
`WORDS` shows it below a visible separator for definitions added by the user. Only the newest searchable
definition of a name is shown; hidden, failed, and rolled-back definitions are omitted.

The host prints the DATA stack after each successful input. `BYE` and `EXIT` are launcher commands for
leaving this reference REPL; they are not frozen CORE words.

## File mode with diagnostics

Without `-z`, the launcher identifies the release and shows the final DATA stack:

```powershell
python workbench/min0_forth.py workbench/examples/basic.fth
ruby workbench/min0_forth.rb workbench/examples/basic.fth
```

The older `run_source.py/.rb` tools exercise the smaller raw bytecode compiler and are retained for
cross-language experiments. New users should prefer `min0_forth.py/.rb`.

## Safety

Read [`FIRST_READ.md`](../FIRST_READ.md) before using the security demonstrations. All included signing keys are public test
fixtures. Edited Viewer source is not executed inside the Viewer; copy or save it and use one of the host
launchers above.
