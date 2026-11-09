-- clocks.lua - 一個 daemon 顧幾個時鐘 loop（for 迴圈產生子項）
-- 編：aos-lua build clocks.lua <輸出>；跑：aos-exec --ws <工作區> <輸出>（PATH 要有 aos-daemon、aos-loop、aos-exec、aos-clock）
-- 每個子 loop 跑 n 次 aos-clock，跑完工作區的 .stack/procs/clock_<n>/clock.txt 就是 n（11-03 起 daemon 的子項小格在 procs/<名字>/，11-02 是 loops/）。
local aos = require("aos")

local procs = {}
for n = 1, 3 do
  procs["clock_" .. n] = aos.loop {
    exec = aos.inst { argv = { "aos-clock", aos.env("AOS_STACK", { path = "clock.txt" }) } },
    max = n,
  }
end

return aos.dir {
  _entry = { "aos-daemon", "daemon.json" },   -- 入口寫成 argv 陣列（沒 +x 的 JSON 檔），不用 sh
  ["daemon.json"] = aos.daemon { max = 15, interval_ms = 100, state = "state.json", procs = procs },
}
