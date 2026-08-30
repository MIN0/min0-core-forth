# frozen_string_literal: true

require_relative "image_execution_profile_demo"

result = run_image_execution_profile_demo
checks = {
  "safe profile" => result[:safe_image_profile] == "safe-runtime",
  "build profile" => result[:build_image_profile] == "standard-build",
  "compiled DSET evidence" => result[:build_has_defer_store_record],
  "safe verifier capability" => result[:safe_verified_capabilities] == [],
  "build verifier capability" => result[:build_verified_capabilities] == ["compiled-defer-store"],
  "build verifier instructions" => result[:build_verified_instruction_count].positive?,
  "safe loader rejects" => result[:safe_loader_rejected_before_write],
  "rejection precedes write" => result[:inactive_slot_untouched],
  "build loader installs" => result[:standard_build_installed_slot] == "B",
  "profile tamper rejected" => result[:profile_tamper_rejected],
  "recovery remains safe" => result[:standard_build_recovery_rejected]
}
checks.each do |name, passed|
  raise "#{name}: FAIL" unless passed

  puts "#{name}: PASS"
end
puts "PASS: Ruby image execution-profile tests completed"
