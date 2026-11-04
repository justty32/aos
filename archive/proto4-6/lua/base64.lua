local M = {}

local alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local reverse = {}
for i = 1, #alphabet do reverse[alphabet:byte(i)] = i - 1 end

function M.encode(s)
  assert(type(s) == "string", "base64.encode: 要字串")
  local out = {}
  for i = 1, #s, 3 do
    local a, b, c = s:byte(i, i + 2)
    local n = a * 65536 + (b or 0) * 256 + (c or 0)
    out[#out + 1] = alphabet:sub(n // 262144 + 1, n // 262144 + 1)
    out[#out + 1] = alphabet:sub((n // 4096) % 64 + 1, (n // 4096) % 64 + 1)
    out[#out + 1] = b and alphabet:sub((n // 64) % 64 + 1, (n // 64) % 64 + 1) or "="
    out[#out + 1] = c and alphabet:sub(n % 64 + 1, n % 64 + 1) or "="
  end
  return table.concat(out)
end

function M.decode(s)
  assert(type(s) == "string", "base64.decode: 要字串")
  if #s % 4 ~= 0 or s:find("[^A-Za-z0-9+/=]") then error("base64.decode: 格式錯誤", 2) end
  local out = {}
  for i = 1, #s, 4 do
    local c1, c2, c3, c4 = s:byte(i, i + 3)
    if not reverse[c1] or not reverse[c2] or (c3 ~= 61 and not reverse[c3])
        or (c4 ~= 61 and not reverse[c4]) or (c3 == 61 and c4 ~= 61)
        or ((c3 == 61 or c4 == 61) and i + 3 ~= #s) then
      error("base64.decode: 格式錯誤", 2)
    end
    local n = reverse[c1] * 262144 + reverse[c2] * 4096
        + (reverse[c3] or 0) * 64 + (reverse[c4] or 0)
    out[#out + 1] = string.char(n // 65536)
    if c3 ~= 61 then out[#out + 1] = string.char((n // 256) % 256) end
    if c4 ~= 61 then out[#out + 1] = string.char(n % 256) end
  end
  return table.concat(out)
end

return M
