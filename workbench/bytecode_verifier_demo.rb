# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_verify"

BYTECODE_VERIFY_BASES = { code: 0x1000, dictionary: 0x4000, data: 0x8000 }.freeze

def verifier_components(code, dictionary = "".b)
  { code: code.b, dictionary: dictionary.b, data: "".b }
end

def verifier_record(section, offset, target, kind)
  { section: section, offset: offset, target: target, width: 4, kind: kind }
end

def verifier_rejected?
  yield
  false
rescue Min0CoreForth::BytecodeVerificationError
  true
end

def run_bytecode_verifier_demo(implementation = "ruby")
  literal_25 = [Min0CoreForth::Op::LIT, 0x25, Min0CoreForth::Op::EXIT].pack("CV C")
  literal_summary = Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
    verifier_components(literal_25),
    BYTECODE_VERIFY_BASES,
    Min0CoreForth::Linker.build_manifest([])
  )

  dset_code = [Min0CoreForth::Op::DSET, 0x4004, Min0CoreForth::Op::EXIT].pack("CV C")
  dset_record = verifier_record("code", 1, "dictionary", "defer-store-slot")
  dset_summary = Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
    verifier_components(dset_code),
    BYTECODE_VERIFY_BASES,
    Min0CoreForth::Linker.build_manifest([dset_record])
  )

  missing_dset_record = verifier_rejected? do
    Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
      verifier_components(dset_code), BYTECODE_VERIFY_BASES,
      Min0CoreForth::Linker.build_manifest([])
    )
  end
  fake_dset_record = verifier_rejected? do
    Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
      verifier_components(literal_25), BYTECODE_VERIFY_BASES,
      Min0CoreForth::Linker.build_manifest([dset_record])
    )
  end
  truncated_operand = verifier_rejected? do
    Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
      verifier_components([Min0CoreForth::Op::CALL, 0, 0].pack("C*")),
      BYTECODE_VERIFY_BASES,
      Min0CoreForth::Linker.build_manifest([])
    )
  end
  invalid_opcode = verifier_rejected? do
    Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
      verifier_components([0xFF].pack("C")), BYTECODE_VERIFY_BASES,
      Min0CoreForth::Linker.build_manifest([])
    )
  end

  branch_code = [
    Min0CoreForth::Op::LIT, 123,
    Min0CoreForth::Op::BRANCH, 0x1002,
    Min0CoreForth::Op::EXIT
  ].pack("CV CV C")
  branch_record = verifier_record("code", 6, "code", "branch")
  branch_into_operand = verifier_rejected? do
    Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
      verifier_components(branch_code), BYTECODE_VERIFY_BASES,
      Min0CoreForth::Linker.build_manifest([branch_record])
    )
  end

  dictionary_pointer = [0x1002].pack("V")
  entry_record = verifier_record("dictionary", 0, "code", "colon-code")
  entry_into_operand = verifier_rejected? do
    Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
      verifier_components(literal_25, dictionary_pointer), BYTECODE_VERIFY_BASES,
      Min0CoreForth::Linker.build_manifest([entry_record])
    )
  end
  {
    implementation: implementation,
    literal_0x25_capabilities: literal_summary[:capabilities],
    literal_instruction_count: literal_summary[:instruction_count],
    dset_capabilities: dset_summary[:capabilities],
    dset_addresses: dset_summary[:dset_addresses],
    rejected: {
      missing_dset_record: missing_dset_record,
      fake_dset_record: fake_dset_record,
      truncated_operand: truncated_operand,
      invalid_opcode: invalid_opcode,
      branch_into_operand: branch_into_operand,
      entry_into_operand: entry_into_operand
    }
  }
end

puts JSON.generate(run_bytecode_verifier_demo) if $PROGRAM_NAME == __FILE__
