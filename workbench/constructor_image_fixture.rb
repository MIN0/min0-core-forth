# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

IMAGE_FORMAT = "min0-core-forth-constructor-audit"
IMAGE_VERSION = 1

def make_image_system
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
  [vm, dictionary]
end

def build_envelope(writer = "ruby")
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(": RECORD: CREATE C, ALLOT ALIGN ;")
  record = dictionary.find("RECORD:")
  plan, = dictionary.read_definer_descriptor(record)
  {
    "format" => IMAGE_FORMAT,
    "version" => IMAGE_VERSION,
    "writer" => writer,
    "memory_size" => 0x10000,
    "code_base" => Min0CoreForth::DEFAULT_CODE_BASE,
    "code_here" => outer.code_here,
    "dictionary_base" => dictionary.base,
    "dictionary_limit" => dictionary.limit,
    "header_here" => dictionary.here,
    "latest" => dictionary.latest,
    "body_base" => dictionary.body_base,
    "body_limit" => dictionary.body_limit,
    "data_here" => dictionary.data_here,
    "record_plan" => plan,
    "code_hex" => vm.read_bytes(Min0CoreForth::DEFAULT_CODE_BASE, outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE).unpack1("H*"),
    "dictionary_hex" => dictionary.image.unpack1("H*"),
    "body_hex" => dictionary.body_image.unpack1("H*")
  }
end

def require_integer(envelope, name, expected = nil)
  value = envelope[name]
  raise "constructor image field #{name} must be an integer" unless value.is_a?(Integer)
  if !expected.nil? && value != expected
    raise "constructor image field #{name} is unsupported"
  end
  value
end

def load_envelope(envelope, reader = "ruby")
  raise "unsupported constructor image format" unless envelope["format"] == IMAGE_FORMAT

  require_integer(envelope, "version", IMAGE_VERSION)
  require_integer(envelope, "memory_size", 0x10000)
  code_base = require_integer(envelope, "code_base", Min0CoreForth::DEFAULT_CODE_BASE)
  code_here = require_integer(envelope, "code_here")
  dictionary_base = require_integer(envelope, "dictionary_base", 0x4000)
  require_integer(envelope, "dictionary_limit", 0x8000)
  header_here = require_integer(envelope, "header_here")
  latest = require_integer(envelope, "latest")
  body_base = require_integer(envelope, "body_base", 0x8000)
  require_integer(envelope, "body_limit", 0x10000)
  data_here = require_integer(envelope, "data_here")
  record_plan = require_integer(envelope, "record_plan")
  decode_hex = lambda do |name|
    value = envelope[name]
    unless value.is_a?(String) && value.bytesize.even? && value.match?(/\A[0-9a-f]*\z/)
      raise "constructor image contains invalid hex data"
    end
    [value].pack("H*")
  end
  code = decode_hex.call("code_hex")
  headers = decode_hex.call("dictionary_hex")
  body = decode_hex.call("body_hex")
  raise "constructor image CODE length disagrees with code HERE" unless code_here - code_base == code.bytesize
  unless header_here - dictionary_base == headers.bytesize
    raise "constructor image DICTIONARY length disagrees with header HERE"
  end
  raise "constructor image DATA length disagrees with data HERE" unless data_here - body_base == body.bytesize

  vm, dictionary = make_image_system
  vm.load(code, address: code_base)
  dictionary.load_images(headers, latest: latest, body_image: body)
  unless dictionary.here == header_here && dictionary.data_here == data_here
    raise "constructor image allocator state did not restore"
  end
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary, code_base: code_here)
  record = dictionary.find("RECORD:")
  raise "constructor image has no RECORD: definer" if record.nil?

  plan, behavior = dictionary.read_definer_descriptor(record)
  raise "constructor image RECORD: metadata disagrees" unless plan == record_plan && behavior.zero?

  actions = dictionary.read_constructor_plan(record).map(&:last)
  stack = outer.interpret("2 0x1AB RECORD: ITEM ITEM")
  item = dictionary.find("ITEM")
  {
    reader: reader,
    source_writer: envelope["writer"],
    plan_version: vm.read_cell(plan + 4),
    actions: actions,
    stack: stack,
    item_body: item.payload,
    body_hex: vm.read_bytes(item.payload, 4).unpack1("H*"),
    data_here: dictionary.data_here
  }
end

if $PROGRAM_NAME == __FILE__
  abort "usage: ruby constructor_image_fixture.rb MODE IMAGE" unless ARGV.length == 2

  mode, image_path = ARGV
  case mode
  when "write"
    envelope = build_envelope
    raw = JSON.generate(envelope.sort.to_h) + "\n"
    File.write(image_path, raw, mode: "wb")
    result = { writer: "ruby", bytes: raw.bytesize, sha256: Digest::SHA256.hexdigest(raw) }
  when "read"
    result = load_envelope(JSON.parse(File.binread(image_path)))
  else
    abort "mode must be write or read"
  end
  puts JSON.generate(result)
end
