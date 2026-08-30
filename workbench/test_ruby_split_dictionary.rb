# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def make_split_dictionary(body_limit: 0x10000)
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
    vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: body_limit
  )
  [vm, dictionary]
end

vm, dictionary = make_split_dictionary
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
stack = outer.interpret(
  "CREATE TABLE 10 , 20 , VARIABLE FLAG " \
  ": SUM-TABLE TABLE @ TABLE CELL+ @ + ; " \
  "SUM-TABLE DUP FLAG ! FLAG @ TABLE"
)
table = dictionary.find("TABLE")
flag = dictionary.find("FLAG")
assert_equal(0x8000, table.payload, "split CREATE body")
assert_equal(0x8008, flag.payload, "split VARIABLE body")
assert_equal(true, table.header_address < 0x8000, "split CREATE header")
assert_equal(true, flag.header_address < 0x8000, "split VARIABLE header")
assert_equal(0x800C, dictionary.data_here, "split data HERE")
assert_equal("0a000000140000001e000000", dictionary.body_image.unpack1("H*"), "split body image")
assert_equal([30, 30, 0x8000], stack, "split execution")

_vm, dictionary = make_split_dictionary(body_limit: 0x8002)
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
begin
  dictionary.add_variable("TOO-BIG")
  raise "split rollback: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "split rollback pointers")
  assert_equal(nil, dictionary.find("TOO-BIG", include_hidden: true), "split rollback word")
end

puts "PASS: Ruby split-dictionary tests completed"
