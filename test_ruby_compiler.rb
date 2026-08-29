# frozen_string_literal: true

require_relative "min0_core_forth_compiler"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def run_source(source)
  vm = Min0CoreForth::VM.new
  vm.load(Min0CoreForth::Compiler.compile(source))
  vm.run
end

assert_equal(
  [25, 14],
  run_source(": SQUARE DUP * ; : DOUBLE DUP + ; 5 SQUARE 7 DOUBLE"),
  "colon definitions"
)
assert_equal([18], run_source(": double dup + ; 9 DoUbLe"), "case insensitive")
assert_equal([42], run_source(": A B ; : B 41 1 + ; A"), "forward reference")
assert_equal([32], run_source("0x10 \\ ignored\n 2 *"), "comment and hex literal")

begin
  Min0CoreForth::Compiler.compile("MISSING")
  raise "unknown word: expected CompileError"
rescue Min0CoreForth::CompileError
  puts "unknown word: PASS"
end

begin
  Min0CoreForth::Compiler.compile(": BAD 1 2 +")
  raise "unterminated definition: expected CompileError"
rescue Min0CoreForth::CompileError
  puts "unterminated definition: PASS"
end

puts "PASS: Ruby compiler tests completed"
