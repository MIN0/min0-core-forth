# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_linker"

def make_linker_fixture
  components = {
    code: [0x1004, 0x3000, 0xDEADBEEF].pack("V3"),
    dictionary: [0x1000].pack("V"),
    data: [0x11223344].pack("V")
  }
  source_bases = { code: 0x1000, dictionary: 0x2000, data: 0x3000 }
  target_bases = { code: 0x4000, dictionary: 0x5000, data: 0x6000 }
  manifest = Min0CoreForth::Linker.build_manifest(
    [
      { section: "code", offset: 0, target: "code", width: 4, kind: "call" },
      { section: "code", offset: 4, target: "data", width: 4, kind: "data-literal" },
      { section: "dictionary", offset: 0, target: "code", width: 4, kind: "colon-code" }
    ]
  )
  [components, source_bases, target_bases, manifest]
end

def rejected_link(name)
  components, source_bases, target_bases, manifest = make_linker_fixture
  yield components, source_bases, target_bases, manifest
  before_components = Marshal.load(Marshal.dump(components))
  before_manifest = Marshal.load(Marshal.dump(manifest))
  begin
    Min0CoreForth::Linker.link_components(components, source_bases, target_bases, manifest)
  rescue Min0CoreForth::LinkError
    raise "#{name} mutated its inputs" unless components == before_components && manifest == before_manifest

    return name
  end
  raise "#{name} was accepted"
end

def run_linker_validation_demo(implementation = "ruby")
  components, source_bases, target_bases, manifest = make_linker_fixture
  before = Marshal.load(Marshal.dump(components))
  linked = Min0CoreForth::Linker.link_components(components, source_bases, target_bases, manifest)
  raise "successful link mutated source components" unless components == before

  rejected = [
    rejected_link("version") { |_c, _s, _t, m| m[:version] = 2 },
    rejected_link("section") { |_c, _s, _t, m| m[:records][0][:section] = "unknown" },
    rejected_link("width") { |_c, _s, _t, m| m[:records][0][:width] = 8 },
    rejected_link("offset") { |_c, _s, _t, m| m[:records][0][:offset] = 99 },
    rejected_link("overlap") do |_c, _s, _t, m|
      m[:records] << { section: "code", offset: 2, target: "code", width: 4, kind: "overlap" }
    end,
    rejected_link("pointer") { |c, _s, _t, _m| c[:code][0, 4] = [0].pack("V") },
    rejected_link("target-overlap") { |_c, _s, t, _m| t[:dictionary] = 0x4008 },
    rejected_link("overflow") { |_c, _s, t, _m| t[:code] = 0xFFFFFFFC },
    rejected_link("kind") { |_c, _s, _t, m| m[:records][0][:kind] = "" }
  ]
  {
    implementation: implementation,
    record_count: manifest[:records].length,
    source_unchanged: components == before,
    code_hex: linked.fetch("code").unpack1("H*"),
    dictionary_hex: linked.fetch("dictionary").unpack1("H*"),
    data_hex: linked.fetch("data").unpack1("H*"),
    rejected: rejected
  }
end

puts JSON.generate(run_linker_validation_demo) if $PROGRAM_NAME == __FILE__
