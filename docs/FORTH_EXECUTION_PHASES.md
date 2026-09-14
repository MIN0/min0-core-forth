# Understanding FORTH interpretation, compilation, and execution

[Read this page in Japanese](FORTH_EXECUTION_PHASES_JP.md)

Status: knowledge record based on implemented MIN0 CORE FORTH behavior, intended for integration into the
learning material of the next release.

## Why one word can appear to have several meanings

FORTH distinguishes reading source from later execution of the word produced by that source. Whether a word
acts now or creates code that acts later depends on interpreter state and on the semantics assigned to the
word.

This note uses four convenient times:

| Time | What happens |
| --- | --- |
| Interpretation | A number or ordinary word entered at the prompt is handled immediately. |
| Compilation | Source inside `: name ... ;` creates a dictionary entry and code for later execution. |
| Defining-word execution | Invoking a definition containing `CREATE` makes a named child word. |
| Created-word execution | Invoking that child performs behavior supplied after `DOES>`. |

Standard FORTH descriptions distinguish interpretation semantics, compilation semantics, and execution
semantics for each word. Labeling a word only “for compilation” or “for execution” hides these time shifts.

## `: ... ;`: entering and leaving compilation state

```forth
: SQUARE
  DUP *
;
```

`:` executes during interpretation, parses a name, and begins a hidden colon definition. `DUP` and `*` then
compile code for a future invocation of `SQUARE`; they do not act on the DATA stack at that moment. `;`
finishes and publishes the definition and returns the interpreter to interpretation state.

`:` and `;` therefore are matched definition delimiters. They do not use the direct-control buffer because
the colon compiler already owns their multiline state, code generation, publication, and rollback.

A standalone `;` fails because there is no unfinished definition to close, not because `;` lacks semantics.

## `IF ... THEN`: build structure during compilation, consume a flag during execution

```forth
: ABS-LIKE
  DUP 0 < IF
    0 SWAP -
  THEN
;
```

During compilation, `IF` and `THEN` construct code containing a patched branch. The `( flag -- )` effect of
`IF` occurs when `ABS-LIKE` later executes, not while its definition is being compiled.

MIN0 CORE FORTH also accepts the structure directly at the prompt:

```forth
1 IF 10 ELSE 20 THEN
```

Here the outer interpreter collects through `THEN`, validates the structure and all referenced words, and
then executes it. An opener is not rejected merely because its closer has not arrived yet; an `ELSE` or
`THEN` with no corresponding opener remains a context error.

## `['] name`: resolve during compilation, leave an `xt` during execution

```forth
: GET-SQUARE-XT
  ['] SQUARE
;
```

`[']` parses `SQUARE` during compilation and emits code that will place its execution token, or `xt`, on the
DATA stack later. It does not place that `xt` on the stack while `GET-SQUARE-XT` is being compiled.

At the prompt, use the interpretation form to obtain the `xt` immediately:

```forth
' SQUARE
```

The name following `[']` is a syntactic operand, not a closing delimiter, so this form does not need a
matched-control buffer.

## `CREATE ... DOES>`: one definition creates another word

```forth
: VALUE:
  CREATE ,
  DOES> @
;

10 VALUE: TEN
TEN
```

Three times are visible:

1. Defining `VALUE:` parses `CREATE , DOES> @` and creates a defining word.
2. Executing `10 VALUE: TEN` lets `CREATE` make `TEN` and lets `,` store 10 in its data field.
3. Executing `TEN` performs the `@` behavior after `DOES>` and retrieves 10.

`CREATE` and `DOES>` cooperate, but they are not a simple opener/closer pair:

- `CREATE` can make a child without `DOES>`.
- `DOES>` does not close `CREATE`; it marks the behavior later assigned to the created child.
- `;` closes the entire definition, including the portion after `DOES>`.

In MIN0 CORE FORTH v0.1, source `CREATE` must be the first body token of a defining word and `DOES>` may
appear once after it. These are current implementation-stage rules, separate from the general FORTH model.

## `UNLOOP`: remove a run-time resource, not a syntactic delimiter

The closer corresponding to `DO` is `LOOP` or `+LOOP`. `UNLOOP` is instead an executable word that explicitly
removes the innermost active loop frame.

```forth
: SEARCH-LIKE
  10 0 DO
    I 3 = IF
      UNLOOP EXIT
    THEN
  LOOP
;
```

It is commonly used before leaving a colon definition without passing through the normal loop terminator.
`UNLOOP` itself does not transfer control, so the example combines it with `EXIT`. With no active loop frame,
it has a context error.

MIN0 direct-input loops currently use `LEAVE`, which combines control transfer with loop-frame cleanup.
`UNLOOP` inside the direct buffer remains out of scope until its relationship with following execution,
`EXIT`, and the buffered loop terminator is specified.

## Distinguishing reasons for errors

| Kind | Example | Meaning |
| --- | --- | --- |
| Incomplete | EOF after `1 IF` | Wait for more input first; at EOF, report the required `THEN`. |
| No matching context | Standalone `THEN`, `LOOP`, or `;` | Nothing in the current context can be closed. |
| Missing run-time context | `I`, `J`, or `UNLOOP` outside a loop | The word exists, but its required frame does not. |
| Current implementation limit | `S"` or `UNLOOP` in a direct buffer | Safe unified semantics have not yet been specified. |

This separates incomplete syntax, mismatched structure, missing run-time context, and implementation-stage
limits instead of calling every case “a dictionary word that cannot execute.”

## Integration into the next release

The next consolidated learning chapter should build on this note and cover:

- interpretation, compilation, and execution semantics;
- the timeline from source reading through defining-word and created-word invocation;
- a comparison of `: ... ;`, direct controls, `[']`, `CREATE ... DOES>`, and `UNLOOP`;
- classifications that are more precise than the short label “compile-only”;
- when incomplete input should wait and when a context error should be immediate; and
- matching executable examples and regression tests in Python and Ruby.

That chapter must clearly separate general FORTH concepts from current MIN0 implementation limits.
