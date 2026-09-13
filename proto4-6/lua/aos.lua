local json = require "json"
local base64 = require "base64"
local M = {}

local source = debug.getinfo(1, "S").source:sub(2)
local lua_dir = source:match("^(.*)/[^/]+$") or "."
local proto_dir = lua_dir:match("^(.*)/lua$") or (lua_dir .. "/..")
local repo_dir = proto_dir:match("^(.*)/[^/]+$") or (proto_dir .. "/..")
local default_exec = repo_dir .. "/proto4-3/aos-exec"
local default_llm = repo_dir .. "/proto4-5/aos-llm"

local function shquote(s)
  s = tostring(s)
  return "'" .. s:gsub("'", "'\\''") .. "'"
end

local function exit_code(a, why, code)
  if a == true then return 0 end
  if why == "exit" then return code or 1 end
  if type(a) == "number" then return a end
  return code or 1
end

local function read_file(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local value = f:read("*a"); f:close(); return value
end

local function write_file(path, value)
  local f, err = io.open(path, "wb")
  if not f then error(err, 2) end
  local ok, write_err = f:write(value)
  f:close()
  if not ok then error(write_err, 2) end
end

local function temp_file()
  local path = os.tmpname()
  if not path then error("aos.call: 建不了暫存檔", 2) end
  return path
end

local function is_dir(path)
  local a, why, code = os.execute("test -d " .. shquote(path))
  return exit_code(a, why, code) == 0
end

function M.call(target, opts)
  opts = opts or {}
  if type(opts) ~= "table" then error("aos.call: opts 必須是 table", 2) end
  local argv = {os.getenv("AOS_EXEC") or default_exec, target}
  if opts.dir_target ~= nil then argv[#argv + 1] = "--dir-target"; argv[#argv + 1] = opts.dir_target end
  if opts.timeout_ms ~= nil then
    if type(opts.timeout_ms) ~= "number" or opts.timeout_ms < 0 or opts.timeout_ms % 1 ~= 0 then
      error("aos.call: timeout_ms 必須是非負整數", 2)
    end
    argv[#argv + 1] = "--timeout-ms"; argv[#argv + 1] = tostring(opts.timeout_ms)
  end
  local stderr_target = rawget(_G, "AOS_STEP_STDERR") or os.getenv("AOS_STEP_STDERR")
  if stderr_target then argv[#argv + 1] = "--stderr"; argv[#argv + 1] = stderr_target end
  local command = {}
  for _, value in ipairs(argv) do command[#command + 1] = shquote(value) end
  local stdin_path, err_path = nil, temp_file()
  if opts.stdin ~= nil then stdin_path = temp_file(); write_file(stdin_path, tostring(opts.stdin)) end
  local shell = table.concat(command, " ")
  if stdin_path then shell = shell .. " < " .. shquote(stdin_path) end
  shell = shell .. " 2> " .. shquote(err_path)
  local code, out
  if opts.capture then
    local pipe, open_err = io.popen(shell, "r")
    if not pipe then os.remove(err_path); if stdin_path then os.remove(stdin_path) end; error(open_err, 2) end
    out = pipe:read("*a")
    local a, why, n = pipe:close(); code = exit_code(a, why, n)
  else
    local a, why, n = os.execute(shell); code = exit_code(a, why, n)
  end
  local err = read_file(err_path) or ""
  os.remove(err_path); if stdin_path then os.remove(stdin_path) end
  if stderr_target == "-" and err ~= "" then io.stderr:write(err) end
  local kind = "child"
  if code == 125 then kind = "aos"
  elseif code == 2 and err:match("^aos%-exec:") then kind = "usage" end
  if opts.read ~= nil then out = read_file(opts.read) end
  if opts.read_err ~= nil then err = read_file(opts.read_err) end
  local decoded = json.null
  if opts.json and out ~= nil and out ~= "" then
    local ok, value = pcall(json.decode, out)
    if ok then decoded = value end
  end
  return {code=code, kind=kind, out=out == nil and json.null or out,
          err=err == nil and json.null or err, value=decoded}
end

function M.call_dir(dir, opts)
  if not is_dir(dir) then error("aos.call_dir: 不是資料夾：" .. tostring(dir), 2) end
  return M.call(dir, opts)
end

function M.call_json(path, opts)
  if type(path) ~= "string" or not path:match("%.json$") then
    error("aos.call_json: 不是 .json 路徑：" .. tostring(path), 2)
  end
  return M.call(path, opts)
end

function M.ok(result)
  return type(result) == "table" and result.kind == "child" and result.code == 0
end

function M.value(result)
  if type(result) ~= "table" then return nil end
  return result.value ~= nil and result.value ~= json.null and result.value or
      (result.out ~= json.null and result.out or nil)
end

function M.b64(s) return base64.encode(s) end
function M.unb64(s) return base64.decode(s) end

function M.llm(endpoint, req, out, timeout_ms)
  if type(req) ~= "table" then error("aos.llm: req 必須是 table", 2) end
  if timeout_ms ~= nil and (type(timeout_ms) ~= "number" or timeout_ms < 0 or timeout_ms % 1 ~= 0) then
    error("aos.llm: timeout_ms 必須是非負整數", 2)
  end
  write_file(out .. ".req.json", json.encode(req) .. "\n")
  local argv = {os.getenv("AOS_LLM") or default_llm, "call", endpoint, out .. ".req.json", out}
  if timeout_ms ~= nil then argv[#argv + 1] = "--timeout-ms"; argv[#argv + 1] = tostring(timeout_ms) end
  local command = {}; for _, value in ipairs(argv) do command[#command + 1] = shquote(value) end
  os.execute(table.concat(command, " "))
  local raw = read_file(out)
  if raw then
    local ok, value = pcall(json.decode, raw)
    if ok and type(value) == "table" then return value end
  end
  return {ok=false, error={kind="no_result"}}
end

function M.llm_text(result)
  if type(result) == "table" and result.ok == true then return result.text end
  return nil
end

return M
