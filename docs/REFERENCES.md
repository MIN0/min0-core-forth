# FORTH design and learning references

[Read this page in Japanese](REFERENCES_JP.md)

FORTH material can be difficult to discover because important explanations are spread across old books,
archives, and living implementations. This page is a short route map: it explains what each resource is
useful for and links to the page maintained by its publisher or project.

> [!NOTE]
> MIN0 CORE FORTH does not bundle these books or third-party implementations. A link is a reading
> recommendation, not a claim that the external material is part of this release or uses exactly the same
> words and behavior.

## A short reading path

| If you want to... | Begin with... |
| --- | --- |
| Try FORTH before studying theory | the Guided Viewer, then the [pocket word reference](WORD_REFERENCE.md) |
| Learn ordinary FORTH programming | *Starting FORTH*, then *Thinking FORTH* |
| Understand dictionaries and interpreters | FIG-Forth, CF, and *eForth and Zen* |
| Ask why FORTH has this shape | *Programming a Problem-Oriented Language* |
| Think about small-MPU ports | the 430eForth material and compact VM implementations |

## FORTH design

- [Forth Interest Group (FIG)](https://www.forth.org/) — a historical gateway to educational material,
  reference works, implementations, and Forth community archives.
- [FIG-Forth implementations](https://www.forth.org/fig-forth/contents.html) — scanned and transcribed
  implementations for many processors. The site warns that OCR text may contain errors, so program listings
  should be checked against the page images before critical use.
- [CF FORTH](https://github.com/CCurl/cf) — a compact C-based FORTH VM exposing its primitives and
  inner/outer interpreters. It is useful when comparing the boundary between a small VM and source-defined
  words.
- [RETRO FORTH](https://retroforth.org/) — a portable modern Forth centered on a small, understandable
  virtual machine. It provides another example of separating a language environment from a host CPU.

These are design references, not source-code parents of MIN0 CORE FORTH. This project uses its own
Python and Ruby implementations and tests. The references help readers compare choices such as VM shape,
dictionary layout, primitives, interpretation, compilation, and portability.

## Books for learning FORTH

### Begin with the language

- [*Standard FORTH* by Toshio Inoue — National Diet Library Search (Japanese)](https://ndlsearch.ndl.go.jp/books/R100000002-I000001755527)
  — a 1985 Japanese introduction extending from basic ideas to applications. The catalog records a digitized
  copy; access is governed by the National Diet Library's transmission and registered-user conditions.
- [*Starting FORTH* — official online edition from FORTH, Inc.](https://www.forth.com/starting-forth/)
  — Leo Brodie's illustrated introduction and a practical first book for learning stack use, definitions,
  decisions, and loops.
- [*Thinking FORTH* — official FORTH, Inc. book page](https://www.forth.com/forth-books/)
  — Leo Brodie's guide to factoring problems into words and writing programs that preserve the strengths of
  FORTH. The publisher's page links to the available edition.

### Go deeper into implementation and design

- [*eForth and Zen* — second-edition PDF preserved by FIG](https://www.forth.org/OffeteStore/1013_eForthAndZen.pdf)
  — Dr. Chen-Hanson Ting's explanation of a compact eForth implementation. Other editions exist, so check the
  edition before comparing code or architecture details.
- [*Zen and the Forth Language: eForth for the MSP430 from Texas Instruments* — 430eForth resources](https://forth-ev.de/wiki/en%3Aprojects%3A430eforth%3Astart)
  — a concrete study of constructing eForth on a constrained microcontroller; especially relevant when
  considering how a common FORTH core becomes a target-specific child system.
- [*Programming a Problem-Oriented Language: Forth — how the internals work* by Charles H. Moore](https://colorforth.github.io/POL.htm)
  — an online text about growing a language around a problem and about input, stacks, dictionaries,
  definitions, and memory. Read it for the reasoning behind FORTH's structure, not merely its commands.

## Keep implementation differences visible

The books and systems above represent different periods, standards, cell sizes, threading models, and target
machines. A familiar word may be absent or have different edge conditions. For the behavior implemented by
this project, use the [MIN0 CORE FORTH pocket word reference](WORD_REFERENCE.md) and the executable tests as
the final local authority.

## Source and link boundary

This route map was adapted for MIN0 CORE FORTH from the [Japanese](https://github.com/MinoruKishi/forth-in-motion/blob/main/docs/ja/REFERENCES.md)
and [English](https://github.com/MinoruKishi/forth-in-motion/blob/main/docs/en/REFERENCES.md) reference
lists in *forth-in-motion*.
The descriptions here are newly written for this project. External sites remain under their respective
owners and terms, and their availability may change.
