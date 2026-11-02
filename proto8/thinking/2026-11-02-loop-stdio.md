# 2026-11-02 loop／daemon 的 stdin／stdout 與 log

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜同日：[state 窗](2026-11-02-state-window.md)（log 的實作在那輪）

本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-02，逐字）

> aos體系下，stdin/out/err都可以任意指定，混在一起就是使用者自己要處理的，不用管太多。

> aos-loop和aos-daemon他們印出的log感覺都沒啥用，應該要改成默認不印。除此之外，daemon的子loop走的是aos inst格式，那應該可以自行指定stdin/out吧。然後loop/daemon的body那個，他也應該可以自行指定要走哪個stdin/out吧。

## 決定

- aos-loop／aos-daemon 的 log **預設不印**，旗標打開才印到 stdout（翻掉同日稍早的「預設開」；旗標名由 state 窗那輪實作時定）。
- stdout 跟身體的輸出混在一起是使用者自己的事，程式不另外分。

## 結論（11-02，頂層查現行程式與 README）

- **現況**：aos-loop／aos-daemon 自己不讀 stdin、不寫 stdout，只在出錯時往 stderr 寫一行；每次跑的身體**繼承** loop／daemon 的 fd 0／1／2。daemon 起子項時把子項的 stdin／stdout 接 `/dev/null`、stderr 附加到小格 `stderr.txt`。
- **身體要自己指定 stdin／stdout：現在就做得到**——`exec` 寫成**內嵌單子**（inst），用單子的 `stdin`／`stdout`／`stderr`（＋`stdout_append`／`stderr_append`）key，例 `"stdout": {"$env": "AOS_STACK", "$path": "clock.txt"}`（試驗場 daemons/main 的 clock 就是這樣寫）。`exec` 寫成字串或陣列（aos-exec 目標）＝照舊繼承，要指定就改寫成單子 `{"argv": [...], "stdout": ...}`。
- **daemon 的子 loop**：子 loop 的設定就是一份 loop.json，它的 `exec` 寫成單子就能指定那個子 loop 每次身體的 stdin／stdout；子 loop **程序本身**的 fd 仍是 daemon 定的（`/dev/null`／`stderr.txt`），子 loop 自己不讀不寫所以影響不到。
- **daemon 的 exec 型子項（`execs`）**：只收 aos-exec 目標（字串或陣列）、**不收單子**，所以目前**不能**指定 stdin／stdout（stdout 一律丟掉）。要指定得讓 `execs` 也收單子——要不要做留給使用者。
