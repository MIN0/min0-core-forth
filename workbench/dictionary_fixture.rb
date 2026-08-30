# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_dictionary"

abort "usage: ruby dictionary_fixture.rb IMAGE" unless ARGV.length == 1

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
dictionary.add_primitive("DUP", Min0CoreForth::Op::DUP)
dictionary.add_primitive("*", Min0CoreForth::Op::MUL)
dictionary.add_colon("SQUARE", 0x120)
dictionary.add_primitive("IMM", Min0CoreForth::Op::NOP, immediate: true)
entries = dictionary.entries.map do |entry|
  {
    name: entry.name,
    header: entry.header_address,
    link: entry.link,
    flags: entry.flags,
    xt: entry.xt,
    kind: entry.kind,
    payload: entry.payload,
    immediate: entry.immediate?,
    hidden: entry.hidden?
  }
end
File.binwrite(ARGV.fetch(0), dictionary.image)
puts JSON.generate(
  {
    base: dictionary.base,
    here: dictionary.here,
    latest: dictionary.latest,
    bytes: dictionary.image.bytesize,
    entries: entries
  }
)
