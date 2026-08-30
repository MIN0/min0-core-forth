# frozen_string_literal: true

require_relative "min0_core_forth_vm"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

vm = Min0CoreForth::VM.new
assert_equal(Min0CoreForth::DEFAULT_DATA_STACK_DEPTH, vm.max_data_depth, "data depth default")
assert_equal(Min0CoreForth::DEFAULT_RETURN_STACK_DEPTH, vm.max_return_depth, "return depth default")
assert_equal(Min0CoreForth::DEFAULT_LOOP_STACK_DEPTH, vm.max_loop_depth, "loop depth default")
assert_equal(8, Min0CoreForth::MINIMUM_CONFORMING_LOOP_DEPTH, "minimum loop depth")

vm = Min0CoreForth::VM.new(max_data_depth: 2)
vm.push(1)
vm.push(2)
begin
  vm.push(3)
  raise "data overflow: expected DataStackOverflow"
rescue Min0CoreForth::DataStackOverflow
  assert_equal([1, 2], vm.data_stack, "data overflow preserves stack")
end

asm = Min0CoreForth::Assembler.new
asm.emit(Min0CoreForth::Op::CALL, "FIRST")
asm.emit(Min0CoreForth::Op::HALT)
asm.label("FIRST")
asm.emit(Min0CoreForth::Op::CALL, "SECOND")
asm.emit(Min0CoreForth::Op::EXIT)
asm.label("SECOND")
asm.emit(Min0CoreForth::Op::EXIT)
vm = Min0CoreForth::VM.new(max_return_depth: 1)
vm.load(asm.build)
begin
  vm.run
  raise "return overflow: expected ReturnStackOverflow"
rescue Min0CoreForth::ReturnStackOverflow
  puts "return overflow: PASS"
end

asm = Min0CoreForth::Assembler.new
2.times do
  asm.emit(Min0CoreForth::Op::LIT, 2)
  asm.emit(Min0CoreForth::Op::LIT, 0)
  asm.emit(Min0CoreForth::Op::DO)
end
asm.emit(Min0CoreForth::Op::HALT)
vm = Min0CoreForth::VM.new(max_loop_depth: 1)
vm.load(asm.build)
begin
  vm.run
  raise "loop overflow: expected LoopStackOverflow"
rescue Min0CoreForth::LoopStackOverflow
  puts "loop overflow: PASS"
  assert_equal([2, 0], vm.data_stack, "loop overflow preserves arguments")
  assert_equal(1, vm.loop_stack.length, "loop overflow preserves frames")
end

asm = Min0CoreForth::Assembler.new
asm.emit(Min0CoreForth::Op::LIT, 2)
asm.emit(Min0CoreForth::Op::LIT, 0)
asm.emit(Min0CoreForth::Op::DO)
asm.emit(Min0CoreForth::Op::LIT, 0)
asm.emit(Min0CoreForth::Op::LIT, 0)
asm.emit(Min0CoreForth::Op::QDO, "done")
asm.label("done")
asm.emit(Min0CoreForth::Op::HALT)
vm = Min0CoreForth::VM.new(max_loop_depth: 1)
vm.load(asm.build)
assert_equal([], vm.run, "?DO zero trip with full loop stack")
assert_equal(1, vm.loop_stack.length, "?DO zero trip preserves outer frame")

asm = Min0CoreForth::Assembler.new
asm.emit(Min0CoreForth::Op::LIT, 1)
asm.emit(Min0CoreForth::Op::PLOOP, 0)
vm = Min0CoreForth::VM.new
vm.load(asm.build)
begin
  vm.run
  raise "PLOOP loop underflow: expected LoopStackUnderflow"
rescue Min0CoreForth::LoopStackUnderflow
  assert_equal([1], vm.data_stack, "PLOOP loop underflow preserves increment")
end

asm = Min0CoreForth::Assembler.new
asm.emit(Min0CoreForth::Op::LIT, 2)
asm.emit(Min0CoreForth::Op::LIT, 0)
asm.emit(Min0CoreForth::Op::DO)
asm.emit(Min0CoreForth::Op::PLOOP, 0)
vm = Min0CoreForth::VM.new
vm.load(asm.build)
begin
  vm.run
  raise "PLOOP data underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal(1, vm.loop_stack.length, "PLOOP data underflow preserves frame")
end

[
  [Min0CoreForth::Op::J, nil],
  [Min0CoreForth::Op::LEAVE, 0]
].each do |op, operand|
  asm = Min0CoreForth::Assembler.new
  operand.nil? ? asm.emit(op) : asm.emit(op, operand)
  vm = Min0CoreForth::VM.new
  vm.load(asm.build)
  begin
    vm.run
    raise "extended loop underflow: expected LoopStackUnderflow"
  rescue Min0CoreForth::LoopStackUnderflow
    puts "extended loop underflow: PASS"
  end
end

asm = Min0CoreForth::Assembler.new
asm.emit(Min0CoreForth::Op::LIT, 7)
asm.emit(Min0CoreForth::Op::ADD)
vm = Min0CoreForth::VM.new
vm.load(asm.build)
begin
  vm.run
  raise "binary underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal([7], vm.data_stack, "binary underflow preserves operand")
end

[
  [Min0CoreForth::Op::I, Min0CoreForth::Op::HALT].pack("C*"),
  [Min0CoreForth::Op::UNLOOP, Min0CoreForth::Op::HALT].pack("C*")
].each do |program|
  vm = Min0CoreForth::VM.new
  vm.load(program)
  begin
    vm.run
    raise "loop underflow: expected LoopStackUnderflow"
  rescue Min0CoreForth::LoopStackUnderflow
    puts "loop underflow: PASS"
  end
end

asm = Min0CoreForth::Assembler.new
asm.emit(Min0CoreForth::Op::LOOP, 0)
vm = Min0CoreForth::VM.new
vm.load(asm.build)
begin
  vm.run
  raise "LOOP underflow: expected LoopStackUnderflow"
rescue Min0CoreForth::LoopStackUnderflow
  puts "LOOP underflow: PASS"
end

begin
  Min0CoreForth::VM.new(max_loop_depth: 0)
  raise "invalid depth: expected ArgumentError"
rescue ArgumentError
  puts "invalid depth: PASS"
end

puts "PASS: Ruby stack-limit tests completed"
