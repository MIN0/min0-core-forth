# frozen_string_literal: true

require_relative "min0_core_forth_vm"

include Min0CoreForth

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def assert_raises(error_class, name)
  yield
  raise "#{name}: expected #{error_class}"
rescue error_class
  puts "#{name}: PASS"
end

class RecordingMemory < FlatMemory
  attr_reader :fetches, :reads

  def initialize(size)
    super
    @fetches = []
    @reads = []
  end

  def fetch(address, length)
    @fetches << [address, length]
    super
  end

  def fetch_u8(address)
    @fetches << [address, 1]
    super
  end

  def read(address, length)
    @reads << [address, length]
    super
  end
end

asm = Assembler.new
asm.emit(Op::LIT, 5)
asm.emit(Op::CALL, "square")
asm.emit(Op::LIT, 7)
asm.emit(Op::CALL, "double")
asm.emit(Op::HALT)
asm.label("square")
asm.emit(Op::DUP)
asm.emit(Op::MUL)
asm.emit(Op::EXIT)
asm.label("double")
asm.emit(Op::DUP)
asm.emit(Op::ADD)
asm.emit(Op::EXIT)
vm = VM.new
vm.load(asm.build)
assert_equal([25, 14], vm.run, "colon-style calls")
assert_equal([], vm.return_stack, "balanced return stack")

asm = Assembler.new
asm.emit(Op::LIT, 0xFFFF_FFFF)
asm.emit(Op::LIT, 1)
asm.emit(Op::ADD)
asm.emit(Op::HALT)
vm = VM.new
vm.load(asm.build)
assert_equal([0], vm.run, "32-bit wraparound")

asm = Assembler.new
asm.emit(Op::LIT, -1)
asm.emit(Op::LIT, 0)
asm.emit(Op::LESS)
asm.emit(Op::HALT)
vm = VM.new
vm.load(asm.build)
assert_equal([0xFFFF_FFFF], vm.run, "signed comparison and Forth true")

vm = VM.new
vm.load([Op::DROP].pack("C"))
assert_raises(StackUnderflow, "data stack underflow") { vm.run }

vm = VM.new
vm.load("\xFF".b)
assert_raises(InvalidOpcode, "invalid opcode") { vm.run }

vm = VM.new(memory_size: 64)
assert_raises(MemoryFault, "memory range check") { vm.write_cell(62, 1) }

bus = RecordingMemory.new(64)
vm = VM.new(memory_size: 64, memory_bus: bus)
asm = Assembler.new
asm.emit(Op::LIT, 48)
asm.emit(Op::FETCH)
asm.emit(Op::HALT)
vm.load(asm.build)
vm.write_cell(48, 0x1234_5678)
assert_equal([0x1234_5678], vm.run, "memory bus execution")
assert_equal(true, bus.fetches.include?([1, 4]), "memory bus fetch path")
assert_equal([[48, 4]], bus.reads, "memory bus data path")

bus = RegionMemory.new(
  80,
  [
    MemoryRegion.new(name: "CODE", start: 0, size: 32, permissions: "rx", programmable: true),
    MemoryRegion.new(name: "DATA", start: 32, size: 32, permissions: "rw")
  ]
)
vm = VM.new(memory_size: 80, memory_bus: bus)
asm = Assembler.new
asm.emit(Op::LIT, 0x1234_5678)
asm.emit(Op::LIT, 32)
asm.emit(Op::STORE)
asm.emit(Op::LIT, 32)
asm.emit(Op::FETCH)
asm.emit(Op::HALT)
vm.load(asm.build)
assert_equal([0x1234_5678], vm.run, "region memory execution")
assert_equal("78563412", bus.region_bytes("DATA").byteslice(0, 4).unpack1("H*"), "region data bytes")
assert_raises(MemoryFault, "CODE write protection") { bus.write_u8(0, 0) }
assert_raises(MemoryFault, "DATA execute protection") { bus.fetch_u8(32) }
assert_raises(MemoryFault, "cross-region cell") { bus.read(30, 4) }
assert_raises(MemoryFault, "unmapped address") { bus.read_u8(64) }

data = MemoryRegion.new(name: "DATA", start: 0, size: 16, permissions: "rw", programmable: true)
bus = RegionMemory.new(16, [data])
bus.write(0, "AB".b)
bus.seal_read_only_region("DATA")
bus.seal_read_only_region("DATA")
assert_equal("AB".b, bus.read(0, 2), "read-only data remains readable")
assert_equal("r", data.permissions, "read-only permissions")
assert_equal(true, data.read_only_sealed?, "read-only seal state")
assert_raises(MemoryFault, "read-only write protection") { bus.write_u8(0, 0) }
assert_raises(MemoryFault, "read-only program protection") { bus.program(0, "Z".b) }
assert_raises(MemoryFault, "read-only clear protection") { bus.clear }

puts "PASS: Ruby VM tests completed"
