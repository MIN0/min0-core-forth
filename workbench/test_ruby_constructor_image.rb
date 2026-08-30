# frozen_string_literal: true

require_relative "constructor_image_fixture"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def assert_error(error_class, message, name)
  yield
  raise "#{name}: expected #{error_class}"
rescue error_class => error
  raise "#{name}: #{error.message.inspect} does not include #{message.inspect}" unless error.message.include?(message)

  puts "#{name}: PASS"
end

envelope = build_envelope
result = load_envelope(envelope)
assert_equal(1, result[:plan_version], "round-trip plan version")
assert_equal([2, 3, 4, 0], result[:actions], "round-trip actions")
assert_equal([0x8000], result[:stack], "round-trip stack")
assert_equal("ab000000", result[:body_hex], "round-trip body")
assert_equal(0x8004, result[:data_here], "round-trip data HERE")

bad_transport = build_envelope
bad_transport["version"] = 2
assert_error(RuntimeError, "version", "transport version") { load_envelope(bad_transport) }

bad_plan = build_envelope
headers = [bad_plan["dictionary_hex"]].pack("H*")
offset = bad_plan["record_plan"] - bad_plan["dictionary_base"] + 4
headers[offset, 4] = [2].pack("V")
bad_plan["dictionary_hex"] = headers.unpack1("H*")
assert_error(Min0CoreForth::InvalidDictionary, "plan version", "embedded plan version") do
  load_envelope(bad_plan)
end

vm, dictionary = make_image_system
vm.load([bad_plan["code_hex"]].pack("H*"), address: bad_plan["code_base"])
assert_error(Min0CoreForth::InvalidDictionary, "plan version", "component rollback rejection") do
  dictionary.load_images(headers, latest: bad_plan["latest"], body_image: "".b)
end
assert_equal(dictionary.base, dictionary.here, "component rollback HERE")
assert_equal(0, dictionary.latest, "component rollback LATEST")
assert_equal(dictionary.body_base, dictionary.data_here, "component rollback data HERE")
assert_equal("\0" * headers.bytesize, vm.read_bytes(dictionary.base, headers.bytesize), "component rollback bytes")

_vm, dictionary = make_image_system
dictionary.add_created("EXISTING")
assert_error(Min0CoreForth::DictionaryError, "empty dictionary", "nonempty loader rejection") do
  dictionary.load_images([envelope["dictionary_hex"]].pack("H*"), latest: envelope["latest"])
end

bad_hex = build_envelope
bad_hex["code_hex"] = "0Z"
assert_error(RuntimeError, "hex", "invalid hex rejection") { load_envelope(bad_hex) }

puts "PASS: Ruby constructor-image component tests completed"
