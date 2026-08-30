# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def make_traced_system(trace = nil)
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
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary, trace: trace)]
end

trace = Min0CoreForth::TraceRecorder.new("ruby")
vm, dictionary, outer = make_traced_system(trace)
stack = outer.interpret(": VALUE: CREATE , DOES> @ ; 123 VALUE: ANSWER ANSWER")
expected = [
  "definer.compile.complete", "definer.execute.begin", "child.create.hidden",
  "constructor.segment.begin", "constructor.segment.end", "constructor.comma",
  "constructor.segment.begin", "constructor.segment.end", "child.does.attach",
  "child.publish", "definer.execute.end", "does.execute.begin", "does.execute.end"
]
assert_equal([123], stack, "trace VALUE execution")
assert_equal(expected, trace.events.map { |event| event[:event] }, "trace event order")
comma = trace.events[5]
assert_equal(0x8000, comma[:details][:address], "trace COMMA address")
assert_equal(123, comma[:details][:value], "trace COMMA value")
assert_equal(0x8004, comma[:state][:data_here], "trace COMMA data HERE")
assert_equal([], comma[:state][:data_stack], "trace COMMA stack")
assert_equal(Min0CoreForth::TRACE_PAYLOAD_ROLE, comma[:payload_role], "trace payload role")
assert_equal(Min0CoreForth::TRACE_FORMAT, trace.document[:trace_format], "trace format")

trace = Min0CoreForth::TraceRecorder.new("ruby")
vm, dictionary, outer = make_traced_system(trace)
outer.interpret(": VALUE: CREATE , DOES> @ ;")
trace.events.clear
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
begin
  outer.interpret("VALUE: EMPTY")
  raise "trace rollback: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  rollback = trace.events.last
  assert_equal("definer.execute.rollback", rollback[:event], "trace rollback event")
  assert_equal("StackUnderflow", rollback[:details][:error], "trace rollback error")
  assert_equal(saved, [rollback[:state][:header_here], rollback[:state][:data_here], rollback[:state][:latest]], "trace rollback state")
  assert_equal(nil, dictionary.find("EMPTY", include_hidden: true), "trace rollback child absent")
end

broken_observer = Object.new
def broken_observer.emit(*) = raise("observer failed")
vm, dictionary, outer = make_traced_system(broken_observer)
assert_equal([123], outer.interpret(": VALUE: CREATE , DOES> @ ; 123 VALUE: ANSWER ANSWER"), "broken observer execution")
assert_equal(123, vm.read_cell(0x8000), "broken observer data")
assert_equal(true, !outer.trace_failures.empty?, "broken observer isolated")

puts "PASS: Ruby semantic-trace tests completed"
