local base64 = require "base64"
local M = {null = setmetatable({}, {__tostring = function() return "null" end})}

local escapes = {['"']='\\"', ['\\']='\\\\', ['\b']='\\b', ['\f']='\\f',
                 ['\n']='\\n', ['\r']='\\r', ['\t']='\\t'}

local function valid_utf8(s)
  return utf8.len(s) ~= nil
end

local function quote(s)
  return '"' .. s:gsub('[%z\1-\31\\"]', function(c)
    return escapes[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

local function table_shape(t)
  local count, max, has_string = 0, 0, false
  for k in pairs(t) do
    count = count + 1
    if type(k) == "string" then
      has_string = true
    elseif type(k) == "number" and k >= 1 and k % 1 == 0 then
      if k > max then max = k end
    else
      error("key 不是字串或整數", 0)
    end
  end
  if count == 0 then return "object", 0 end
  if not has_string and max == count then return "array", max end
  if not has_string then error("整數 key 不是 1..n 連續", 0) end
  for k in pairs(t) do
    if type(k) ~= "string" then error("key 不是字串或整數", 0) end
  end
  return "object", count
end

local function encode_value(v, seen)
  if v == M.null then return "null" end
  local kind = type(v)
  if kind == "nil" then error("nil", 0) end
  if kind == "boolean" then return tostring(v) end
  if kind == "number" then
    if v ~= v or v == math.huge or v == -math.huge then error("非有限數字", 0) end
    return string.format("%.17g", v)
  end
  if kind == "string" then
    if valid_utf8(v) then return quote(v) end
    return '{"$b64":' .. quote(base64.encode(v)) .. '}'
  end
  if kind ~= "table" then
    local names = {['function']="函式", userdata="userdata", thread="thread"}
    error(names[kind] or kind, 0)
  end
  if seen[v] then error("循環", 0) end
  seen[v] = true
  local shape, n = table_shape(v)
  local out = {}
  if shape == "array" then
    for i = 1, n do out[i] = encode_value(v[i], seen) end
    seen[v] = nil
    return "[" .. table.concat(out, ",") .. "]"
  end
  local keys = {}
  for k in pairs(v) do keys[#keys + 1] = k end
  table.sort(keys)
  for _, k in ipairs(keys) do
    out[#out + 1] = quote(k) .. ":" .. encode_value(v[k], seen)
  end
  seen[v] = nil
  return "{" .. table.concat(out, ",") .. "}"
end

function M.encode(value)
  return encode_value(value, {})
end

local function codepoint(n)
  if n >= 0xD800 and n <= 0xDFFF then error("JSON 的 Unicode surrogate 不完整", 0) end
  return utf8.char(n)
end

function M.decode(text)
  if type(text) ~= "string" then error("json.decode: 要字串", 2) end
  local pos, length = 1, #text
  local function skip()
    local _, e = text:find("^[ \t\r\n]*", pos); pos = (e or pos - 1) + 1
  end
  local parse
  local function string_value()
    pos = pos + 1
    local out = {}
    while pos <= length do
      local b = text:byte(pos)
      if b == 34 then pos = pos + 1; return table.concat(out) end
      if b < 32 then error("JSON 字串有控制字元", 0) end
      if b ~= 92 then
        local start = pos
        repeat pos = pos + 1; b = text:byte(pos) until pos > length or b == 34 or b == 92 or b < 32
        out[#out + 1] = text:sub(start, pos - 1)
      else
        local e = text:sub(pos + 1, pos + 1)
        local simple = {['"']='"', ['\\']='\\', ['/']='/', b='\b', f='\f', n='\n', r='\r', t='\t'}
        if simple[e] then out[#out + 1] = simple[e]; pos = pos + 2
        elseif e == "u" then
          local hex = text:sub(pos + 2, pos + 5)
          if not hex:match("^%x%x%x%x$") then error("JSON 的 \\u 跳脫錯誤", 0) end
          local n = tonumber(hex, 16); pos = pos + 6
          if n >= 0xD800 and n <= 0xDBFF then
            local low = text:sub(pos, pos + 5):match("^\\u(%x%x%x%x)$")
            local m = low and tonumber(low, 16)
            if not m or m < 0xDC00 or m > 0xDFFF then error("JSON 的 Unicode surrogate 不完整", 0) end
            n = 0x10000 + (n - 0xD800) * 0x400 + (m - 0xDC00); pos = pos + 6
          end
          out[#out + 1] = codepoint(n)
        else error("JSON 字串跳脫錯誤", 0) end
      end
    end
    error("JSON 字串沒有結尾", 0)
  end
  local function array_value()
    pos = pos + 1; skip(); local out = {}
    if text:sub(pos, pos) == "]" then pos = pos + 1; return out end
    while true do
      out[#out + 1] = parse(); skip()
      local c = text:sub(pos, pos); pos = pos + 1
      if c == "]" then return out end
      if c ~= "," then error("JSON 陣列缺逗號或 ]", 0) end
      skip()
    end
  end
  local function object_value()
    pos = pos + 1; skip(); local out, count = {}, 0
    if text:sub(pos, pos) == "}" then pos = pos + 1; return out end
    while true do
      if text:sub(pos, pos) ~= '"' then error("JSON 物件 key 必須是字串", 0) end
      local key = string_value(); skip()
      if text:sub(pos, pos) ~= ":" then error("JSON 物件缺冒號", 0) end
      pos = pos + 1; skip(); out[key] = parse(); count = count + 1; skip()
      local c = text:sub(pos, pos); pos = pos + 1
      if c == "}" then
        if count == 1 and type(out["$b64"]) == "string" then return base64.decode(out["$b64"]) end
        return out
      end
      if c ~= "," then error("JSON 物件缺逗號或 }", 0) end
      skip()
    end
  end
  function parse()
    skip(); local c = text:sub(pos, pos)
    if c == '"' then return string_value() end
    if c == "[" then return array_value() end
    if c == "{" then return object_value() end
    local literals = {['true']=true, ['false']=false, ['null']=M.null}
    for word, value in pairs(literals) do
      if text:sub(pos, pos + #word - 1) == word then pos = pos + #word; return value end
    end
    local tail, token = text:sub(pos)
    local patterns = {"^-?%d+%.%d+[eE][+-]?%d+", "^-?%d+[eE][+-]?%d+",
                      "^-?%d+%.%d+", "^-?%d+"}
    for _, pattern in ipairs(patterns) do
      local candidate = tail:match(pattern)
      if candidate then token = candidate; break end
    end
    if token then
      local integer = token:match("^-?(%d+)")
      if #integer == 1 or integer:sub(1, 1) ~= "0" then
        pos = pos + #token; return tonumber(token)
      end
    end
    error("JSON 值格式錯誤（第 " .. pos .. " byte）", 0)
  end
  local value = parse(); skip()
  if pos <= length then error("JSON 結尾有多餘內容", 0) end
  return value
end

return M
