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

Tempfile.create(["min0-cli-for", ".fth"], encoding: "UTF-8") do |source|
  source.write("3 FOR I . NEXT")
  source.flush
  stdout, stderr, status = Open3.capture3(
    "ruby", File.join(__dir__, "min0_forth.rb"), "-z", source.path
  )
  assert_cli(status.success?, "Ruby direct FOR exit")
  assert_cli(stdout == "012", "Ruby direct FOR output")
  assert_cli(stderr.empty?, "Ruby direct FOR stderr")
end

Tempfile.create(["min0-cli-for-error", ".fth"], encoding: "UTF-8") do |source|
  source.write("3 FOR I")
  source.flush
  stdout, stderr, status = Open3.capture3(
    "ruby", File.join(__dir__, "min0_forth.rb"), "-z", source.path
  )
  assert_cli(!status.success?, "Ruby unfinished FOR exit")
  assert_cli(stdout.empty?, "Ruby unfinished FOR output")
  assert_cli(stderr.include?("matching NEXT"), "Ruby unfinished FOR message")
end

Tempfile.create(["min0-cli-compiled-output", ".fth"], encoding: "UTF-8") do |source|
  source.write(': CORE-OUT 65 EMIT CR -42 . S" ABC" TYPE ; CORE-OUT')
  source.flush
  stdout, stderr, status = Open3.capture3(
    "ruby", File.join(__dir__, "min0_forth.rb"), "-z", source.path
  )
  assert_cli(status.success?, "Ruby compiled output exit")
  assert_cli(stdout == "A\n-42ABC", "Ruby compiled output bytes")
  assert_cli(stderr.empty?, "Ruby compiled output stderr")
end

Tempfile.create(["min0-cli-direct-control", ".fth"], encoding: "UTF-8") do |source|
  source.write("1 IF\n5 2 DO I . LOOP\nELSE 99 . THEN")
  source.flush
  stdout, stderr, status = Open3.capture3(
    "ruby", File.join(__dir__, "min0_forth.rb"), "-z", source.path
  )
  assert_cli(status.success?, "Ruby direct mixed-control exit")
  assert_cli(stdout == "234", "Ruby direct mixed-control output")
  assert_cli(stderr.empty?, "Ruby direct mixed-control stderr")
end

puts "PASS: Ruby host CLI tests completed"
