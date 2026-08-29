# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def aligned(address)
  (address + 3) & ~3
end

def build_outer(limit: nil, install_primitives: true)
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm, limit: limit)
  Min0CoreForth.install_core_primitives(dictionary) if install_primitives
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

vm, dictionary, outer = build_outer
outer.interpret("CREATE BYTES 0x41 C, 0x142 C,")
entry = dictionary.find("BYTES")
assert_equal("AB", vm.memory.byteslice(entry.payload, 2), "C, low bytes")
assert_equal([0x41, 0x42], outer.interpret("BYTES C@ BYTES CHAR+ C@"), "C@ CHAR+")
vm.data_stack.clear
outer.interpret(": SECOND-BYTE BYTES CHAR+ C@ ;")
assert_equal([0x42], outer.interpret("SECOND-BYTE"), "compiled byte access")

vm, dictionary, outer = build_outer
outer.interpret("CREATE BYTE 0 C,")
entry = dictionary.find("BYTE")
assert_equal([0xFF], outer.interpret("0x1FF BYTE C! BYTE C@"), "C! low byte")
assert_equal(0xFF, vm.memory.getbyte(entry.payload), "C! memory")

vm, _dictionary, outer = build_outer
assert_equal([5, 6], outer.interpret("5 CHARS 5 CHAR+"), "CHARS CHAR+")
vm.data_stack.clear
assert_equal([Min0CoreForth::CELL_MASK, 0], outer.interpret("-1 CHARS -1 CHAR+"), "character wrapping")

vm, dictionary, outer = build_outer
outer.interpret("CREATE MIXED 0xAA C, 0x11223344 ,")
entry = dictionary.find("MIXED")
cell_address = aligned(entry.payload + 1)
assert_equal(0xAA, vm.memory.getbyte(entry.payload), "mixed character")
assert_equal(
  "\x00" * (cell_address - entry.payload - 1),
  vm.memory.byteslice(entry.payload + 1, cell_address - entry.payload - 1),
  "mixed alignment padding"
)
assert_equal(0x11223344, vm.read_cell(cell_address), "mixed cell")

vm, dictionary, outer = build_outer(
  limit: Min0CoreForth::DICTIONARY_BASE + 1,
  install_primitives: false
)
outer.interpret("0x141 C,")
assert_equal(0x41, vm.memory.getbyte(Min0CoreForth::DICTIONARY_BASE), "initial C,")
begin
  outer.interpret("0x142 C,")
  raise "full C,: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([0x142], vm.data_stack, "full C, preserves value")
  assert_equal(Min0CoreForth::DICTIONARY_BASE + 1, dictionary.here, "full C, HERE")
  assert_equal(0x41, vm.memory.getbyte(Min0CoreForth::DICTIONARY_BASE), "full C, preserves byte")
end

vm, _dictionary, outer = build_outer
begin
  outer.interpret("65536 C@")
  raise "C@ fault: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_equal([65_536], vm.data_stack, "C@ fault preserves address")
end
vm.data_stack.clear
begin
  outer.interpret("7 65536 C!")
  raise "C! fault: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_equal([7, 65_536], vm.data_stack, "C! fault preserves arguments")
end

vm, _dictionary, outer = build_outer
begin
  outer.interpret("65536 @")
  raise "@ fault: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_equal([65_536], vm.data_stack, "@ fault preserves address")
end
vm.data_stack.clear
begin
  outer.interpret("7 65536 !")
  raise "! fault: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_equal([7, 65_536], vm.data_stack, "! fault preserves arguments")
end

[["C@", []], ["7 C!", [7]], ["CHAR+", []], ["CHARS", []]].each do |source, expected_stack|
  vm, _dictionary, outer = build_outer
  begin
    outer.interpret(source)
    raise "#{source}: expected StackUnderflow"
  rescue Min0CoreForth::StackUnderflow
    assert_equal(expected_stack, vm.data_stack, "#{source} stack check")
  end
end

vm, dictionary, outer = build_outer
outer.interpret("CREATE TEXT 0x46 C, 0x4F C, 0x52 C, 0x54 C, 0x48 C,")
assert_equal([], outer.interpret("TEXT 5 TYPE"), "TYPE stack effect")
assert_equal(["FORTH"], outer.output, "TYPE output fragment")
assert_equal("FORTH", outer.terminal_text, "TYPE exact output")
raise "TYPE fixture: TEXT was not defined" if dictionary.find("TEXT").nil?

vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("0xFFFFFFFF 0 TYPE"), "zero-length TYPE stack effect")
assert_equal([], outer.output, "zero-length TYPE output")

vm, _dictionary, outer = build_outer
outer.interpret("65 EMIT")
begin
  outer.interpret("65534 4 TYPE")
  raise "TYPE fault: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_equal([65_534, 4], vm.data_stack, "TYPE fault preserves arguments")
  assert_equal(["A"], outer.output, "TYPE fault preserves output")
end

[["TYPE", []], ["7 TYPE", [7]]].each do |source, expected_stack|
  vm, _dictionary, outer = build_outer
  begin
    outer.interpret(source)
    raise "#{source}: expected StackUnderflow"
  rescue Min0CoreForth::StackUnderflow
    assert_equal(expected_stack, vm.data_stack, "#{source} stack check")
    assert_equal([], outer.output, "#{source} output check")
  end
end

flash = Min0CoreForth::MemoryRegion.new(
  name: "FLASH", start: 0x9000, size: 0x1000, permissions: "r", programmable: true
)
bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(
      name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true
    ),
    Min0CoreForth::MemoryRegion.new(
      name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"
    ),
    Min0CoreForth::MemoryRegion.new(
      name: "DATA", start: 0x8000, size: 0x1000, permissions: "rw"
    ),
    flash
  ]
)
bus.program(0x9000, "FORTH".b)
vm = Min0CoreForth::VM.new(memory_bus: bus)
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
assert_equal([], outer.interpret("0x9000 5 TYPE"), "read-only TYPE stack effect")
assert_equal("FORTH", outer.terminal_text, "read-only TYPE output")
outer.interpret("65 EMIT")
begin
  outer.interpret("0x8FFF 2 TYPE")
  raise "cross-region TYPE: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_equal([0x8FFF, 2], vm.data_stack, "cross-region TYPE preserves arguments")
  assert_equal(["FORTH", "A"], outer.output, "cross-region TYPE preserves output")
end

puts "PASS: Ruby character-data tests completed"
