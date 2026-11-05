-- aos - 用 Lua table 寫 aos 的資料夾程式，編成資料夾＋JSON（嘗試，2026-10-24）
--
-- 一份 .lua 原始檔 `return` 一個節點，`aos-lua build 原始檔 輸出` 把它寫成檔案：
--   aos.dir{名字 = 節點, ...}      資料夾（名字＝檔名／子資料夾名，照字面）
--   aos.file(文字) / aos.script(文字)   純文字檔 / 可執行檔（+x）
--   一般 table                      JSON 檔（loop.json、fsm.json、_entry 寫成 argv 陣列…）
--   一般字串                        純文字檔（同 aos.file）
-- JSON 那邊的建構子只是「有名字的 table」，編出來就是原樣的 JSON 物件，順便在寫的當下查形狀：
--   aos.inst{argv = {...}, ...}     單子（N-25）        aos.loop{exec = ..., max = ...}（N-28）
--   aos.fsm{start = ..., states = ...}（N-36）         aos.daemon{loops = {...}, ...}
--   aos.env(名字, {path =, prefix =}) / aos.ref(目標, {...})   指示詞 $env / $ref（N-45）
--   aos.self_entry(程式)            ["程式", {"$env": "AOS_CF"}]：讓這份 JSON 自己就是 aos-exec 的入口
-- 不偷加東西：沒寫的 key 不補、寫什麼編什麼（C-56「寫什麼就做什麼」）。
-- 只用 Lua 5.1 的子集，lua 5.x、luajit、nvim -l 都能跑。

local M = {}

local KIND = {}   -- metatable 裡放種類的 key（不會撞到使用者的字串 key）

local function kind(v)
  local mt = type(v) == "table" and getmetatable(v)
  return mt and mt[KIND] or nil
end
M.kind = kind   -- "dir"、"file"、"inst"、"loop"、"fsm"、"daemon"、"array"、"object" 或 nil

local function tag(t, k)
  return setmetatable(t, { [KIND] = k })
end

local function fail(msg, level)
  error("aos: " .. msg, (level or 1) + 1)
end

-- ---------- 檔案與資料夾 ----------

function M.dir(t)
  if type(t) ~= "table" then fail("aos.dir needs a table", 2) end
  for name, node in pairs(t) do
    if type(name) ~= "string" or name == "" or name:find("/", 1, true) or name == "." or name == ".." then
      fail("aos.dir: a name must be a string without /: " .. tostring(name), 2)
    end
    if node == nil or type(node) == "boolean" or type(node) == "function" then
      fail("aos.dir: the value of " .. name .. " cannot be a " .. type(node), 2)
    end
  end
  return tag(t, "dir")
end

function M.file(text, opts)
  if type(text) ~= "string" then fail("aos.file needs a string", 2) end
  return tag({ text = text, x = opts and opts.x or false }, "file")
end

function M.script(text)
  if type(text) ~= "string" then fail("aos.script needs a string", 2) end
  return tag({ text = text, x = true }, "file")
end

-- 讀原始檔旁邊的檔（相對路徑從正在編的 .lua 所在資料夾算，aos-lua 編譯前設好 M.src_dir）
function M.read(path)
  if path:sub(1, 1) ~= "/" and M.src_dir then path = M.src_dir .. "/" .. path end
  local f, err = io.open(path, "rb")
  if not f then fail("cannot read " .. path .. ": " .. tostring(err), 2) end
  local s = f:read("*a")
  f:close()
  return s
end

-- ---------- JSON 的值 ----------

function M.array(t) return tag(t or {}, "array") end      -- 空陣列要明寫（空 table 預設是物件 {}）
function M.object(t) return tag(t or {}, "object") end

