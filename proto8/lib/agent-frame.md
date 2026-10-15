# agent 當函數／當工具（定義資料夾＋frame）

← [agent.md](agent.md)｜[proto8/lib](README.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)

> 10-15 晚從 [agent.md](agent.md) 拆出來（整檔超過 8 KB）；內容沒改。**實作慣例，還不是規範。**

概念：[CONCEPTS C-46、C-50](../CONCEPTS/05-agent.md)｜決定：[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md#callbindinglisp-式)（10-15 收工後：call／binding 不寫專用程式，用 json＋資料夾＋inst；原本的 `aos_agent_call.py`、`aos_agent_lib.py ask` 已退場）

**定義資料夾**（照 Lisp 的函數本體；呼叫時一個字都不寫，所以能重複用）：

```
clerk/
  fsm.json      {"start": "intake", "state": "fsm-state.json", "end": ["done", "halted"], "states": {
                   "intake": {"val": "cells/intake.json", "next": "thinking"},
                   "thinking": {"val": "cells/think.json", "next": "route"},
                   "route": "cells/route.json",                       // 回 {"next": "tool"} 或 {"next": "done"}
                   "tool": {"val": "cells/tool.json", "next": "thinking"},
                   "done": "cells/done.json"}}   // halted 只在 end：think 連錯自己寫好 ret.json、跳去就結束
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

- 一趟：intake（args.json → history）→ think → route → (tool → think → route)* → done（寫 `ret.json`＝`{"reply"}`；done 在 `end` 裡，fsm 結束那行帶 `"end": true`，loop 的 `stop_on_end` 看到就停，N-44）。think 連錯 3 次＝think 自己寫 `ret.json`＝`{"error": {"code", "msg"}}`、回 `next: halted`（只在 `end`、不在 `states`）＝fsm 結束，不經 done 格（10-15 使用者「都同意。」，[盤點第 8 條](../thinking/2026-10-15-principles.md)）。走完 end，fsm 的 phase 歸位 `intake`。
- **成敗看 `ret.json`**：走到 halted 時 loop 照樣退 0、state `done`（C-52：loop 只說自己這一層，不把 agent 的失敗當自己的錯；10-15 使用者「都同意。」），呼叫方看 `ret.json` 有沒有 `error`。
- loop 的 `times` 用完還沒走到 done＝沒有 `ret.json`（沒跑完）。
- **同一個 frame 再叫一次**＝接著那裡的 history：呼叫方只要再寫一份 `args.json`；intake 把它接在後面、順手刪上一輪的 `ret.json`（這次沒跑完就讀不到舊的）。不必刪 `ctl.json`：done 不寫 ctl，loop 靠 fsm 結束那行停。
- 兩個呼叫同時指同一個 frame 不擋（卡死不防護）；不同 frame 可以同時跑。

**當工具**：工具 inst 用 `sh -c` 三步（寫 env.json → 跑被叫者的 loop → 讀 ret.json）。tool 格每次在 `work/<n>/` 開新資料夾、寫好 `args.json`、在那裡跑它，所以那裡就是被叫者的 frame；`cat ret.json` 的內容就是工具結果，父 agent 的 tool 訊息 `result` 看得到（錯也是 N-29 形狀）。demo 的 `tools/clerk.json`：

```jsonc
{"argv": ["aos-demo", "sh", "-c",
   "printf '{\"parent\": \"%s\"}' \"$AOS_DEMO/fsm/clerk\" > env.json && aos loop \"$AOS_DEMO/fsm/clerk/loop.json\" >/dev/null; cat ret.json"],
 "timeout_ms": 120000, "_tool": {"description": "問報時員…", "parameters": {…}}}
```

- 綁定也在這一步做：例 `demo/kernels/llm/boss/tools/clerk.json` 多一步 `cp …/boss/brain.json brain.json`，報時員就改用 boss 的腦（經閘門）。

**換腦只換那一層**（10-15 使用者「都按照推薦」，[litellm 實跑 #1](../thinking/2026-10-15-litellm-live.md#拍板10-15)）：子 agent 沿**自己 frame** 的 `env.json` 往上找（`chain()` 只看 frame 自己的 env.json，不看呼叫方），所以呼叫方 frame 放的 `brain.json` 不會傳到子 agent。呼叫方要換子 agent 的腦，就在**子 agent 的 frame** 放 `brain.json`——寫在當工具的那張 inst 裡（像上面 boss 的 `cp`），或在 frame 放一份同名工具蓋過定義的（`demo/paint/run.py` 的 `bind_brain()`）。
- 查過（10-15）：boss 叫報時員用的是 boss **定義資料夾**那顆經閘門的假腦，是因為 `boss/tools/clerk.json` 那行 `cp "$AOS_DEMO/kernels/llm/boss/brain.json"` 寫死抄定義的腦，不是綁定從 boss 的 frame 漏下去；報時員自己的定義（`demo/fsm/clerk/brain.json`）是不經閘門的假腦。boss 的 frame 換了腦，報時員照樣用那行抄的那顆——這正是「只換那一層」。
- 上限：被叫者 loop 的 `times`、那張工具 inst 的 `timeout_ms`（父 agent 的 tool 格 `timeout_ms` 要更大）；遞迴深度不另外擋（Busy、TooDeep、MaxTicks 都拿掉了）。
- 定義資料夾的路徑：demo 用 `aos-demo` 給的 `AOS_DEMO` 拼絕對路徑；不在 demo 裡就直接寫絕對路徑。
