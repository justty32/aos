-- smoke.lua - 在 nvim --clean --headless 裡把 aos_nvim 的指令走一遍（proto8/tests/test_lua_aos.py 叫它）
--   nvim --clean --headless -l proto8/extras/editors/nvim/tests/smoke.lua
-- 全過印「smoke: 全部通過」、退 0；任一項不過印原因、退 1。暫存資料夾跑完刪掉。
local here = debug.getinfo(1, "S").source:sub(2):match("^(.*)/tests/smoke%.lua$")
vim.opt.rtp:prepend(here)
local proto8 = vim.fn.fnamemodify(here .. "/../../..", ":p"):gsub("/$", "")
local aos = require("aos_nvim")

local tmp = vim.fn.tempname()
vim.fn.mkdir(tmp, "p")
local ws = tmp .. "/ws"
vim.fn.mkdir(ws, "p")
aos.setup({ ws = ws, listen_timeout = 30 })

local failed = 0
local function check(name, ok, detail)
  if ok then
    print("ok   " .. name)
  else
    failed = failed + 1
    print("FAIL " .. name .. (detail and ("：" .. detail) or ""))
  end
end

local function wait()
  return vim.wait(60000, function() return aos.busy == 0 end, 50)
end

local function panel_has(s)
  return table.concat(aos.panel_lines(), "\n"):find(s, 1, true) ~= nil
end

-- 1. :AosLuaBuild：把 examples/agent_dan.lua 編成資料夾
local src = proto8 .. "/extras/langs/lua/examples/agent_dan.lua"
vim.cmd.edit(vim.fn.fnameescape(src))
local dan = tmp .. "/dan"
vim.cmd("AosLuaBuild " .. vim.fn.fnameescape(dan))
wait()
check("AosLuaBuild 寫出 fsm.json", vim.uv.fs_stat(dan .. "/fsm.json") ~= nil, table.concat(aos.panel_lines(), "\n"))
check("AosLuaBuild 面板列出檔案", panel_has("tools/clock/_entry*"))

-- 2. :AosLuaPreview：只看一段 JSON
vim.cmd("AosLuaPreview fsm.json#/states/think/exec")
wait()
check("AosLuaPreview 看到 brain.py", panel_has('"argv": ["python3", "brain.py"]'), table.concat(aos.panel_lines(), "\n"))

-- 3. :AosGoto：從 loop.json 的 "fsm.json" 跳到 fsm.json，再跳到 #/states/act/exec
vim.cmd.edit(vim.fn.fnameescape(dan .. "/loop.json"))
check("AosGoto 游標下的字", (function()
  vim.fn.search("fsm.json")
  return aos.target_under_cursor() == "fsm.json"
end)())
vim.cmd("AosGoto")
check("AosGoto 開了 fsm.json", vim.fn.expand("%:t") == "fsm.json", vim.fn.expand("%:p"))
vim.cmd("AosGoto #/states/act/exec")
local line = vim.api.nvim_get_current_line()
local col = vim.api.nvim_win_get_cursor(0)[2]
check("AosGoto 指標落在 act 的 exec", line:sub(col + 1):find('^{"argv": %["python3", "act.py"%]') ~= nil, line .. " @" .. col)
check("AosGoto 指不到回 false", aos.jump("fsm.json#/states/nope") == false)
check("AosGoto 資料夾＝它的 _entry", aos.jump("idle") and vim.fn.expand("%:p") == dan .. "/idle/_entry", vim.fn.expand("%:p"))

-- 4. :AosExec：放一題、跑目前檔案所在的 agent（往上找 _entry）
vim.cmd.edit(vim.fn.fnameescape(dan .. "/fsm.json"))
vim.fn.mkdir(ws .. "/new", "p")
local f = io.open(ws .. "/new/q1.txt", "w")
f:write("現在幾點？\n")
f:close()
vim.cmd("AosExec")
wait()
check("AosExec 結束碼 0", panel_has("== 結束碼 0"), table.concat(aos.panel_lines(), "\n"))
check("AosExec 面板有 trace", panel_has("think") and panel_has("act"))
check("AosExec 寫了答案", vim.fn.filereadable(ws .. "/out/q1.txt") == 1)

-- 4b. :AosExec!：跑目前這個檔本身（fsm.json 帶 _entry＝只走一格）
local function trace_n()
  local t = io.open(ws .. "/.stack/trace.jsonl")
  if not t then return 0 end
  local n = select(2, t:read("*a"):gsub("\n", ""))
  t:close()
  return n
end
local before = trace_n()
vim.cmd("AosExec!")
wait()
check("AosExec! 只走一格", trace_n() == before + 1 and panel_has("dan/fsm.json"), before .. " → " .. trace_n())

-- 5. :AosTrace
vim.cmd("AosTrace")
check("AosTrace 有 idle", panel_has("idle"))

-- 6. :AosSay!：預設外掛自己寫 new/、輪詢 out/（舊協議；10-30 起 aos-say／aos-listen 走 queue、說不到 fsm 範本，use_say 預設 false）
local answer
aos.say("第二題", true, function(a) answer = a end)
wait()
check("AosSay! 拿到答案（自己寫檔）", answer and answer:find("FAKE ANSWER to: 第二題") ~= nil, table.concat(aos.panel_lines(), "\n"))

-- 8. pointer：陣列、跳脫、空白
local p = require("aos_nvim.pointer")
local s = '{"a/b": [1, {"x": "y"}], "c~d": {"k": true}}'
check("pointer 陣列", p.find(s, "/a~1b/1/x") == s:find('"y"'))
check("pointer ~0", p.find(s, "/c~0d/k") == s:find("true"))
check("pointer 指不到", p.find(s, "/a~1b/5") == nil)

vim.fn.delete(tmp, "rf")
if failed == 0 then
  print("smoke: 全部通過")
  os.exit(0)
end
print("smoke: " .. failed .. " 項不過")
os.exit(1)
