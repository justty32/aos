# 10b agent 的圈：模板骨架
← [入口](README.md)

[10](10-agent.md) 規定 agent 那塊地有哪些檔、圈要走哪六種步。這份檔給那個圈的實體：一份能過 [`schemas/program.schema.json`](schemas/program.schema.json) 的模板，實作照抄改。條款編號接著 10 往下（S-10-45 起）。

## 骨架

`.aos/program/main.json`（`source_hash` 由編譯器填）。`agent-*` 是地上的普通程式，名字實作自取；`${frame}`、`${land}`、`${llm_world}`、`${home}` 是內建暫存器，由 exec 換掉，見 [05b](05b-series-lifetimes.md)；每筆 `inst` 建議加 `"env_inherit": false`。

```json
{ "format_version": 1, "name": "main",
  "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "steps": [
 { "name": "build_prompt", "kind": "inst", "expect": "${frame}/request.json", "then": "check_limits",
   "inst": { "format_version": 1, "id": "build", "argv": ["agent-prompt", "${frame}"] } },
 { "name": "check_limits", "kind": "inst", "then": "send",
   "inst": { "format_version": 1, "id": "lim", "argv": ["agent-limits", "${land}"] } },
 { "name": "send", "kind": "inst", "then": "wait_reply",
   "inst": { "format_version": 1, "id": "send",
             "argv": ["aos", "deliver", "${llm_world}", "--llm", "${frame}/request.json"] } },
 { "name": "wait_reply", "kind": "await", "result": "${frame}/reply.txt",
   "max_ticks": 600, "then": "tally_usage" },
 { "name": "tally_usage", "kind": "inst", "then": "parse",
   "inst": { "format_version": 1, "id": "tally",
             "argv": ["agent-tally", "${land}", "${frame}/reply.txt"] } },
 { "name": "parse", "kind": "inst", "expect": "${frame}/calls.json", "select": "${frame}/next.txt",
   "inst": { "format_version": 1, "id": "parse", "argv": ["agent-parse", "${frame}"] } },
 { "name": "run_fast", "kind": "inst", "expect": "${frame}/fast.json", "select": "${frame}/after.txt",
   "inst": { "format_version": 1, "id": "fast", "argv": ["agent-tools", "${frame}"] } },
 { "name": "call_slow", "kind": "call", "child": "slow", "mode": "async", "then": "await_slow",
   "result": "${frame}/slow.json", "clock": { "kind": "until", "until": "idle" } },
 { "name": "await_slow", "kind": "await", "result": "${frame}/slow.json",
   "max_ticks": 600, "then": "wrap", "on_fail": "wrap" },
 { "name": "wrap", "kind": "inst", "expect": "${frame}/envelope.json", "then": "build_prompt",
   "inst": { "format_version": 1, "id": "wrap", "argv": ["agent-wrap", "${frame}"] } },
 { "name": "close", "kind": "inst", "then": "end",
   "inst": { "format_version": 1, "id": "close",
             "argv": ["aos", "say", "${home}", "--body", "${frame}/reply.txt"] } }
] }
```

## 讀這份骨架要知道的

- `tally_usage` 自己一步，不跟 `wait_reply` 擠同一格：一格裡的指令彼此看不到結果，`await` 那格還沒有用量檔可讀。
- `parse` 的 `select` 讀 `${frame}/next.txt` 第一行：工具清單有東西寫 `run_fast`，空的寫 `close`。
- `run_fast` 的 `select` 同理，在 `call_slow` 與 `wrap` 之間選。
- `wait_reply` 沒寫 `on_fail`，所以 LLM 那筆壞掉整條串就停住；要重投得自己補一步（見 [10](10-agent.md) 的 S-10-35）。
- `close` 那步把模型最後那句話當一封信寄回家，使用者用 `aos listen` 讀得到。

## 條款

- **S-10-45** 這份骨架必須當成建議的形狀：步名、`agent-*` 的程式名、`max_ticks` 的值都可以改，[10](10-agent.md) 的 S-10-15 那六種步與順序不准改。〔主編補〕
- **S-10-46** 骨架禁止用 `~` 或任何寫死的家路徑；要指家必須用 `${home}`，要指 LLM 世界必須用 `${llm_world}`。〔主編補〕
- **S-10-47** `aos state` 的三態必須靠步名認：`wait_reply`＝等 LLM，`run_fast`／`await_slow`＝等工具，其餘＝組 prompt。改了步名就必須跟著改這張對照。〔主編補〕
- **S-10-48** 骨架裡每個 `await` 步都建議給 `max_ticks`；不給就有一條串永遠在等、run 永遠不停。〔主編補〕

## 待使用者拍板

- S-10-45 骨架是建議形狀，六種步與順序不准改。〔主編補〕
- S-10-46 指家用 `${home}`、指 LLM 世界用 `${llm_world}`，禁止寫死路徑。〔主編補〕
- S-10-47 `aos state` 的三態靠步名認。〔主編補〕
- S-10-48 每個 `await` 都建議給 `max_ticks`。〔主編補〕

## 現況對照

今天沒有模板、沒有步，agent 的一圈寫死在 `core/agent/src/step.cpp` 裡：LLM 呼叫是同步等 HTTP，工具往返靠 `.aos/every/` 每格重投一份。這份骨架把那段程式碼換成一份資料檔。
