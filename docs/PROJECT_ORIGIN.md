# Why MIN0 CORE FORTH began with Ruby and Python

[Read this page in Japanese](PROJECT_ORIGIN_JP.md)

MIN0 CORE FORTH began as an experiment in a common FORTH system that is not tied in advance to one CPU,
MPU, operating system, or memory size. Small microcontrollers and FPGAs are leading future targets, but
the first stage deliberately avoids letting a target instruction set constrain the design too early.

The project therefore built Ruby and Python implementations in parallel as executable specifications
before writing target-machine code. They are not the final targets. Expressing the same FORTH meaning
independently in two languages makes ambiguity, hidden assumptions, and portability errors easier to
find. The unrestricted host stage can explore ideas first; later work can choose small size, additional
features, or a new processor according to the target's purpose.

Ruby also has a personal place in the project's history. The developer briefly wrote 80386 firmware in
assembly in the late 1980s and then spent many years away from programming. Using Ruby later for an
Excel-file transformation brought back the pleasure of expressing an idea directly and immediately
seeing it run. Python is equally important to the current experimental environment. Their different
styles and strengths make the two implementations useful mirrors for one another.

The purpose is therefore not to select a winner between Ruby and Python. It is to use two independent
implementations to observe the common FORTH semantics and decide what should be carried into future
hardware descendants. MIN0 CORE FORTH begins not as one finished machine, but as a root from which many
implementations may grow.

This text is background material. It can be shortened and combined with a demonstration when presenting
the project to FORTH2020 or another audience.
