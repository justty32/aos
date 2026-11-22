「私有地盤 `wf/ws/<agent>/`＋repo 裡的 `_stack` 取代 `~/aos-home`」的規劃入口（11-22，線 ws-stack-plan-1122、ws-stack-plan-1122b，只規劃、沒改程式、沒動活樹）。

# 工作區與 _stack：規劃（11-22）

← [2026-11-22](../README.md)｜相關：[two-machines（11-10）](../../10/two-machines/README.md)、[搬家文件](../../../../py/aos/apps/agent/docs/04-搬家.md)、[sec-1114 計劃](../../14/sec-1114/03-計劃.md)、[onboard-1114 計劃](../../14/onboard-1114/03-計劃.md)

使用者 11-22 先定了四件事：
- `_stack` 放在 `~/repo/aos/_stack`，被根 `.gitignore` 忽略，只有換機那次才 commit。
- 大家的工作區照舊是 `~/repo/aos`，另外各配一塊私有地盤 `wf/ws/<agent>/`，照掛的層級嵌套。
- 任何一層的 `temp/` 都不進 git，交件時查單檔大小。
- `_stack` 取代 `~/aos-home`。

看過第一版之後又定了幾件：
- llm kernel、權限站各台自己跑、放在 repo 外，用 `AOS_LLM_KERNEL`、`AOS_KERNEL` 指定。他說的 `AOS_PERM_KERNEL`＝`AOS_KERNEL`，`AOS_DAEMON_ROOT`＝`AOS_DAEMON`。
- 舊樹的 `eca-claude`、`ann` 不搬；公司現有的樹別管。
- export 的順序靠一份換機說明書教。
- 用量與預算不處理。

| 分檔 | 內容 |
|---|---|
| [01-決定與調查](01-決定與調查.md) | 使用者原話（逐字）、決定 A～E 與後來定的幾項、三份調查的摘要與出處（標明哪些已對過程式）、規劃員量到的活樹實況（含決定 E 之後第二輪查的環境變數怎麼傳） |
| [02-規劃](02-規劃.md) | 大白話摘要、九條線與先後（含新的線 9 換機說明書）、llm kernel 與權限站怎麼各台自己跑、每條線要改的檔與驗法、要使用者當場點頭的步驟、怎麼接上 ok-sec／ok-onboard／進度檔、要改的現行文件、邊緣狀況、要使用者決定的一題 |

狀態：規劃第二版寫完。第一版的題 2、題 3 已定；剩題 1「根那份小定義放哪」，等使用者答了才開施工線。
