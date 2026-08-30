# frozen_string_literal: true

require "json"
require_relative "constructor_image_fixture"
require_relative "constructor_relocation_demo"
require_relative "min0_core_forth_linker"

def run_compiled_string_relocation_demo(implementation = "ruby")
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(': MESSAGE S" Relocated" ;')

  string_record = outer.relocation_manifest.find { |record| record[:kind] == "string-address" }
  records = outer.relocation_manifest + collect_dictionary_relocations(vm, dictionary)
  components = {
    code: vm.read_bytes(
      Min0CoreForth::DEFAULT_CODE_BASE,
      outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE
    ),
    dictionary: dictionary.image,
    data: dictionary.body_image
  }
  source_bases = {
    code: Min0CoreForth::DEFAULT_CODE_BASE,
    dictionary: dictionary.base,
    data: dictionary.body_base
  }
  target_bases = {
    code: NEW_CODE_BASE,
    dictionary: NEW_DICTIONARY_BASE,
    data: NEW_DATA_BASE
  }
  manifest = Min0CoreForth::Linker.build_manifest(records)
  linked = Min0CoreForth::Linker.link_components(components, source_bases, target_bases, manifest)

  data_region = Min0CoreForth::MemoryRegion.new(
    name: "DATA", start: NEW_DATA_BASE, size: 0x8000, permissions: "rw"
  )
  bus = Min0CoreForth::RegionMemory.new(
    0x11000,
    [
      Min0CoreForth::MemoryRegion.new(
        name: "CODE", start: 0, size: 0x5000, permissions: "rwx", programmable: true
      ),
      Min0CoreForth::MemoryRegion.new(
        name: "DICTIONARY", start: NEW_DICTIONARY_BASE, size: 0x4000, permissions: "rw"
      ),
      data_region
    ]
  )
  moved_vm = Min0CoreForth::VM.new(memory_size: 0x11000, memory_bus: bus)
  moved_vm.load(linked.fetch("code"), address: NEW_CODE_BASE)
  moved_dictionary = Min0CoreForth::RuntimeDictionary.new(
    moved_vm,
    base: NEW_DICTIONARY_BASE,
    limit: NEW_DATA_BASE,
    body_base: NEW_DATA_BASE,
    body_limit: 0x11000
  )
  moved_dictionary.load_images(
    linked.fetch("dictionary"),
    latest: dictionary.latest + NEW_DICTIONARY_BASE - dictionary.base,
    body_image: linked.fetch("data")
  )
  bus.seal_read_only_region("DATA")
  moved_outer = Min0CoreForth::OuterInterpreter.new(
    moved_vm,
    moved_dictionary,
    code_base: NEW_CODE_BASE + linked.fetch("code").bytesize
  )
  stack = moved_outer.interpret("MESSAGE")
  address, length = stack
  raw = moved_vm.read_bytes(address, length)
  moved_outer.interpret("TYPE")

  operations = {
    write: -> { moved_vm.write_u8(address, 0) },
    program: -> { bus.program(address, "X".b) },
    clear: -> { bus.clear }
  }
  rejected = operations.to_h do |name, operation|
    denied = false
    begin
      operation.call
    rescue Min0CoreForth::MemoryFault
      denied = true
    end
    [name, denied]
  end

  {
    implementation: implementation,
    relocation: string_record,
    source_data_base: dictionary.body_base,
    moved_data_base: NEW_DATA_BASE,
    address: address,
    length: length,
    text_hex: raw.unpack1("H*"),
    terminal_text: moved_outer.terminal_text,
    data_permissions: data_region.permissions,
    read_only_sealed: data_region.read_only_sealed?,
    rejected: rejected
  }
end

puts JSON.generate(run_compiled_string_relocation_demo) if $PROGRAM_NAME == __FILE__
