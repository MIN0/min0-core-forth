# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def make_split_dictionary(dictionary_limit: 0x8000)
  bus = Min0CoreForth::RegionMemory.new(
    0x10000,
    [
      Min0CoreForth::MemoryRegion.new(
        name: "CODE", start: 0x0000, size: 0x4000,
        permissions: "rwx", programmable: true
      ),
      Min0CoreForth::MemoryRegion.new(
        name: "DICTIONARY", start: 0x4000, size: 0x4000,
        permissions: "rw"
      ),
      Min0CoreForth::MemoryRegion.new(
        name: "DATA", start: 0x8000, size: 0x8000,
        permissions: "rw"
      )
    ]
  )
  vm = Min0CoreForth::VM.new(memory_bus: bus)
  dictionary = Min0CoreForth::RuntimeDictionary.new(
    vm, base: 0x4000, limit: dictionary_limit,
    body_base: 0x8000, body_limit: 0x10000
  )
  [vm, dictionary]
end

vm, dictionary = make_split_dictionary
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret("CREATE COUNTER 41 , : READ-PLUS-ONE @ 1 + ;")
counter = dictionary.find("COUNTER")
behavior = dictionary.find("READ-PLUS-ONE")
transformed = dictionary.set_does(counter, behavior.payload)
body_address, code_address = dictionary.read_does_descriptor(transformed)
assert_equal(Min0CoreForth::KIND_DOES, transformed.kind, "DOES kind")
assert_equal(0x8000, body_address, "DOES body")
assert_equal(behavior.payload, code_address, "DOES code")
assert_equal(true, transformed.payload.between?(0x4000, 0x7FFF), "descriptor region")
assert_equal([42], outer.interpret("COUNTER"), "interpreted DOES")
vm.data_stack.clear
assert_equal([42], outer.interpret(": USE-COUNTER COUNTER ; USE-COUNTER"), "compiled DOES")

flat_vm = Min0CoreForth::VM.new
flat_dictionary = Min0CoreForth::RuntimeDictionary.new(flat_vm)
Min0CoreForth.install_core_primitives(flat_dictionary)
flat_outer = Min0CoreForth::OuterInterpreter.new(flat_vm, flat_dictionary)
flat_outer.interpret("CREATE FLAT-ITEM 5 , : TWICE-BODY @ 2 * ;")
flat_item = flat_dictionary.find("FLAT-ITEM")
flat_behavior = flat_dictionary.find("TWICE-BODY")
flat_item = flat_dictionary.set_does(flat_item, flat_behavior.payload)
assert_equal([10], flat_outer.interpret("FLAT-ITEM"), "flat DOES")

item = dictionary.add_created("ITEM")
saved = [dictionary.here, dictionary.latest, vm.read_bytes(item.xt, 8)]
begin
  dictionary.set_does(item, 0x4000)
  raise "non-executable behavior: expected DictionaryError"
rescue Min0CoreForth::DictionaryError
  assert_equal(saved, [dictionary.here, dictionary.latest, vm.read_bytes(item.xt, 8)], "invalid target rollback")
end

small_vm, small_dictionary = make_split_dictionary(dictionary_limit: 0x4014)
small_vm.write_u8(0x1000, Min0CoreForth::Op::EXIT)
created = small_dictionary.add_created("X")
saved = [small_dictionary.here, small_dictionary.latest, small_vm.read_bytes(created.xt, 8)]
begin
  small_dictionary.set_does(created, 0x1000)
  raise "descriptor full: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal(saved, [small_dictionary.here, small_dictionary.latest, small_vm.read_bytes(created.xt, 8)], "full rollback")
end

puts "PASS: Ruby DOES-descriptor tests completed"
