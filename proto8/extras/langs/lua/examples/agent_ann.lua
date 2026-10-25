-- agent_ann.lua - 用 Lua 寫 demo/agent-ann（全內嵌的一題一答 agent：loop 跑 fsm，fsm 三格都是單子）
-- 編：aos-lua build agent_ann.lua <輸出>；跑：aos-exec --ws <工作區> <輸出>
-- 三支 .py 直接讀 demo/agent-ann 那份（只示範 loop／fsm／單子怎麼寫，程式本身不重寫）
local aos = require("aos")
local demo = "../../../../demo/agent-ann/"

return aos.dir {
  -- loop.json 自己帶 _entry，所以入口只要叫 aos-exec loop.json
  _entry = aos.script("#!/bin/sh\n# loop.json 帶 _entry，aos-exec 它就把 loop 跑起來（10-21 傍晚）\nexec aos-exec loop.json\n"),

  ["loop.json"] = aos.loop {
    _entry = aos.self_entry("aos-loop"),
    exec = aos.inst { argv = { "aos-fsm", "fsm.json" } },
    max = 20,
  },

  ["fsm.json"] = aos.fsm {
    start = "idle",
    states = {   -- 陣列寫法：照這個順序寫出去
      { "idle",  exec = aos.inst { argv = { "python3", "idle.py" } }, next = "think" },
      { "think", exec = aos.inst {
          argv = { "python3", "brain.py" },
          stdout = aos.env("AOS_STACK", { path = "plan.txt" }),
          timeout_ms = 120000,
        }, next = "act" },
      { "act",   exec = aos.inst { argv = { "python3", "act.py" } }, next = "idle" },
    },
  },

  ["idle.py"] = aos.read(demo .. "idle.py"),
  ["brain.py"] = aos.read(demo .. "brain.py"),
  ["act.py"] = aos.read(demo .. "act.py"),
  [".env"] = aos.read(demo .. ".env"),
}
