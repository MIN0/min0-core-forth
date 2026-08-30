# frozen_string_literal: true

require "open3"
require "tempfile"

def assert_cli(condition, name)
  raise name unless condition

  puts "#{name}: PASS"
end

Tempfile.create(["min0-cli", ".fth"], encoding: "UTF-8") do |source|
  source.write(': GREET ." Hello" ; GREET')
  source.flush
  stdout, stderr, status = Open3.capture3(
    "ruby", File.join(__dir__, "min0_forth.rb"), "-z", source.path
  )
  assert_cli(status.success?, "Ruby quiet exit")
  assert_cli(stdout == "Hello", "Ruby quiet exact output")
  assert_cli(stderr.empty?, "Ruby quiet stderr")
end

Tempfile.create(["min0-cli-error", ".fth"], encoding: "UTF-8") do |source|
  source.write("MISSING")
  source.flush
  stdout, stderr, status = Open3.capture3(
    "ruby", File.join(__dir__, "min0_forth.rb"), "-z", source.path
  )
  assert_cli(!status.success?, "Ruby quiet error exit")
  assert_cli(stdout.empty?, "Ruby quiet error output")
  assert_cli(stderr.include?("ERROR UnknownWord"), "Ruby quiet error message")
end

puts "PASS: Ruby host CLI tests completed"
