# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_compiler"

abort "usage: ruby run_source.rb SOURCE [IMAGE]" unless (1..2).cover?(ARGV.length)

image = Min0CoreForth::Compiler.compile(File.read(ARGV.fetch(0), encoding: "UTF-8"))
File.binwrite(ARGV.fetch(1), image) if ARGV[1]
vm = Min0CoreForth::VM.new
vm.load(image)
stack = vm.run
puts JSON.generate({ stack: stack, steps: vm.steps, image_bytes: image.bytesize })
