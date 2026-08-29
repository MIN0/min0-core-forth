# frozen_string_literal: true

require "digest"
require "json"
require_relative "constructor_image_fixture"

NEW_CODE_BASE = 0x2000
NEW_DICTIONARY_BASE = 0x5000
NEW_DATA_BASE = 0x9000

def collect_dictionary_relocations(vm, dictionary)
  records = []
  add = lambda do |cell_address, target, kind|
    records << {
      section: "dictionary",
      offset: cell_address - dictionary.base,
      target: target,
      width: 4,
      kind: kind
    }
  end

  dictionary.entries.each do |entry|
    add.call(entry.header_address, "dictionary", "dictionary-link") unless entry.link.zero?
    case entry.kind
    when Min0CoreForth::KIND_COLON
      add.call(entry.xt + 4, "code", "colon-code")
    when Min0CoreForth::KIND_VARIABLE, Min0CoreForth::KIND_CREATED
      add.call(entry.xt + 4, "data", "data-body")
    when Min0CoreForth::KIND_DEFER
      add.call(entry.xt + 4, "dictionary", "defer-target-xt") unless entry.payload.zero?
    when Min0CoreForth::KIND_DOES, Min0CoreForth::KIND_DEFINER
      add.call(entry.xt + 4, "dictionary", "descriptor")
    end

    if entry.kind == Min0CoreForth::KIND_DOES
      descriptor = entry.payload
      add.call(descriptor, "data", "does-body")
      add.call(descriptor + 4, "code", "does-behavior")
    elsif entry.kind == Min0CoreForth::KIND_DEFINER
      descriptor = entry.payload
      plan, behavior = dictionary.read_definer_descriptor(entry)
      add.call(descriptor, "dictionary", "constructor-plan")
      add.call(descriptor + 4, "code", "definer-behavior") unless behavior.zero?
      count = vm.read_cell(plan + 8)
      count.times do |index|
        add.call(plan + 12 + index * 8, "code", "constructor-segment")
      end
    end
  end
  records.sort_by { |record| record[:offset] }
end

def run_relocation_demo(implementation = "ruby")
  envelope = build_envelope
  vm, dictionary = make_image_system
  vm.load([envelope["code_hex"]].pack("H*"), address: envelope["code_base"])
  dictionary.load_images(
    [envelope["dictionary_hex"]].pack("H*"),
    latest: envelope["latest"],
    body_image: [envelope["body_hex"]].pack("H*")
  )
  records = collect_dictionary_relocations(vm, dictionary)
  deltas = {
    "code" => NEW_CODE_BASE - envelope["code_base"],
    "dictionary" => NEW_DICTIONARY_BASE - envelope["dictionary_base"],
    "data" => NEW_DATA_BASE - envelope["body_base"]
  }
  headers = [envelope["dictionary_hex"]].pack("H*")
  records.each do |record|
    offset = record[:offset]
    old_value = headers.byteslice(offset, 4).unpack1("V")
    headers[offset, 4] = [old_value + deltas.fetch(record[:target])].pack("V")
  end

  bus = Min0CoreForth::RegionMemory.new(
    0x11000,
    [
      Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x5000, permissions: "rwx", programmable: true),
      Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x5000, size: 0x4000, permissions: "rw"),
      Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x9000, size: 0x8000, permissions: "rw")
    ]
  )
  moved_vm = Min0CoreForth::VM.new(memory_size: 0x11000, memory_bus: bus)
  code = [envelope["code_hex"]].pack("H*")
  moved_vm.load(code, address: NEW_CODE_BASE)
  moved_dictionary = Min0CoreForth::RuntimeDictionary.new(
    moved_vm,
    base: NEW_DICTIONARY_BASE,
    limit: NEW_DATA_BASE,
    body_base: NEW_DATA_BASE,
    body_limit: 0x11000
  )
  moved_latest = envelope["latest"] + deltas["dictionary"]
  moved_dictionary.load_images(headers, latest: moved_latest)
  moved_code_here = NEW_CODE_BASE + code.bytesize
  moved_outer = Min0CoreForth::OuterInterpreter.new(moved_vm, moved_dictionary, code_base: moved_code_here)
  stack = moved_outer.interpret("2 0x1AB RECORD: ITEM ITEM")
  record = moved_dictionary.find("RECORD:")
  item = moved_dictionary.find("ITEM")
  plan, = moved_dictionary.read_definer_descriptor(record)
  actions = moved_dictionary.read_constructor_plan(record).map(&:last)
  canonical_manifest = records.map { |entry| "#{entry[:offset]}:#{entry[:target]}" }.join(";")
  target_counts = ["code", "dictionary", "data"].to_h do |target|
    [target, records.count { |record_entry| record_entry[:target] == target }]
  end
  {
    implementation: implementation,
    source_bases: [envelope["code_base"], envelope["dictionary_base"], envelope["body_base"]],
    moved_bases: [NEW_CODE_BASE, NEW_DICTIONARY_BASE, NEW_DATA_BASE],
    deltas: [deltas["code"], deltas["dictionary"], deltas["data"]],
    relocation_count: records.length,
    target_counts: target_counts,
    manifest_sha256: Digest::SHA256.hexdigest(canonical_manifest),
    plan: plan,
    actions: actions,
    stack: stack,
    item_body: item.payload,
    body_hex: moved_vm.read_bytes(item.payload, 4).unpack1("H*"),
    data_here: moved_dictionary.data_here
  }
end

puts JSON.generate(run_relocation_demo) if $PROGRAM_NAME == __FILE__
