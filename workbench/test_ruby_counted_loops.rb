# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_outer(max_loop_depth: 32, direct_token_limit: 4096)
  vm = Min0CoreForth::VM.new(max_loop_depth: max_loop_depth)
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  [
    vm,
    dictionary,
    Min0CoreForth::OuterInterpreter.new(
      vm, dictionary, direct_token_limit: direct_token_limit
    )
  ]
end

vm, _dictionary, outer = build_outer
outer.interpret(": INDEXES 5 0 DO I LOOP ;")
assert_equal([0, 1, 2, 3, 4], outer.interpret("INDEXES"), "DO LOOP I")
assert_equal([], vm.loop_stack, "loop stack balanced")
assert_equal(
  "010500000001000000001517160b10000003",
  vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
  "DO LOOP code"
)

_vm, _dictionary, outer = build_outer
outer.interpret(": RANGE 5 2 DO I LOOP ;")
assert_equal([2, 3, 4], outer.interpret("RANGE"), "nonzero start")

vm, _dictionary, outer = build_outer
outer.interpret(": GRID 2 0 DO 3 0 DO I LOOP LOOP ;")
assert_equal([0, 1, 2, 0, 1, 2], outer.interpret("GRID"), "nested DO LOOP")
assert_equal([], vm.loop_stack, "nested loop stack balanced")

_vm, _dictionary, outer = build_outer
outer.interpret(": THREE 3 0 DO")
outer.interpret("I")
outer.interpret("LOOP ;")
assert_equal([0, 1, 2], outer.interpret("THREE"), "DO LOOP across inputs")

vm = Min0CoreForth::VM.new
program = [
  Min0CoreForth::Op::LIT, 2, 0, 0, 0,
  Min0CoreForth::Op::LIT, 0, 0, 0, 0,
  Min0CoreForth::Op::DO,
  Min0CoreForth::Op::UNLOOP,
  Min0CoreForth::Op::HALT
].pack("C*")
vm.load(program)
assert_equal([], vm.run, "UNLOOP execution")
assert_equal([], vm.loop_stack, "UNLOOP removes frame")

vm, _dictionary, outer = build_outer(max_loop_depth: 1)
outer.interpret(": NESTED 2 0 DO 2 0 DO I LOOP LOOP ;")
begin
  outer.interpret("NESTED")
  raise "nested limit: expected LoopStackOverflow"
rescue Min0CoreForth::LoopStackOverflow
  puts "nested loop limit: PASS"
  assert_equal([], vm.data_stack, "loop overflow data recovery")
  assert_equal([], vm.return_stack, "loop overflow return recovery")
  assert_equal([], vm.loop_stack, "loop overflow loop recovery")
end

[
  ": BAD DO ;",
  ": BAD LOOP ;",
  ": BAD DO IF LOOP THEN ;"
].each do |source|
  _vm, dictionary, outer = build_outer
  saved_here = dictionary.here
  saved_code_here = outer.code_here
  begin
    outer.interpret(source)
    raise "malformed DO LOOP: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "DO LOOP rollback state")
    assert_equal([], outer.control_stack, "DO LOOP rollback control stack")
    assert_equal(saved_here, dictionary.here, "DO LOOP rollback dictionary")
    assert_equal(saved_code_here, outer.code_here, "DO LOOP rollback code")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "DO LOOP rollback word")
  end
end

_vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("3 0 DO"), "direct DO begins")
assert_equal(true, outer.awaiting_direct_control?, "direct DO awaits closer")
begin
  outer.finish_input
  raise "unfinished direct DO: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("matching LOOP")

  assert_equal([], outer.vm.data_stack, "unfinished direct DO rollback")
end
begin
  outer.interpret("LOOP")
  raise "unmatched LOOP: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("direct DO")
end

