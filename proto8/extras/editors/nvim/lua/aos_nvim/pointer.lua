-- aos_nvim.pointer - 在 JSON 文字裡找 JSON 指標（RFC 6901，`/states/think/exec`）指到的值從第幾個位元組開始
-- 不用 vim.json.decode：要的是「在原文的哪裡」，decode 完位置就丟了。只認標準 JSON（aos 的 JSON 都是）。
local M = {}

local function skip_ws(s, i)
  return s:find("[^ \t\r\n]", i) or #s + 1
end

-- 讀一個字串，回 (內容, 字串後面的位置)；i 指著開頭的 "
local function read_string(s, i)
  local out, j = {}, i + 1
  while j <= #s do
    local c = s:sub(j, j)
    if c == '"' then return table.concat(out), j + 1 end
    if c == "\\" then
      local e = s:sub(j + 1, j + 1)
      local map = { n = "\n", t = "\t", r = "\r", b = "\b", f = "\f", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
      if e == "u" then
        local code = tonumber(s:sub(j + 2, j + 5), 16) or 63
        out[#out + 1] = vim.fn.nr2char(code)
        j = j + 6
      else
        out[#out + 1] = map[e] or e
        j = j + 2
      end
    else
      out[#out + 1] = c
      j = j + 1
    end
  end
  return nil, nil
end

local skip_value

-- 跳過一個值，回值後面的位置；壞了回 nil
skip_value = function(s, i)
  i = skip_ws(s, i)
  local c = s:sub(i, i)
  if c == '"' then
    local _, j = read_string(s, i)
    return j
  elseif c == "{" or c == "[" then
    local close = c == "{" and "}" or "]"
    i = skip_ws(s, i + 1)
    if s:sub(i, i) == close then return i + 1 end
    while i <= #s do
      if c == "{" then
        local _, j = read_string(s, skip_ws(s, i))
        if not j then return nil end
        i = skip_ws(s, j)
        if s:sub(i, i) ~= ":" then return nil end
        i = i + 1
      end
      i = skip_value(s, i)
      if not i then return nil end
      i = skip_ws(s, i)
      local d = s:sub(i, i)
      if d == close then return i + 1 end
      if d ~= "," then return nil end
      i = i + 1
    end
    return nil
  else
    local j = s:find("[,%]} \t\r\n]", i)
    return j or #s + 1
  end
end

local function parts(ptr)
  local out = {}
  for raw in (ptr:sub(2) .. "/"):gmatch("([^/]*)/") do
    out[#out + 1] = (raw:gsub("~1", "/"):gsub("~0", "~"))
  end
  return out
end

-- 回指到的值開頭的位元組位置（1 起算）；指不到回 nil
function M.find(s, ptr)
  local i = skip_ws(s, 1)
  if ptr == "" or ptr == nil then return i end
  if ptr:sub(1, 1) ~= "/" then return nil end
  for _, want in ipairs(parts(ptr)) do
    local c = s:sub(i, i)
    if c == "{" then
      local found = nil
      i = skip_ws(s, i + 1)
      while s:sub(i, i) == '"' do
        local key, j = read_string(s, i)
        if not j then return nil end
        j = skip_ws(s, j)
        if s:sub(j, j) ~= ":" then return nil end
        local vstart = skip_ws(s, j + 1)
        if key == want then
          found = vstart
          break
        end
        local after = skip_value(s, vstart)
        if not after then return nil end
        i = skip_ws(s, after)
        if s:sub(i, i) == "," then i = skip_ws(s, i + 1) end
      end
      if not found then return nil end
      i = found
    elseif c == "[" then
      local idx = tonumber(want)
      if not idx then return nil end
      i = skip_ws(s, i + 1)
      for _ = 1, idx do
        local after = skip_value(s, i)
        if not after then return nil end
        i = skip_ws(s, after)
        if s:sub(i, i) ~= "," then return nil end
        i = skip_ws(s, i + 1)
      end
      if s:sub(i, i) == "]" then return nil end
    else
      return nil
    end
  end
  return i
end

-- 位元組位置 → (行, 欄)，行 1 起、欄 0 起（nvim_win_set_cursor 用的）
function M.to_pos(s, offset)
  local line, last = 1, 0
  for nl in s:sub(1, offset - 1):gmatch("()\n") do
    line = line + 1
    last = nl
  end
  return line, offset - 1 - last
end

return M
