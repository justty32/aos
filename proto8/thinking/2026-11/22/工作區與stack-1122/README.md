「私有地盤 `wf/ws/<agent>/`＋repo 裡的 `_stack` 取代 `~/aos-home`」的規劃入口（11-22，線 ws-stack-plan-1122、1122b、1122c，只規劃、沒改程式、沒動活樹）。

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

看過第二版之後再定了兩件：
- 根那份小定義放 `wf/tree/root/`（「定義這塊我選a」）。
- llm kernel 預設放 `~/aos-home/llm`（「預設放aos home/llm吧」，確認後答「對」）：
  - 定義原地沿用，stack 放 `~/aos-home/.llm-stack`。
  - `~/aos-home` 不改名，往後只裝這台的 llm。
  - 舊樹其他東西搬進 `~/aos-home.old-1122/` 當退路，不刪。

| 分檔 | 內容 |
|---|---|
| [01-決定與調查](01-決定與調查.md) | 使用者原話（逐字）、決定 A～E 與後來定的幾項、三份調查的摘要與出處（標明哪些已對過程式）、規劃員三輪量到的活樹實況（第三輪是 `~/aos-home/llm` 能不能原地用、`.bak` 檔、`install.py`、舊根與 llm 的行程） |
| [02-規劃](02-規劃.md) | 大白話摘要、九條線與先後（含線 9 換機說明書）、llm kernel 與權限站怎麼各台自己跑、每條線要改的檔與驗法、舊樹怎麼收與退路、要使用者當場點頭的步驟、怎麼接上 ok-sec／ok-onboard／進度檔、要改的現行文件、邊緣狀況、要使用者決定的一題 |
| [03-線3施工](03-線3施工.md) | 線 3 做完：subagent 的 stack、帳、子 `exec.json` 的通知信箱與 parent 改存相對 daemon stack；換家目錄檢查 `home_move.py`；要重建什麼；測試結果 |
| [04-線6演練](04-線6演練.md) | 線 6 家機搬家：腳本 `wf/tools/home-move-1122/home-move` 在暫存夾用活樹抄本演練的七次結果、抓到並修好的三個 bug、13:53 第一次真跑卡在使用者的終端機分頁與修法、重新演練、收尾核對 |

狀態：線 1～6、9 已完成。線 6 家機搬家 11-22 14:12 搬好：eca-aos 與三個 subagent 住進 `~/repo/aos/_stack`，llm kernel 獨立跑（`~/aos-home/llm`、stack `~/aos-home/.llm-stack`），舊樹其他東西在 `~/aos-home.old-1122/`；13:53 第一次在 `stop-old` 失敗、自動退回（腳本把使用者的分頁算成舊樹，修在 `48478426e`），搬完 eca-aos 的 aos 工具連不上（stack 裡 `tools.json` 的相對 `$override`，修在 `89caf5117`）。線 7（改現行文件）由線 ws-stack-1122-docs 做了大部分；還沒改的：kits 包裡拼好的 `gather/`、`site.txt`，`wf/public/user-zone-mail.md` 的 `aos-user` 路徑（邊緣狀況 32），`wf/progress.json` 的 `workspace-stack-alloc`、`default-stack`。剩線 8「公司那台起 `_stack`」與題 4「公司那台的 llm kernel 放哪」（線 8 開工前答就好）。
