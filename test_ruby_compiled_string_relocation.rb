# frozen_string_literal: true

require_relative "compiled_string_relocation_demo"

result = run_compiled_string_relocation_demo
raise "string relocation target failed" unless result[:relocation][:target] == "data"
raise "string relocation kind failed" unless result[:relocation][:kind] == "string-address"
raise "string address was not relocated" unless result[:address] == result[:moved_data_base]
raise "string address stayed at source" if result[:address] == result[:source_data_base]
raise "relocated length failed" unless result[:length] == 9
raise "relocated bytes failed" unless result[:text_hex] == "Relocated".b.unpack1("H*")
raise "read-only TYPE output failed" unless result[:terminal_text] == "Relocated"
raise "DATA permission failed" unless result[:data_permissions] == "r"
raise "DATA seal failed" unless result[:read_only_sealed]
raise "read-only rejection matrix failed" unless result[:rejected].values.all?

puts "PASS: Ruby compiled-string relocation tests completed"