-- 固定順序的物件：aos.obj{{"idle", 值}, {"think", 值}}（一般 table 的 key 照「常用的在前、其餘字母序」排）
function M.obj(pairs_list)
  local t, order = {}, {}
  for i, p in ipairs(pairs_list) do
    if type(p) ~= "table" or type(p[1]) ~= "string" then fail("aos.obj: item " .. i .. " must be {name, value}", 2) end
    t[p[1]] = p[2]
    order[#order + 1] = p[1]
  end
  return setmetatable(t, { [KIND] = "object", order = order })
end

local function mods(t, m, who)
  if m == nil then return t end
  if type(m) ~= "table" then fail(who .. ": the second argument must be {path =, prefix =}", 3) end
  for k, v in pairs(m) do
    if k ~= "path" and k ~= "prefix" then fail(who .. ": unknown modifier " .. tostring(k) .. " (only path, prefix)", 3) end
    t["$" .. k] = v
  end
  return t
end

function M.env(name, m)
  if type(name) ~= "string" or name == "" then fail("aos.env needs an environment variable name", 2) end
  local t = mods(tag({ ["$env"] = name }, "object"), m, "aos.env")   -- 不寫成尾呼叫：錯誤才指得到原始檔那行
  return t
end

function M.ref(target, m)
  if type(target) ~= "string" and type(target) ~= "table" then fail("aos.ref needs a file name (or an array of file names)", 2) end
  local t = mods(tag({ ["$ref"] = target }, "object"), m, "aos.ref")
  return t
end

local function is_directive(v)
  return type(v) == "table" and (v["$env"] ~= nil or v["$ref"] ~= nil)
end

function M.self_entry(prog)
  return { prog, M.env("AOS_CF") }
end

-- ---------- 單子、loop、fsm、daemon：原樣的物件＋寫的當下查形狀 ----------

function M.inst(t)
  if type(t) ~= "table" then fail("aos.inst needs a table", 2) end
  local argv = t.argv
  if not is_directive(argv) then
    if type(argv) ~= "table" or #argv == 0 then fail("aos.inst needs a non-empty argv", 2) end
    for i, a in ipairs(argv) do
      if type(a) ~= "string" and not is_directive(a) then
        fail("aos.inst: argv[" .. i .. "] must be a string or a directive", 2)
      end
    end
  end
  return tag(t, "inst")
end

-- exec＝字串（aos-exec 的目標）、非空陣列（[目標, 參數...]）、單子、或指示詞
local function check_exec(v, who)
  if type(v) == "string" then
    if v == "" then fail(who .. ": exec is an empty string", 3) end
    return
  end
  if is_directive(v) or kind(v) == "inst" then return end
  if type(v) == "table" and v.argv ~= nil then return end   -- 沒用 aos.inst 包的單子也收
  if type(v) == "table" and #v > 0 then
    for i, a in ipairs(v) do
      if type(a) ~= "string" then fail(who .. ": exec[" .. i .. "] must be a string", 3) end
    end
    return
  end
  fail(who .. ": exec must be a string, [target, args...], an instruction or a directive", 3)
end

function M.loop(t)
  if type(t) ~= "table" then fail("aos.loop needs a table", 2) end
  if t.exec == nil then fail("aos.loop: exec is missing", 2) end
  check_exec(t.exec, "aos.loop")
  return tag(t, "loop")
end

-- states 兩種寫法：{idle = {exec =, next =}, ...}，或照順序的陣列 {{"idle", exec =, next =}, ...}
function M.fsm(t)
  if type(t) ~= "table" then fail("aos.fsm needs a table", 2) end
  local states = t.states
  if type(states) ~= "table" then fail("aos.fsm: states is missing", 2) end
  if #states > 0 then
    local list = {}
    for i, s in ipairs(states) do
      if type(s) ~= "table" or type(s[1]) ~= "string" then fail("aos.fsm: states[" .. i .. "] must be {name, exec =, next =}", 2) end
      list[#list + 1] = { s[1], { exec = s.exec, next = s.next } }
    end
    states = M.obj(list)
    t.states = states
  end
  if type(t.start) ~= "string" or states[t.start] == nil then
    fail("aos.fsm: start (" .. tostring(t.start) .. ") is not in states", 2)
  end
  for name, cell in pairs(states) do
    if type(cell) ~= "table" then fail("aos.fsm: state " .. name .. " must be {exec =, next =}", 2) end
    check_exec(cell.exec, "aos.fsm: state " .. name)
    if type(cell.next) ~= "string" or states[cell.next] == nil then
      fail("aos.fsm: next of state " .. name .. " (" .. tostring(cell.next) .. ") is not in states", 2)
    end
    if cell.next:match("^%s") or cell.next:match("%s$") or cell.next:find("\n", 1, true) then
      fail("aos.fsm: next of state " .. name .. " cannot start or end with spaces or newlines", 2)
    end
  end
  return tag(t, "fsm")
end

function M.daemon(t)
  if type(t) ~= "table" then fail("aos.daemon needs a table", 2) end
  -- 11-03 loops／execs 統稱 procs：一份名單，每項看寫法（字串、陣列、只有 exec〔＋ws、stack〕＝跑一次；其他＝loop 型）
  if t.procs ~= nil and type(t.procs) ~= "table" then fail("aos.daemon: procs must be a table", 2) end
  for name, sub in pairs(t.procs or {}) do
    if type(sub) == "table" and kind(sub) ~= "loop" and not is_directive(sub) and sub.exec == nil and sub.argv == nil then
      fail("aos.daemon: proc " .. tostring(name) .. " must be a loop config or a target", 2)
    end
  end
  return tag(t, "daemon")
end

-- ---------- JSON 編碼（排好順序、兩格縮排、UTF-8 原樣輸出） ----------

local FIRST = {
  "_entry", "kind", "start", "states", "exec", "next", "argv", "cwd", "env", "stdin", "stdout", "stderr",
  "timeout_ms", "grace_ms", "max", "interval_ms", "ctl", "state", "procs", "stack",
  "$env", "$ref", "$path", "$prefix", "description", "type", "properties", "required",
}
local RANK = {}
for i, k in ipairs(FIRST) do RANK[k] = i end

local function sorted_keys(t)
  local mt = getmetatable(t)
  if mt and mt.order then return mt.order end
  local keys = {}
  for k in pairs(t) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b)
    local ra, rb = RANK[a] or 1000, RANK[b] or 1000
    if ra ~= rb then return ra < rb end
    return a < b
  end)
  return keys
