-- clocks.lua - 一個 daemon 顧幾個時鐘 loop（for 迴圈產生子項）
-- 編：aos-lua build clocks.lua <輸出>；跑：aos-exec --ws <工作區> <輸出>（PATH 要有 aos-daemon、aos-loop、aos-exec、aos-tick）
-- 每個子 loop 跑 n 次 aos-tick，跑完工作區的 .stack/clock_<n>/tick.txt 就是 n。
local aos = require("aos")

local loops = {}
for n = 1, 3 do
  loops["clock_" .. n] = aos.loop {
    exec = aos.inst { argv = { "aos-tick", aos.env("AOS_STACK", { path = "tick.txt" }) } },
    max = n,
  }
end

return aos.dir {
  _entry = { "aos-daemon", "daemon.json" },   -- 入口寫成 argv 陣列（沒 +x 的 JSON 檔），不用 sh
  ["daemon.json"] = aos.daemon { max = 15, interval_ms = 100, state = "state.json", loops = loops },
}
