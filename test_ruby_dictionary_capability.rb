# frozen_string_literal: true

require_relative "dictionary_capability_demo"

result = run_dictionary_capability_demo
raise "DICTIONARY permission changed unexpectedly" unless result[:dictionary_permissions] == "rw"
raise "DICTIONARY is not protected" unless result[:dictionary_write_protected]
raise "runtime structure is not sealed" unless result[:runtime_structure_sealed]
raise "DATA write stopped working" unless result[:data_value] == 123
raise "Monitor DEFER switch failed" unless result[:defer_value_after_monitor] == 9
raise "Monitor changed non-DEFER bytes" unless result[:monitor_changed_only_defer_slot]
raise "rejected attacks changed dictionary" unless result[:attacks_left_dictionary_unchanged]
raise "dictionary rejection matrix failed" unless result[:rejected].values.all?

puts "sealed DICTIONARY structure: PASS"
puts "DATA write and Monitor DEFER gate: PASS"
puts "PASS: Ruby dictionary capability tests completed"
