# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def assert_invalid(message, name)
  yield
  raise "#{name}: expected InvalidDictionary"
rescue Min0CoreForth::InvalidDictionary => error
  raise "#{name}: #{error.message.inspect} does not include #{message.inspect}" unless error.message.include?(message)

  puts "#{name}: PASS"
end

def assert_dictionary_error(name)
  yield
  raise "#{name}: expected DictionaryError"
rescue Min0CoreForth::DictionaryError
  puts "#{name}: PASS"
end

def make_plan_audit_system
  bus = Min0CoreForth::RegionMemory.new(
    0x10000,
    [
      Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true),
      Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"),
      Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x8000, size: 0x8000, permissions: "rw")
    ]
  )
  vm = Min0CoreForth::VM.new(memory_bus: bus)
  dictionary = Min0CoreForth::RuntimeDictionary.new(
    vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x10000
  )
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(": RECORD: CREATE C, ALLOT ALIGN ;")
  entry = dictionary.find("RECORD:")
  descriptor = entry.payload
  plan = vm.read_cell(descriptor)
  count = vm.read_cell(plan + 8)
  [vm, dictionary, outer, entry, descriptor, plan, count]
end

vm, dictionary, = make_plan_audit_system
entry = dictionary.find("RECORD:")
descriptor = entry.payload
plan = vm.read_cell(descriptor)
count = vm.read_cell(plan + 8)
assert_equal(Min0CoreForth::CONSTRUCTOR_PLAN_MAGIC, vm.read_cell(plan), "plan magic")
assert_equal(Min0CoreForth::CONSTRUCTOR_PLAN_VERSION, vm.read_cell(plan + 4), "plan version")
assert_equal(4, count, "plan count")
assert_equal(4, dictionary.read_constructor_plan(entry).length, "plan decoded count")

[
  [0, 0, "magic"],
  [4, Min0CoreForth::CONSTRUCTOR_PLAN_VERSION + 1, "version"]
].each do |offset, value, message|
  vm, dictionary, _outer, entry, _descriptor, plan, = make_plan_audit_system
  vm.write_cell(plan + offset, value)
  assert_invalid(message, "reject #{message}") { dictionary.read_constructor_plan(entry) }
end

[0, 0xFFFF_FFFF].each do |bad_count|
  vm, dictionary, _outer, entry, _descriptor, plan, = make_plan_audit_system
  vm.write_cell(plan + 8, bad_count)
  assert_invalid("length", "reject length #{bad_count}") { dictionary.read_constructor_plan(entry) }
end

[
  [0, 99, "unknown constructor action"],
  [0, Min0CoreForth::CONSTRUCTOR_ACTION_END, "END must be the final"],
  [-1, Min0CoreForth::CONSTRUCTOR_ACTION_ALIGN, "END must be the final"]
].each do |step_index, action, message|
  vm, dictionary, _outer, entry, _descriptor, plan, count = make_plan_audit_system
  index = step_index.negative? ? count - 1 : step_index
  vm.write_cell(plan + 12 + index * 8 + 4, action)
  assert_invalid(message, "reject action #{step_index}/#{action}") { dictionary.read_constructor_plan(entry) }
end

vm, dictionary, _outer, entry, descriptor, = make_plan_audit_system
vm.write_cell(descriptor, descriptor - 4)
assert_invalid("plan address", "reject overlapping plan") { dictionary.read_constructor_plan(entry) }

vm, dictionary, _outer, entry, _descriptor, plan, = make_plan_audit_system
vm.write_cell(plan + 12, 0x4000)
assert_invalid("not executable", "reject non-CODE segment") { dictionary.read_constructor_plan(entry) }

vm, dictionary, _outer, entry, descriptor, = make_plan_audit_system
vm.write_cell(entry.xt + 4, descriptor + 1)
assert_invalid("descriptor address", "reject unaligned descriptor") { dictionary.read_constructor_plan(entry) }

vm, dictionary, outer, = make_plan_audit_system
outer.interpret(": CANDIDATE 1 ;")
candidate = dictionary.find("CANDIDATE")
code = candidate.payload
saved = [
  dictionary.here,
  dictionary.data_here,
  dictionary.latest,
  vm.read_bytes(dictionary.base, dictionary.here - dictionary.base)
]
[
  [],
  [[code, 99]],
  [[code, Min0CoreForth::CONSTRUCTOR_ACTION_ALIGN]],
  [[code, Min0CoreForth::CONSTRUCTOR_ACTION_END], [code, Min0CoreForth::CONSTRUCTOR_ACTION_END]],
  [[0x4000, Min0CoreForth::CONSTRUCTOR_ACTION_END]],
  [[0x10000, Min0CoreForth::CONSTRUCTOR_ACTION_END]]
].each_with_index do |steps, index|
  assert_dictionary_error("reject set_definer input #{index}") { dictionary.set_definer(candidate, steps) }
  actual = [
    dictionary.here,
    dictionary.data_here,
    dictionary.latest,
    vm.read_bytes(dictionary.base, dictionary.here - dictionary.base)
  ]
  assert_equal(saved, actual, "set_definer input #{index} preserves dictionary")
end

vm, dictionary, outer, _entry, _descriptor, plan, = make_plan_audit_system
outer.interpret("2 0x1AB")
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
vm.write_cell(plan + 4, Min0CoreForth::CONSTRUCTOR_PLAN_VERSION + 1)
assert_invalid("version", "corrupt plan execution") { outer.interpret("RECORD: BAD") }
assert_equal([2, 0x1AB], vm.data_stack, "corrupt plan stack preserved")
assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "corrupt plan allocator preserved")
assert_equal(nil, dictionary.find("BAD", include_hidden: true), "corrupt plan child absent")

vm, dictionary, outer, _entry, _descriptor, plan, = make_plan_audit_system
outer.interpret("2 0x1AB")
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
first_code = vm.read_cell(plan + 12)
vm.write_u8(first_code, 0xFF)
begin
  outer.interpret("RECORD: BAD")
  raise "segment failure: expected InvalidOpcode"
rescue Min0CoreForth::InvalidOpcode
  puts "segment failure rejected: PASS"
end
assert_equal([2, 0x1AB], vm.data_stack, "segment failure stack preserved")
assert_equal([], vm.return_stack, "segment failure return stack")
assert_equal([], vm.loop_stack, "segment failure loop stack")
assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "segment failure allocator preserved")
assert_equal(nil, dictionary.find("BAD", include_hidden: true), "segment failure child absent")

puts "PASS: Ruby constructor-plan validation audit completed"
