-- 三格：同步問 LLM（不經 kernel）→ 塞一段 binary 進 state → 寫結果檔。
local json = require "json"
local ENDPOINT = "__PLAY__/stations/1-ask-once/endpoint.json"

local function ask(state)
  local req = {messages = {{role = "user", content = "用三個字形容今天。"}}}
  local r = aos.llm(ENDPOINT, req, here .. "/answer.json")
  state.answer = aos.llm_text(r)
end

local function stash(state)
  state.blob = aos.b64("\255\254\0 not utf-8")   -- 不是合法 UTF-8 的位元組，存檔會長成 {"$b64":"..."}，讀回來還原
end

local function write(state)
  local f = assert(io.open(here .. "/result.json", "w"))
  f:write(json.encode(state), "\n"); f:close()
end

return {
  {name = "ask", fn = ask},
  {name = "stash", fn = stash},
  {name = "write", fn = write},
}
