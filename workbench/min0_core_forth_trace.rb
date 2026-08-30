# frozen_string_literal: true

module Min0CoreForth
  TRACE_FORMAT = "min0-core-forth-trace/0.1"
  TRACE_PAYLOAD_ROLE = "observed-data-not-instructions"

  def self.trace_hex(address)
    format("0x%08X", address)
  end

  def self.explain_trace_event(event, details)
    case event
    when "definer.compile.complete"
      "#{details[:word]} のconstructor planを辞書へ公開しました。"
    when "definer.execute.begin"
      "定義ワード #{details[:word]} が子 #{details[:child]} の生成を開始しました。"
    when "child.create.hidden"
      "#{details[:child]} をhidden状態で作成しました。"
    when "constructor.segment.begin"
      "constructorのCODE断片 #{trace_hex(details[:code_address])} を実行します。"
    when "constructor.segment.end"
      "constructorのCODE断片 #{trace_hex(details[:code_address])} が終了しました。"
    when "constructor.comma"
      "DATAアドレス#{trace_hex(details[:address])}へ#{details[:value]}を保存し、" \
        "data HEREを#{trace_hex(details[:data_here_after])}へ進めました。"
    when "constructor.c_comma"
      "DATAアドレス#{trace_hex(details[:address])}へ1バイト値#{details[:value]}を保存し、" \
        "data HEREを#{trace_hex(details[:data_here_after])}へ進めました。"
    when "constructor.allot"
      "DATAアドレス#{trace_hex(details[:address])}から#{details[:count]}バイトを予約し、" \
        "data HEREを#{trace_hex(details[:data_here_after])}へ進めました。"
    when "constructor.align"
      "data HERE #{trace_hex(details[:address_before])}へ#{details[:padding]}バイトの" \
        "paddingを入れ、#{trace_hex(details[:data_here_after])}へ整列しました。"
    when "child.does.attach"
      "#{details[:child]} のbody #{trace_hex(details[:body])} とbehavior " \
        "#{trace_hex(details[:behavior])}を接続しました。"
    when "child.publish"
      "完成した #{details[:child]} のhidden状態を解除して公開しました。"
    when "definer.execute.end"
      "#{details[:child]} の生成が正常に完了しました。"
    when "definer.execute.rollback"
      "#{details[:child]} の生成中に#{details[:error]}が発生したため、" \
        "辞書とスタックを開始前へ戻しました。"
    when "does.execute.begin"
      "#{details[:word]} がbody #{trace_hex(details[:body])}を積み、" \
        "behavior #{trace_hex(details[:behavior])}を開始します。"
    when "does.execute.end"
      "#{details[:word]} のDOES behaviorが終了しました。"
    else
      "#{event} が発生しました。"
    end
  end

  class TraceRecorder
    attr_reader :implementation, :events

    def initialize(implementation)
      @implementation = implementation
      @events = []
    end

    def emit(vm, dictionary, event, **details)
      loops = vm.loop_stack.map { |frame| { limit: frame.limit, index: frame.index } }
      events << {
        sequence: events.length,
        event: event,
        payload_role: TRACE_PAYLOAD_ROLE,
        details: details,
        state: {
          ip: vm.ip,
          steps: vm.steps,
          data_stack: vm.data_stack.dup,
          return_stack: vm.return_stack.dup,
          loop_stack: loops,
          header_here: dictionary.here,
          data_here: dictionary.data_here,
          latest: dictionary.latest
        },
        basic_explanation: Min0CoreForth.explain_trace_event(event, details)
      }
    end

    def document
      {
        trace_format: TRACE_FORMAT,
        implementation: implementation,
        events: events.map(&:dup)
      }
    end
  end
end
