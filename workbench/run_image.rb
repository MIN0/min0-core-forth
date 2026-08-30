# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_vm"

abort "usage: ruby run_image.rb IMAGE" unless ARGV.length == 1

vm = Min0CoreForth::VM.new
vm.load(File.binread(ARGV.fetch(0)))
stack = vm.run
puts JSON.generate({ stack: stack, steps: vm.steps })
