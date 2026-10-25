-- aos_nvim - 在 nvim 裡用 aos：跑資料夾程式、看 trace、對 agent 丟題、跳到 檔#/指標、預覽 Lua 編出的 JSON（嘗試，2026-10-24）
--
--   :AosWs [資料夾]          看／設工作區（預設 nvim 的 cwd）
--   :AosExec [目標 args...]  aos-exec --ws 工作區 目標；沒給目標＝目前檔案所在的 aos 程式（往上找有 _entry 的資料夾）
--   :AosExec!               跑目前這個檔本身（例 fsm.json 帶 _entry＝只走一格）
--   :AosTrace               看工作區 stack 的 trace.jsonl（每格一行）
--   :AosSay[!] 話           放一題到工作區 new/、等 out/ 的答案；加 ! 順便替你跑目前的 agent 一次
--   :AosGoto [檔#/指標]      跳過去；沒給＝游標下的那串字（例 fsm.json#/states/think/exec、"#/states/act"）
--   :AosLuaPreview [路徑]    把目前的 .lua 用 aos-lua 編一次、在面板看 JSON（給路徑＝只看那個檔，可接 #/指標）
--   :AosLuaBuild [輸出]      編出來寫成資料夾（預設＝原始檔旁邊、去掉 .lua 的同名資料夾）
-- 輸出都在同一個下方面板（aos://panel），按 q 關。PATH 只在叫子行程時前面接上 aos 的 bin/，不改 nvim 自己的。
local pointer = require("aos_nvim.pointer")

local M = {}

local here = debug.getinfo(1, "S").source:sub(2):match("^(.*)/lua/aos_nvim/init%.lua$") or "."
local PROTO8 = vim.fn.fnamemodify(here .. "/../../..", ":p"):gsub("/$", "")

M.config = {
  ws = nil,            -- 工作區；nil＝vim.g.aos_ws，再沒有＝nvim 的 cwd
  stack = nil,         -- 看 trace 用的 stack；nil＝工作區/.stack
  bins = nil,          -- 叫子行程時接在 PATH 前面的資料夾；nil＝這個 repo 的 impls/*/bin、bin、extras/human/bin、extras/langs/lua/bin
  lua_cmd = nil,       -- 跑 aos-lua 的方式；nil＝有 lua 用 lua、沒有用 nvim -l
  listen_timeout = 300, -- :AosSay 等答案最多幾秒
  use_say = true,      -- 有 aos-say／aos-listen 就用它們；false＝外掛自己寫 new/、輪詢 out/
  panel_height = 15,
}

M.busy = 0   -- 還在跑的子行程數（測試用 vim.wait 等它歸零）

-- ---------- 小工具 ----------

local function bins()
  if M.config.bins then return M.config.bins end
  local out = {}
  for _, d in ipairs({ "impls/aos-exec/bin", "impls/aos-loop/bin", "impls/aos-fsm/bin", "impls/aos-daemon/bin",
                       "bin", "extras/human/bin", "extras/langs/lua/bin" }) do
    local p = PROTO8 .. "/" .. d
    if vim.fn.isdirectory(p) == 1 then out[#out + 1] = p end
  end
  return out
end

local function env()
  return { PATH = table.concat(bins(), ":") .. ":" .. (vim.env.PATH or "") }
end

local function which(name)
  for _, d in ipairs(bins()) do
    if vim.fn.executable(d .. "/" .. name) == 1 then return d .. "/" .. name end
  end
  return vim.fn.exepath(name) ~= "" and vim.fn.exepath(name) or nil
end

function M.ws()
  local ws = M.config.ws or vim.g.aos_ws or vim.fn.getcwd()
  return (vim.fn.fnamemodify(ws, ":p"):gsub("/$", ""))
end

local function stack()
  return M.config.stack or (M.ws() .. "/.stack")
end

local function read(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local s = f:read("*a")
  f:close()
  return s
end

-- ---------- 面板 ----------

local panel = { buf = nil }

local function panel_buf()
  if panel.buf and vim.api.nvim_buf_is_valid(panel.buf) then return panel.buf end
  local buf = vim.api.nvim_create_buf(false, true)
  pcall(vim.api.nvim_buf_set_name, buf, "aos://panel")
  vim.bo[buf].bufhidden = "hide"
  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = buf, desc = "關 aos 面板" })
  panel.buf = buf
  return buf
end

local function panel_show(title, lines, ft)
  local buf = panel_buf()
  vim.bo[buf].filetype = ft or "text"
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, vim.list_extend({ "== " .. title }, lines or {}))
  local win = vim.fn.bufwinid(buf)
  if win == -1 then
    local cur = vim.api.nvim_get_current_win()
    vim.cmd("botright " .. M.config.panel_height .. "split")
    vim.api.nvim_win_set_buf(0, buf)
    vim.wo.wrap = true
    vim.api.nvim_set_current_win(cur)
  end
end

local function panel_add(lines)
  local buf = panel_buf()
  vim.api.nvim_buf_set_lines(buf, -1, -1, false, lines)
  local win = vim.fn.bufwinid(buf)
  if win ~= -1 then vim.api.nvim_win_set_cursor(win, { vim.api.nvim_buf_line_count(buf), 0 }) end
end

function M.panel_lines()
  return vim.api.nvim_buf_get_lines(panel_buf(), 0, -1, false)
end

-- 跑一個子行程，stdout／stderr 一行一行接進面板；跑完呼叫 done(結果)
local function spawn(cmd, opts, done)
  M.busy = M.busy + 1
  local function feed(prefix)
    local rest = ""
    return function(_, data)
      if not data then
        if rest ~= "" then vim.schedule(function() panel_add({ prefix .. rest }) end) end
        return
      end
      local lines = vim.split(rest .. data, "\n", { plain = true })
      rest = table.remove(lines)
      if #lines > 0 then
        vim.schedule(function()
          for i, l in ipairs(lines) do lines[i] = prefix .. l end
          panel_add(lines)
        end)
      end
    end
  end
  local ok, err = pcall(vim.system, cmd, {
    cwd = opts.cwd, env = env(), text = true, stdin = opts.stdin,
    stdout = (not opts.quiet) and feed("") or nil, stderr = feed("! "),
  }, function(r)
    vim.schedule(function()
      M.busy = M.busy - 1
      if done then done(r) end
    end)
  end)
  if not ok then
    M.busy = M.busy - 1
    panel_add({ "! 起不來：" .. tostring(err) })
  end
end

-- ---------- 找 aos 程式 ----------

-- 從 path 往上找第一個「裡面有 _entry 或 _entry.json」的資料夾（只找資料夾；要跑某個檔本身用 :AosExec!）
function M.program_of(path)
  path = vim.fn.fnamemodify(path ~= "" and path or vim.fn.getcwd(), ":p")
  local dir = vim.fn.isdirectory(path) == 1 and path or vim.fn.fnamemodify(path, ":h")
  dir = dir:gsub("/$", "")
  while dir ~= "" do
    if vim.uv.fs_stat(dir .. "/_entry") or vim.uv.fs_stat(dir .. "/_entry.json") then return dir end
    local up = vim.fn.fnamemodify(dir, ":h")
    if up == dir then break end
    dir = up
  end
  return nil
end

-- ---------- 指令 ----------

local function show_trace(max)
  local s = read(stack() .. "/trace.jsonl")
  if not s then
    panel_add({ "（沒有 " .. stack() .. "/trace.jsonl）" })
    return
  end
  local lines = {}
  for line in s:gmatch("[^\n]+") do
    local ok, t = pcall(vim.json.decode, line)
    if ok and type(t) == "table" then
      lines[#lines + 1] = string.format("%s  %-8s code %s%s  %sms", tostring(t.started_at or ""), tostring(t.state),
        tostring(t.code), t.signal ~= nil and t.signal ~= vim.NIL and (" signal " .. tostring(t.signal)) or "",
        tostring(t.elapsed_ms or "?"))
    else
      lines[#lines + 1] = line
    end
  end
  if max and #lines > max then lines = vim.list_slice(lines, #lines - max + 1) end
  panel_add(lines)
end

-- this_file＝跑目前這個檔本身（例 fsm.json 帶 _entry＝只走一格）
function M.exec(args, done, this_file)
  local target = args and args[1]
  local cmd = { "aos-exec", "--ws", M.ws() }
  if target then
    vim.list_extend(cmd, args)
  elseif this_file then
    vim.cmd("silent! write")
    cmd[#cmd + 1] = vim.fn.expand("%:p")
  else
    local prog = M.program_of(vim.api.nvim_buf_get_name(0))
    if not prog then
      vim.notify("aos: 往上找不到 _entry，給個目標：:AosExec 目標", vim.log.levels.WARN)
      return
    end
    cmd[#cmd + 1] = prog
  end
  panel_show(table.concat(cmd, " "), {})
  spawn(cmd, {}, function(r)
    panel_add({ "== 結束碼 " .. r.code .. (r.signal ~= 0 and (" 訊號 " .. r.signal) or ""), "== trace（最後 20 格）" })
    show_trace(20)
    if done then done(r) end
  end)
end

function M.trace()
  panel_show("trace " .. stack() .. "/trace.jsonl", {})
  show_trace()
end

local function utc_name()
  local t = vim.uv.gettimeofday and { vim.uv.gettimeofday() } or { os.time(), 0 }
  return os.date("!%Y%m%dT%H%M%S", t[1]) .. string.format(".%03dZ.txt", math.floor((t[2] or 0) / 1000))
end

-- 自己放題（沒有 aos-say 時）：先寫工作區頂層的暫存檔，再 rename 進 new/（同 aos-say 的原子寫入；rename 會蓋，所以先查）
local function say_direct(text)
  local ws = M.ws()
  vim.fn.mkdir(ws .. "/new", "p")
  local name = utc_name()
  for _, d in ipairs({ "new", "cur", "out", "done" }) do
    if vim.uv.fs_stat(ws .. "/" .. d .. "/" .. name) then return nil, "題名用過了：" .. name end
  end
  local tmp = ws .. "/.say-nvim-" .. vim.fn.getpid() .. ".tmp"
  local f = io.open(tmp, "wb")
  if not f then return nil, "寫不了 " .. tmp end
  f:write(text:sub(-1) == "\n" and text or text .. "\n")
  f:close()
  local ok, err = vim.uv.fs_rename(tmp, ws .. "/new/" .. name)
  if not ok then return nil, tostring(err) end
  return name
end

local function wait_answer(name, done)
  local listen = M.config.use_say and which("aos-listen")
  local function finish(text)
    panel_add({ "== 答案 out/" .. name })
    panel_add(vim.split(text, "\n", { plain = true, trimempty = true }))
    if done then done(text) end
  end
  if listen then
    spawn({ listen, "--ws", M.ws(), "--timeout", tostring(M.config.listen_timeout), name }, { quiet = true },
      function(r)
        if r.code == 0 then finish(r.stdout or "") else panel_add({ "== aos-listen 結束碼 " .. r.code }) if done then done(nil) end end
      end)
    return
  end
  local path, waited = M.ws() .. "/out/" .. name, 0
  M.busy = M.busy + 1
  local timer = vim.uv.new_timer()
  timer:start(0, 200, vim.schedule_wrap(function()
    local s = read(path)
    waited = waited + 0.2
    if s or waited > M.config.listen_timeout then
      timer:stop()
      timer:close()
      M.busy = M.busy - 1
      if s then finish(s) else panel_add({ "== 等了 " .. M.config.listen_timeout .. " 秒還沒有答案" }) if done then done(nil) end end
    end
  end))
end

function M.say(text, run, done)
  if not text or text == "" then
    vim.notify("aos: :AosSay 要一句話", vim.log.levels.WARN)
    return
  end
  local prog = run and M.program_of(vim.api.nvim_buf_get_name(0)) or nil
  if run and not prog then
    vim.notify("aos: :AosSay! 要在 agent 資料夾裡的檔用（往上找不到 _entry）", vim.log.levels.WARN)
    return
  end
  panel_show("say → " .. M.ws() .. "/new/", { "> " .. text })
  local function after_put(name)
    panel_add({ "== 題名 " .. name })
    if prog then
      panel_add({ "== aos-exec --ws " .. M.ws() .. " " .. prog })
      spawn({ "aos-exec", "--ws", M.ws(), prog }, {}, function(r)
        panel_add({ "== agent 結束碼 " .. r.code })
        wait_answer(name, done)
      end)
    else
      wait_answer(name, done)
    end
  end
  local say = M.config.use_say and which("aos-say")
  if say then
    spawn({ say, "--ws", M.ws() }, { stdin = text, quiet = true }, function(r)
      local name = vim.trim(r.stdout or "")
      if r.code ~= 0 or name == "" then
        panel_add({ "== aos-say 結束碼 " .. r.code })
        if done then done(nil) end
        return
      end
      after_put(name)
    end)
  else
    local name, err = say_direct(text)
    if not name then
      panel_add({ "! " .. err })
      if done then done(nil) end
      return
    end
    after_put(name)
  end
end

-- 「檔#/指標」解成 (檔, 指標)；相對路徑從 base 算；資料夾＝它的 _entry；沒副檔名又找不到＝補 .json（同 aos-exec，N-61）
function M.resolve(target, base)
  local file, ptr = target:match("^([^#]*)#(.*)$")
  if not file then file = target end
  if file == "" then
    file = vim.api.nvim_buf_get_name(0)
  elseif file:sub(1, 1) ~= "/" then
    file = base .. "/" .. file
  end
  file = vim.fn.fnamemodify(file, ":p")
  if vim.fn.isdirectory(file) == 1 then
    local d = file:gsub("/$", "")
    file = vim.uv.fs_stat(d .. "/_entry") and d .. "/_entry" or d .. "/_entry.json"
  elseif not vim.uv.fs_stat(file) and not vim.fn.fnamemodify(file, ":t"):find("%.") then
    file = file .. ".json"
  end
  return file, ptr
end

-- 游標下那串字：往兩邊擴到空白、引號、逗號、括號為止
function M.target_under_cursor()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1
  local stop = "[%s\"',%[%]{}()]"
  local a, b = col, col
  while a > 1 and not line:sub(a - 1, a - 1):match(stop) do a = a - 1 end
  while b <= #line and not line:sub(b, b):match(stop) do b = b + 1 end
  return line:sub(a, b - 1)
end

function M.jump(target)
  target = (target and target ~= "") and target or M.target_under_cursor()
  if target == "" then
    vim.notify("aos: 游標下沒有路徑", vim.log.levels.WARN)
    return false
  end
  local base = vim.fn.expand("%:p:h")
  if base == "" then base = vim.fn.getcwd() end
  local file, ptr = M.resolve(target, base)
  if not vim.uv.fs_stat(file) then
    vim.notify("aos: 找不到 " .. file, vim.log.levels.WARN)
    return false
  end
  if vim.fn.fnamemodify(file, ":p") ~= vim.fn.expand("%:p") then vim.cmd.edit(vim.fn.fnameescape(file)) end
  if ptr and ptr ~= "" then
    local text = table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n")
    local off = pointer.find(text, ptr)
    if not off then
      vim.notify("aos: " .. file .. " 裡指不到 #" .. ptr, vim.log.levels.WARN)
      return false
    end
    local l, c = pointer.to_pos(text, off)
    vim.api.nvim_win_set_cursor(0, { l, c })
  end
  return true
end

local function lua_cmd()
  if M.config.lua_cmd then return vim.deepcopy(M.config.lua_cmd) end
  local script = PROTO8 .. "/extras/langs/lua/bin/aos-lua"
  if vim.fn.executable("lua") == 1 then return { "lua", script } end
  return { vim.v.progpath, "-l", script }
end

function M.lua_preview(what, done)
  local src = vim.fn.expand("%:p")
  if src == "" then return end
  vim.cmd("silent! write")
  local cmd = vim.list_extend(lua_cmd(), { "json", src })
  if what and what ~= "" then cmd[#cmd + 1] = what end
  panel_show("aos-lua json " .. vim.fn.fnamemodify(src, ":t") .. (what and what ~= "" and (" " .. what) or ""), {}, "json")
  spawn(cmd, {}, function(r)
    if r.code ~= 0 then panel_add({ "== 結束碼 " .. r.code }) end
    if done then done(r) end
  end)
end

function M.lua_build(out, done)
  local src = vim.fn.expand("%:p")
  if src == "" then return end
  vim.cmd("silent! write")
  out = (out and out ~= "") and vim.fn.fnamemodify(out, ":p"):gsub("/$", "") or src:gsub("%.lua$", "")
  local cmd = vim.list_extend(lua_cmd(), { "build", src, out })
  panel_show("aos-lua build → " .. out, {})
  spawn(cmd, {}, function(r)
    panel_add({ r.code == 0 and "== 寫好了：" .. out or "== 結束碼 " .. r.code })
    if r.code == 0 then
      spawn(vim.list_extend(lua_cmd(), { "ls", src }), {}, function() if done then done(r) end end)
    elseif done then
      done(r)
    end
  end)
end

function M.setup(opts)
  M.config = vim.tbl_extend("force", M.config, opts or {})
  local cmd = vim.api.nvim_create_user_command
  cmd("AosWs", function(o)
    if o.args ~= "" then M.config.ws = vim.fn.fnamemodify(o.args, ":p") end
    vim.notify("aos 工作區：" .. M.ws())
  end, { nargs = "?", complete = "dir", desc = "aos：看／設工作區" })
  -- 補全用 Lua 函數、不用 complete = "file"：後者會把參數裡的 # 換成「上一個檔」，檔#/指標 就壞了
  local function files(lead) return vim.fn.getcompletion(lead, "file") end
  cmd("AosExec", function(o) M.exec(o.fargs, nil, o.bang) end,
    { nargs = "*", bang = true, complete = files, desc = "aos：aos-exec 跑一次（! 跑目前這個檔）" })
  cmd("AosTrace", function() M.trace() end, { desc = "aos：看 trace" })
  cmd("AosSay", function(o) M.say(o.args, o.bang) end, { nargs = "+", bang = true, desc = "aos：丟一題、等答案（! 順便跑 agent）" })
  cmd("AosGoto", function(o) M.jump(o.args) end, { nargs = "?", complete = files, desc = "aos：跳到 檔#/指標" })
  cmd("AosLuaPreview", function(o) M.lua_preview(o.args) end, { nargs = "?", desc = "aos：預覽 Lua 編出的 JSON" })
  cmd("AosLuaBuild", function(o) M.lua_build(o.args) end, { nargs = "?", complete = "dir", desc = "aos：Lua 編成資料夾" })
  return M
end

return M
