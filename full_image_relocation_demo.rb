# frozen_string_literal: true

require "json"
require_relative "code_relocation_demo"
require_relative "constructor_relocation_demo"
require_relative "min0_core_forth_linker"

def run_full_image_relocation_demo(implementation = "ruby")
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(SOURCE)

  code_records = outer.relocation_manifest
  dictionary_records = collect_dictionary_relocations(vm, dictionary)
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
  components = {
    code: vm.read_bytes(
      Min0CoreForth::DEFAULT_CODE_BASE, outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE
    ),
    dictionary: dictionary.image,
    data: dictionary.body_image
  }
  manifest = Min0CoreForth::Linker.build_manifest(code_records + dictionary_records)
  linked = Min0CoreForth::Linker.link_components(components, source_bases, target_bases, manifest)

  bus = Min0CoreForth::RegionMemory.new(
    0x11000,
    [
      Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x5000, permissions: "rwx", programmable: true),
      Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x5000, size: 0x4000, permissions: "rw"),
      Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x9000, size: 0x8000, permissions: "rw")
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
  moved_outer = Min0CoreForth::OuterInterpreter.new(
    moved_vm, moved_dictionary, code_base: NEW_CODE_BASE + linked.fetch("code").bytesize
  )
  stack = moved_outer.interpret(
    "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"
  )
  answer = moved_dictionary.find("ANSWER")
  slot = moved_dictionary.find("SLOT")
  answer_body, answer_behavior = moved_dictionary.read_does_descriptor(answer)
  {
    implementation: implementation,
    source_bases: [Min0CoreForth::DEFAULT_CODE_BASE, dictionary.base, dictionary.body_base],
    moved_bases: [NEW_CODE_BASE, NEW_DICTIONARY_BASE, NEW_DATA_BASE],
    manifest_records: manifest.fetch(:records).length,
    code_relocations: code_records.length,
    dictionary_relocations: dictionary_records.length,
    code_targets: ["code", "dictionary", "data"].to_h do |target|
      [target, code_records.count { |record| record[:target] == target }]
    end,
    dictionary_targets: ["code", "dictionary", "data"].to_h do |target|
      [target, dictionary_records.count { |record| record[:target] == target }]
    end,
    stack: stack,
    slot: slot.payload,
    answer_body: answer_body,
    answer_behavior: answer_behavior,
    answer_value: moved_vm.read_cell(answer_body),
    code_here: NEW_CODE_BASE + linked.fetch("code").bytesize,
    header_here: moved_dictionary.here,
    data_here: moved_dictionary.data_here
  }
end

puts JSON.generate(run_full_image_relocation_demo) if $PROGRAM_NAME == __FILE__
