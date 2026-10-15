# agent 當函數／當工具（定義資料夾＋frame）

← [agent.md](agent.md)｜[proto8/lib](README.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)

> 10-15 晚從 [agent.md](agent.md) 拆出來（整檔超過 8 KB）；內容沒改。**實作慣例，還不是規範。**

概念：[CONCEPTS C-46、C-50](../CONCEPTS/05-agent.md)｜決定：[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md#callbindinglisp-式)（10-15 收工後：call／binding 不寫專用程式，用 json＋資料夾＋inst；原本的 `aos_agent_call.py`、`aos_agent_lib.py ask` 已退場）

**定義資料夾**（照 Lisp 的函數本體；呼叫時一個字都不寫，所以能重複用）：

```
clerk/
  fsm.json      {"start": "intake", "state": "fsm-state.json", "end": ["done", "halted"], "states": {
                   "intake": {"target": "cells/intake.json", "next": "thinking"},
                   "thinking": {"target": "cells/think.json", "next": "route"},
                   "route": "cells/route.json",                       // 回 {"next": "tool"} 或 {"next": "done"}
                   "tool": {"target": "cells/tool.json", "next": "thinking"},
                   "done": "cells/done.json", "halted": "cells/done.json"}}   // halted＝think 連錯自己跳來
  loop.json     {"inst": {"argv": ["aos", "agent", "fsm"]}, "times": 20, "stop_on_end": true, "ctl": "ctl.json", "state": "loop-state.json"}
  cells/intake.json  {"argv": ["aos", "agent", "intake"]}      think／route（--done done）／tool／done 同樣一行
  brain.json  system.md  tools/clock.json
```

**frame**＝被叫者跑的 cwd，放哪由呼叫方決定（C-46）。裡面：`env.json` `{"parent": "<定義資料夾>"}`（找名字往上一層）、`args.json`（實引數，intake 接走後改名 `args.taken.json`）、`ret.json`（回傳）、`history.json`、`fsm-state.json`、`loop-state.json`、`ctl.json`、`work/`。放同名檔＝綁定：`brain.json` 蓋過定義的腦、`tools/x.json` 追加或同名蓋過（逐項合併；「整份取代」不支援）、`history.json` 綁一段對話。

**呼叫**（直接叫）：

```
cd frame && echo '{"parent": "/abs/clerk"}' > env.json && echo '{"question": "幾點？"}' > args.json \
  && aos loop /abs/clerk/loop.json >/dev/null; cat ret.json
```

- 一趟：intake（args.json → history）→ think → route → (tool → think → route)* → done（寫 `ret.json`＝`{"reply"}`；done 在 `end` 裡，fsm 結束那行帶 `"end": true`，loop 的 `stop_on_end` 看到就停，N-44）。think 連錯 3 次＝halted → 同一張 done 格寫 `{"error": {"code", "msg"}}`。走完 end，fsm 的 phase 歸位 `intake`。
- loop 的 `times` 用完還沒走到 done＝沒有 `ret.json`（沒跑完）。
- **同一個 frame 再叫一次**＝接著那裡的 history：呼叫方只要再寫一份 `args.json`；intake 把它接在後面、順手刪上一輪的 `ret.json`（這次沒跑完就讀不到舊的）。不必刪 `ctl.json`：done 不寫 ctl，loop 靠 fsm 結束那行停。
- 兩個呼叫同時指同一個 frame 不擋（卡死不防護）；不同 frame 可以同時跑。

**當工具**：工具 inst 用 `sh -c` 三步（寫 env.json → 跑被叫者的 loop → 讀 ret.json）。tool 格每次在 `work/<n>/` 開新資料夾、寫好 `args.json`、在那裡跑它，所以那裡就是被叫者的 frame；`cat ret.json` 的內容就是工具結果，父 agent 的 tool 訊息 `result` 看得到（錯也是 N-29 形狀）。demo 的 `tools/clerk.json`：

```jsonc
{"argv": ["aos-demo", "sh", "-c",
   "printf '{\"parent\": \"%s\"}' \"$AOS_DEMO/fsm/clerk\" > env.json && aos loop \"$AOS_DEMO/fsm/clerk/loop.json\" >/dev/null; cat ret.json"],
 "timeout_ms": 120000, "_tool": {"description": "問報時員…", "parameters": {…}}}
```

- 綁定也在這一步做：例 `demo/kernel/boss/tools/clerk.json` 多一步 `cp …/boss/brain.json brain.json`，報時員就改用 boss 的腦（經閘門）。
- 上限：被叫者 loop 的 `times`、那張工具 inst 的 `timeout_ms`（父 agent 的 tool 格 `timeout_ms` 要更大）；遞迴深度不另外擋（Busy、TooDeep、MaxTicks 都拿掉了）。
- 定義資料夾的路徑：demo 用 `aos-demo` 給的 `AOS_DEMO` 拼絕對路徑；不在 demo 裡就直接寫絕對路徑。
