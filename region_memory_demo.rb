# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_vm"

include Min0CoreForth

def faulted
  yield
  false
rescue MemoryFault
  true
end

bus = RegionMemory.new(
  80,
  [
    MemoryRegion.new(name: "CODE", start: 0, size: 32, permissions: "rx", programmable: true),
    MemoryRegion.new(name: "DATA", start: 32, size: 32, permissions: "rw")
  ]
)
vm = VM.new(memory_size: 80, memory_bus: bus)
assembler = Assembler.new
assembler.emit(Op::LIT, 0x1234_5678)
assembler.emit(Op::LIT, 32)
assembler.emit(Op::STORE)
assembler.emit(Op::LIT, 32)
assembler.emit(Op::FETCH)
assembler.emit(Op::HALT)
program = assembler.build
vm.load(program)
stack = vm.run

result = {
  stack: stack,
  steps: vm.steps,
  code_hex: bus.region_bytes("CODE").byteslice(0, program.bytesize).unpack1("H*"),
  data_hex: bus.region_bytes("DATA").byteslice(0, 4).unpack1("H*"),
  code_write_fault: faulted { bus.write_u8(0, 0) },
  data_fetch_fault: faulted { bus.fetch_u8(32) },
  boundary_fault: faulted { bus.read(30, 4) },
  unmapped_fault: faulted { bus.read_u8(64) }
}
puts JSON.generate(result)
