# frozen_string_literal: true

require "digest"
require "json"
require_relative "constructor_image_fixture"

SOURCE = <<~FORTH
  VARIABLE SLOT
  99 CONSTANT MARK
  : INC 1 + ;
  : CHOOSE IF 1 INC ELSE MARK THEN ;
  : SPIN BEGIN DUP 3 < WHILE INC REPEAT ;
  : SUM 0 3 0 DO I + LOOP ;
  : SKIP 0 3 0 ?DO I 1 = IF LEAVE THEN I + LOOP ;
  : STEP 0 4 0 DO I + 2 +LOOP ;
  : VALUE: CREATE , DOES> @ ;
  7 VALUE: ANSWER
  : READ-ANSWER ANSWER ;
  : SLOT-ADDR SLOT ;
FORTH

def run_code_relocation_demo(implementation = "ruby")
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(SOURCE)
  manifest = outer.relocation_manifest
  canonical = manifest.map do |record|
    [record[:section], record[:offset], record[:target], record[:width], record[:kind]].join(":")
  end.join(";")
  kind_counts = manifest.map { |record| record[:kind] }.tally.sort.to_h
  stack = outer.interpret("0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR")
  answer_body, = dictionary.read_does_descriptor(dictionary.find("ANSWER"))
  {
    implementation: implementation,
    manifest: manifest,
    manifest_sha256: Digest::SHA256.hexdigest(canonical),
    kind_counts: kind_counts,
    target_counts: ["code", "dictionary", "data"].to_h do |target|
      [target, manifest.count { |record| record[:target] == target }]
    end,
    code_base: Min0CoreForth::DEFAULT_CODE_BASE,
    code_here: outer.code_here,
    code_hex: vm.read_bytes(
      Min0CoreForth::DEFAULT_CODE_BASE, outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE
    ).unpack1("H*"),
    stack: stack,
    slot: dictionary.find("SLOT").payload,
    answer: answer_body
  }
end

puts JSON.generate(run_code_relocation_demo) if $PROGRAM_NAME == __FILE__
