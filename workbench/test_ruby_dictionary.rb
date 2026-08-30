# frozen_string_literal: true

require_relative "min0_core_forth_dictionary"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
dup_entry = dictionary.add_primitive("dup", Min0CoreForth::Op::DUP)
star = dictionary.add_primitive("*", Min0CoreForth::Op::MUL)
square = dictionary.add_colon("square", 0x120)

assert_equal(0x8000, dup_entry.header_address, "first header")
assert_equal(0x800C, dup_entry.xt, "first XT")
assert_equal(0x8014, star.header_address, "second header")
assert_equal(0x8020, star.xt, "second XT")
assert_equal(0x8028, square.header_address, "third header")
assert_equal(0x8038, square.xt, "third XT")
assert_equal(0x8040, dictionary.here, "HERE")
assert_equal(0x8028, dictionary.latest, "LATEST")
assert_equal(["SQUARE", "*", "DUP"], dictionary.entries.map(&:name), "link order")
assert_equal(square, dictionary.find("SqUaRe"), "case-insensitive find")

old = dictionary.add_colon("TEST", 0x100)
new_entry = dictionary.add_colon("test", 0x200)
assert_equal(new_entry, dictionary.find("TEST"), "latest definition wins")

visible = dictionary.add_colon("WORD", 0x100)
hidden = dictionary.add_colon("WORD", 0x200, hidden: true)
assert_equal(visible, dictionary.find("WORD"), "hidden entry skipped")
assert_equal(hidden, dictionary.find("WORD", include_hidden: true), "hidden entry included")

immediate = dictionary.add_primitive("IMMEDIATE-WORD", Min0CoreForth::Op::NOP, immediate: true)
assert_equal(true, immediate.immediate?, "immediate flag")
assert_equal(nil, dictionary.find("MISSING"), "unknown word")

begin
  dictionary.add_primitive("日本語", Min0CoreForth::Op::NOP)
  raise "non-ASCII name: expected DictionaryError"
rescue Min0CoreForth::DictionaryError
  puts "non-ASCII name: PASS"
end

begin
  small = Min0CoreForth::RuntimeDictionary.new(vm, base: 0x9000, limit: 0x9010)
  small.add_primitive("TOO-LARGE", Min0CoreForth::Op::NOP)
  raise "dictionary limit: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  puts "dictionary limit: PASS"
end

rollback_vm = Min0CoreForth::VM.new
rollback_dictionary = Min0CoreForth::RuntimeDictionary.new(rollback_vm)
keep = rollback_dictionary.add_primitive("KEEP", Min0CoreForth::Op::NOP)
saved_here = rollback_dictionary.here
saved_latest = rollback_dictionary.latest
building = rollback_dictionary.add_colon("BUILDING", 0x100, hidden: true)
assert_equal(nil, rollback_dictionary.find("BUILDING"), "building entry hidden")
building = rollback_dictionary.set_hidden(building, false)
assert_equal(building, rollback_dictionary.find("BUILDING"), "hidden flag cleared")
rollback_dictionary.restore(here: saved_here, latest: saved_latest)
assert_equal(keep, rollback_dictionary.find("KEEP"), "rollback keeps old entry")
assert_equal(nil, rollback_dictionary.find("BUILDING", include_hidden: true), "rollback removes entry")

puts "PASS: Ruby runtime dictionary tests completed"
