local M = {}

local function source_mtime(path, shquote)
  local p = io.popen("stat -c %Y -- " .. shquote(path), "r")
  if not p then return nil end
  local value = p:read("*l"); p:close(); return tonumber(value)
end

local function validate_steps(value)
  if type(value) ~= "table" then error("PROG 最後必須 return 步驟陣列", 0) end
  local n = #value
  for key in pairs(value) do
    if type(key) ~= "number" or key < 1 or key % 1 ~= 0 or key > n then
      error("PROG 最後必須 return 1..n 連續的步驟陣列", 0)
    end
  end
  local names = {}
  for i = 1, n do
    local item = value[i]
    if type(item) ~= "table" or type(item.name) ~= "string" or item.name == "" then
      error("PROG 第 " .. (i - 1) .. " 格缺 name", 0)
    end
    if type(item.fn) ~= "function" then error("PROG 第 " .. (i - 1) .. " 格缺 fn", 0) end
    names[i] = item.name
  end
  return value, names
end

local function declared_functions(source)
  local found, seen, line_no = {}, {}, 0
  for line in (source .. "\n"):gmatch("(.-)\n") do
    line_no = line_no + 1
    for name in line:gmatch("function%s+([%a_][%w_]*)%s*%(") do
      if not seen[name] then
        found[#found + 1] = {name=name, line=line_no}
        seen[name] = true
      end
    end
  end
  return found
end

local function warn_unlisted(source, steps)
  local missing = {}
  for _, declared in ipairs(declared_functions(source)) do
    if declared.name:sub(1, 1) ~= "_" then
      local listed = false
      for _, item in ipairs(steps) do
        local info = debug.getinfo(item.fn, "S") or {}
        if item.name == declared.name or _G[declared.name] == item.fn or info.linedefined == declared.line then
          listed = true
          break
        end
      end
      if not listed then missing[#missing + 1] = declared.name end
    end
  end
  if #missing > 0 then
    io.stderr:write("這些函式沒列進 return 表，不會被執行：" .. table.concat(missing, ", ") .. "\n")
  end
end

function M.load(prog, pc, user_state, source, aos, dirname, shquote)
  _G.state, _G.here, _G.pc, _G.aos = user_state, dirname(prog), pc, aos
  local chunk, syntax = loadfile(prog)
  if not chunk then error("載不起 PROG：" .. tostring(syntax):match("^[^\n]*"), 0) end
  local ok, result = pcall(chunk)
  if not ok then error("載不起 PROG：" .. tostring(result):match("^[^\n]*"), 0) end
  local steps, names = validate_steps(result)
  warn_unlisted(source, steps)
  local src = {n=#steps, size=#source, mtime=source_mtime(prog, shquote), steps=names}
  return steps, names, src
end

return M
