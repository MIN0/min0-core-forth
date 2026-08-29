# frozen_string_literal: true

require_relative "w_x_publish_demo"

result = run_w_x_publish_demo
raise "staging is not rw" unless result[:staging_permissions] == "rw"
raise "runtime is not sealed rx" unless result[:runtime_permissions] == "rx" && result[:runtime_sealed]
raise "runtime remains programmable" if result[:runtime_programmable]
raise "published image did not execute" unless result[:stack] == [7, 5]
raise "staging was not detached" unless result[:staging_changed_after_publish] && result[:runtime_unchanged_after_staging_change]
raise "W^X rejection matrix failed" unless result[:rejected].values.all?

puts "rw,nx staging to sealed rx runtime: PASS"
puts "detached staging mutation: PASS"
puts "PASS: Ruby W^X publication tests completed"