_vm, _dictionary, outer = build_outer
assert_equal([0, 1, 2], outer.interpret("3 FOR I NEXT"), "direct FOR NEXT")
outer.vm.data_stack.clear
outer.interpret(": INDEXES 3 FOR I NEXT ;")
assert_equal([0, 1, 2], outer.interpret("INDEXES"), "compiled FOR NEXT")

_vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("0 FOR 99 NEXT"), "direct zero FOR")
outer.interpret(": ZERO 0 FOR 99 NEXT ;")
assert_equal([], outer.interpret("ZERO"), "compiled zero FOR")

vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("3 FOR"), "direct FOR begins")
assert_equal(Min0CoreForth::STATE_DIRECT_LOOP, outer.state, "direct FOR state")
assert_equal(true, outer.awaiting_direct_loop?, "direct FOR awaiting NEXT")
assert_equal([], outer.interpret("I ."), "direct FOR body collection")
assert_equal(Min0CoreForth::STATE_DIRECT_LOOP, outer.state, "direct FOR state persists")
assert_equal([], outer.interpret("NEXT"), "direct FOR finishes")
assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "direct FOR restores state")
assert_equal(false, outer.awaiting_direct_loop?, "direct FOR no longer awaiting")
assert_equal("012", outer.terminal_text, "direct FOR output")
assert_equal([], vm.loop_stack, "direct FOR loop stack balanced")

vm, _dictionary, outer = build_outer
expected = [0, 0, 0, 1, 0, 2, 1, 0, 1, 1, 1, 2]
assert_equal(
  expected,
  outer.interpret("2 FOR 3 FOR J I NEXT NEXT"),
  "nested direct FOR with I and J"
)
assert_equal([], vm.loop_stack, "nested direct FOR stack balanced")
vm.data_stack.clear
outer.interpret(": GRID 2 FOR 3 FOR J I NEXT NEXT ;")
assert_equal(expected, outer.interpret("GRID"), "nested compiled FOR with I and J")

_vm, _dictionary, outer = build_outer
outer.interpret(": STOP 5 FOR I DUP 2 = IF LEAVE THEN NEXT ;")
assert_equal([0, 1, 2], outer.interpret("STOP"), "LEAVE exits compiled FOR")

_vm, _dictionary, outer = build_outer
outer.interpret("3 FOR I")
begin
  outer.finish_input
  raise "unfinished direct FOR: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("matching NEXT")

  assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "unfinished FOR state rollback")
  assert_equal([], outer.vm.data_stack, "unfinished FOR data rollback")
end

_vm, _dictionary, outer = build_outer(direct_token_limit: 2)
begin
  outer.interpret("3 FOR 1 2 3")
  raise "direct FOR buffer: expected CompileStateError"
rescue Min0CoreForth::CompileStateError => error
  raise unless error.message.include?("exceeds 2 tokens")

  assert_equal([], outer.vm.data_stack, "direct FOR buffer rollback")
end

vm, _dictionary, outer = build_outer(max_loop_depth: 1)
begin
  outer.interpret("2 FOR 2 FOR I NEXT NEXT")
  raise "direct FOR depth: expected LoopStackOverflow"
rescue Min0CoreForth::LoopStackOverflow
  assert_equal([], vm.data_stack, "direct FOR depth data rollback")
  assert_equal([], vm.loop_stack, "direct FOR depth loop rollback")
end

_vm, _dictionary, outer = build_outer
assert_equal(
  [0, 8, 1, 9, 2, 8],
  outer.interpret("3 FOR I DUP 1 = IF 9 ELSE 8 THEN NEXT"),
  "direct FOR supports nested IF"
)

[
  ": BAD FOR ;",
  ": BAD NEXT ;",
  ": BAD FOR IF NEXT THEN ;"
].each do |source|
  _vm, dictionary, outer = build_outer
  begin
    outer.interpret(source)
    raise "compiled FOR structure: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "compiled FOR rollback state")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "compiled FOR rollback word")
  end
end

puts "PASS: Ruby counted-loop tests completed"