end

local function is_array(t)
  local k = kind(t)
  if k == "array" then return true end
  if k and k ~= "array" then return false end
  local n = #t
  if n == 0 then return false end
  local count = 0
  for key in pairs(t) do
    if type(key) ~= "number" or key < 1 or key > n or key % 1 ~= 0 then return false end
    count = count + 1
  end
  return count == n
end

local ESC = { ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }

local function str(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    return ESC[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

local function num(n, where)
  if n ~= n or n == math.huge or n == -math.huge then fail(where .. ": JSON has no NaN or infinity") end
  if n % 1 == 0 and n >= -2 ^ 53 and n <= 2 ^ 53 then return string.format("%d", n) end
  return string.format("%.17g", n)
end

-- 一行放得下（每項都是一行、合起來不長）就寫成一行
local function short(parts)
  local n = 0
  for _, p in ipairs(parts) do
    if p:find("\n", 1, true) then return false end
    n = n + #p + 2
  end
  return n <= 60
end

local function encode(v, indent, where, seen)
  local t = type(v)
  if t == "string" then return str(v) end
  if t == "number" then return num(v, where) end
  if t == "boolean" then return tostring(v) end
  if v == nil or v == M.null then return "null" end
  if t ~= "table" then fail(where .. ": JSON cannot hold a " .. t) end
  local k = kind(v)
  if k == "dir" or k == "file" then fail(where .. ": a folder or file node cannot go inside JSON") end
  if seen[v] then fail(where .. ": the table contains itself") end
  seen[v] = true
  local pad, pad2 = string.rep("  ", indent), string.rep("  ", indent + 1)
  local out = {}
  if is_array(v) then
    local simple = true
    for _, x in ipairs(v) do if type(x) == "table" then simple = false end end
    for i, x in ipairs(v) do out[i] = encode(x, indent + 1, where .. "/" .. (i - 1), seen) end
    seen[v] = nil
    if simple or short(out) then return "[" .. table.concat(out, ", ") .. "]" end
    return "[\n" .. pad2 .. table.concat(out, ",\n" .. pad2) .. "\n" .. pad .. "]"
  end
  for _, key in ipairs(sorted_keys(v)) do
    if type(key) ~= "string" then fail(where .. ": object keys must be strings (" .. tostring(key) .. ")") end
    out[#out + 1] = str(key) .. ": " .. encode(v[key], indent + 1, where .. "/" .. key, seen)
  end
  seen[v] = nil
  if #out == 0 then return "{}" end
  if short(out) then return "{" .. table.concat(out, ", ") .. "}" end
  return "{\n" .. pad2 .. table.concat(out, ",\n" .. pad2) .. "\n" .. pad .. "}"
end

M.null = setmetatable({}, { [KIND] = "null" })

function M.json(v, where)
  return encode(v, 0, where or "#", {}) .. "\n"
end

-- ---------- 攤平成檔案清單 ----------

-- 回 {{path=相對路徑, text=內容, x=是否+x, value=JSON 的 Lua 值或 nil, dir=true/nil}, ...}，照路徑排序
function M.render(node, prefix)
  local list = {}
  local function walk(n, path)
    local k = kind(n)
    if k == "dir" then
      if path ~= "" then list[#list + 1] = { path = path, dir = true } end
      for name, child in pairs(n) do walk(child, path == "" and name or path .. "/" .. name) end
    elseif k == "file" then
      list[#list + 1] = { path = path, text = n.text, x = n.x }
    elseif type(n) == "string" then
      list[#list + 1] = { path = path, text = n, x = false }
    elseif type(n) == "table" or type(n) == "number" then
      list[#list + 1] = { path = path, text = M.json(n, path .. "#"), x = false, value = n }
    else
      fail(path .. ": cannot write this as a file (" .. type(n) .. ")")
    end
  end
  walk(node, prefix or "")
  table.sort(list, function(a, b) return a.path < b.path end)
  return list
end

-- JSON 指標（RFC 6901）走 Lua 值：pointer("/states/think") → 值；指不到回 nil
function M.pointer(v, ptr)
  if ptr == "" then return v end
  if ptr:sub(1, 1) ~= "/" then return nil end
  for raw in (ptr:sub(2) .. "/"):gmatch("([^/]*)/") do
    local part = raw:gsub("~1", "/"):gsub("~0", "~")   -- lua 5.5 的迴圈變數不能改，另開一個
    if type(v) ~= "table" then return nil end
    if is_array(v) then v = v[(tonumber(part) or -1) + 1] else v = v[part] end
    if v == nil then return nil end
  end
  return v
end

-- 跑一份原始檔，回它 return 的節點（M.src_dir 設成原始檔所在資料夾，aos.read 用）
function M.load(src)
  local dir = src:match("^(.*)/[^/]*$") or "."
  local chunk, err = loadfile(src)
  if not chunk then error({ code = "SourceBad", msg = err }, 0) end
  local saved = M.src_dir
  M.src_dir = dir
  local ok, node = pcall(chunk)
  M.src_dir = saved
  if not ok then error({ code = "SourceBad", msg = tostring(node) }, 0) end
  if node == nil then error({ code = "SourceBad", msg = src .. " returns nothing" }, 0) end
  return node
end

return M
