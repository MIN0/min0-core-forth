# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_direct_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_direct_outer(direct_execution_limit: 100_000)
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  Min0CoreForth::OuterInterpreter.new(
    vm, dictionary, direct_execution_limit: direct_execution_limit
  )
end

outer = build_direct_outer
assert_direct_equal([10], outer.interpret("1 IF 10 ELSE 20 THEN"), "direct true IF")
outer.vm.data_stack.clear
assert_direct_equal([20], outer.interpret("0 IF 10 ELSE 20 THEN"), "direct false IF")

outer = build_direct_outer
assert_direct_equal([], outer.interpret("1 IF"), "multiline IF begins")
assert_direct_equal(
  Min0CoreForth::STATE_DIRECT_CONTROL, outer.state, "multiline IF state"
)
assert_direct_equal(true, outer.awaiting_direct_control?, "multiline IF awaits THEN")
assert_direct_equal([], outer.interpret('7 . ." ok"'), "multiline IF body")
assert_direct_equal([], outer.interpret("THEN"), "multiline IF finishes")
assert_direct_equal("7ok", outer.terminal_text, "multiline IF output")

outer = build_direct_outer
assert_direct_equal(
  [20],
  outer.interpret("1 IF 0 IF 10 ELSE 20 THEN ELSE 30 THEN"),
  "nested direct IF"
)

outer = build_direct_outer
assert_direct_equal(
  [3], outer.interpret("0 BEGIN 1 + DUP 3 = UNTIL"), "direct BEGIN UNTIL"
)
outer.vm.data_stack.clear
assert_direct_equal(
  [3],
  outer.interpret("0 BEGIN DUP 3 < WHILE 1 + REPEAT"),
  "direct BEGIN WHILE REPEAT"
)

outer = build_direct_outer(direct_execution_limit: 20)
begin
  outer.interpret("BEGIN AGAIN")
  raise "BEGIN AGAIN limit: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("execution limit")

  assert_direct_equal([], outer.vm.data_stack, "BEGIN AGAIN rollback")
end

outer = build_direct_outer
assert_direct_equal([2, 3, 4], outer.interpret("5 2 DO I LOOP"), "direct DO LOOP")
outer.vm.data_stack.clear
assert_direct_equal([], outer.interpret("4 4 ?DO 99 LOOP"), "direct equal ?DO")
assert_direct_equal([0, 2, 4], outer.interpret("6 0 DO I 2 +LOOP"), "direct +LOOP")
outer.vm.data_stack.clear
assert_direct_equal(
  [0, -1, -2, -3, -4],
  outer.interpret("-5 0 DO I -1 +LOOP").map { |value| Min0CoreForth.signed(value) },
  "direct negative +LOOP"
)

outer = build_direct_outer
assert_direct_equal(
  [0, 0, 0, 1, 1, 0, 1, 1],
  outer.interpret("2 0 DO 2 FOR J I NEXT LOOP"),
  "nested direct DO and FOR"
)
assert_direct_equal([], outer.vm.loop_stack, "nested direct loop stack")

outer = build_direct_outer
assert_direct_equal(
  [0, 1, 2],
  outer.interpret("5 0 DO I DUP 2 = IF LEAVE THEN LOOP"),
  "direct LEAVE"
)
assert_direct_equal([], outer.vm.loop_stack, "direct LEAVE loop stack")

outer = build_direct_outer
begin
  outer.interpret("1 IF 99 . LOOP")
  raise "mismatched direct structure: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("direct DO")

  assert_direct_equal([], outer.vm.data_stack, "mismatched structure rollback")
  assert_direct_equal("", outer.terminal_text, "mismatched structure emits nothing")
end

outer = build_direct_outer
outer.interpret("1 IF 10")
begin
  outer.finish_input
  raise "unfinished direct IF: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("matching THEN")

  assert_direct_equal([], outer.vm.data_stack, "unfinished direct IF rollback")
end

outer = build_direct_outer(direct_execution_limit: 20)
outer.vm.loop_stack << Min0CoreForth::LoopFrame.new(9, 4)
begin
  outer.interpret("BEGIN AGAIN")
  raise "loop snapshot rollback: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("execution limit")

  assert_direct_equal(
    [[9, 4]],
    outer.vm.loop_stack.map { |frame| [frame.limit, frame.index] },
    "direct loop-stack snapshot rollback"
  )
end

outer = build_direct_outer
assert_direct_equal(
  [0, 8, 1, 9, 2, 8],
  outer.interpret("3 FOR I DUP 1 = IF 9 ELSE 8 THEN NEXT"),
  "direct IF nested in FOR"
)

puts "PASS: Ruby direct-control tests completed"
