-- agent_dan.lua - 用 Lua 寫 demo/agent-dan（會問腦、會用工具的問答 agent）
-- 編：aos-lua build agent_dan.lua <輸出>；跑：aos-exec --ws <工作區> <輸出>
-- 示範 Lua 這邊多出來的東西：工具用一個函數產生、agent 本身也是一個函數（換 system、換工具就是另一隻）。
-- 腦（brain.py、act.py）與工具的程式讀 demo/agent-dan 那份。
local aos = require("aos")
local demo = "../../../../demo/agent-dan/"

-- 一個工具＝一個資料夾：tool.json（給模型看）＋可執行的 _entry
local function tool(name, description, properties, required)
  return aos.dir {
    ["tool.json"] = {
      description = description,
      parameters = { type = "object", properties = properties or aos.object(), required = required },
    },
    _entry = aos.script(aos.read(demo .. "tools/" .. name .. "/_entry")),
  }
end

-- 一隻 agent-dan 範本：給 system、模型名、工具表，回一個資料夾
local function agent(opts)
  return aos.dir {
    _entry = aos.script("#!/bin/sh\n# _entry - 把 agent-dan 的 loop 跑起來（loop 每次跑一格 fsm.json）\nexec aos-loop loop.json\n"),
    ["loop.json"] = aos.loop { exec = "fsm.json", max = opts.max or 40 },
    ["fsm.json"] = aos.fsm {
      _entry = aos.self_entry("aos-fsm"),
      start = "idle",
      states = {
        { "idle",  exec = "idle", next = "think" },
        { "think", exec = aos.inst { argv = { "python3", "brain.py" }, timeout_ms = 120000 }, next = "act" },
        { "act",   exec = aos.inst { argv = { "python3", "act.py" }, timeout_ms = 60000 }, next = "idle" },
      },
    },
    [".env"] = opts.dotenv,
    ["system.txt"] = opts.system,
    idle = aos.dir { _entry = aos.script(aos.read(demo .. "idle/_entry")) },
    ["brain.py"] = aos.read(demo .. "brain.py"),
    ["act.py"] = aos.read(demo .. "act.py"),
    tools = aos.dir(opts.tools),
  }
end

return agent {
  system = aos.read(demo .. "system.txt"),
  dotenv = aos.read(demo .. ".env"),
  tools = {
    math = tool("math", "算一個算術式子，回結果。只收數字、+ - * / // % **、括號與正負號。",
      { expr = { type = "string", description = "要算的式子，例：17*23" } }, { "expr" }),
    clock = tool("clock", "查現在的 UTC 時間，回 ISO 8601 格式（例：2026-10-23T08:00:00Z）。"),
  },
}
