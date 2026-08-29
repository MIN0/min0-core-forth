# frozen_string_literal: true

require_relative "min0_core_forth_dictionary"
require_relative "min0_core_forth_outer"

MIN0_FORTH_VERSION = File.read(File.join(__dir__, "VERSION"), encoding: "UTF-8").strip
MIN0_FORTH_BANNER = "MIN0 CORE FORTH #{MIN0_FORTH_VERSION} - educational and experimental reference"

def make_min0_host
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  Min0CoreForth::OuterInterpreter.new(vm, dictionary)
end

def write_new_min0_output(outer, start)
  fragments = outer.output[start..] || []
  unless fragments.empty?
    $stdout.write(fragments.join)
    $stdout.flush
  end
  outer.output.length
end

def run_min0_file(path, quiet:)
  outer = make_min0_host
  begin
    outer.interpret(File.read(path, encoding: "UTF-8"))
  rescue StandardError => e
    warn "ERROR #{e.class.name.split('::').last}: #{e.message}"
    return 1
  end
  puts MIN0_FORTH_BANNER unless quiet
  write_new_min0_output(outer, 0)
  unless quiet
    puts if !outer.output.empty? && !outer.terminal_text.end_with?("\n")
    puts "DATA stack: #{outer.vm.data_stack.inspect}"
  end
  0
end

def run_min0_repl
  outer = make_min0_host
  output_index = 0
  puts MIN0_FORTH_BANNER
  puts "Type BYE or EXIT to leave. Output bytes are emitted by the program."
  loop do
    $stdout.write("ok> ")
    $stdout.flush
    source = $stdin.gets
    if source.nil?
      puts
      return 0
    end
    return 0 if %w[BYE EXIT].include?(source.strip.upcase)

    begin
      outer.interpret(source)
      output_index = write_new_min0_output(outer, output_index)
      puts if !outer.output.empty? && !outer.terminal_text.end_with?("\n")
      puts " ok #{outer.vm.data_stack.inspect}"
    rescue StandardError => e
      warn "ERROR #{e.class.name.split('::').last}: #{e.message}"
    end
  end
end

def min0_usage
  "usage: ruby min0_forth.rb [SOURCE] | -z SOURCE | --version"
end

exit_code = case ARGV
            in ["--version"]
              puts MIN0_FORTH_VERSION
              0
            in ["-z" | "--quiet-source", path]
              run_min0_file(path, quiet: true)
            in [path]
              run_min0_file(path, quiet: false)
            in []
              run_min0_repl
            else
              warn min0_usage
              2
            end
exit exit_code
