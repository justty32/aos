← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／loop、daemon**｜概念：[CONCEPTS 基礎設施 § loop 與 daemon](../CONCEPTS/03-基礎設施/01-inst至fsm.md#loop-與-daemon)｜規範：本檔｜實作：loop＝[aos-loop](../../cpp/aos-loop/README.md)；daemon＝[aos-daemon](../../cpp/aos-daemon/README.md)（C++，唯一實作）

同主題：[inst](03-基礎設施-inst.md)｜loop 與 daemon｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)｜[資料夾程式與執行](10-基礎設施-定義與工作區.md)

# 基礎設施／loop、daemon

> loop 是 `aos-loop [FLAGS] loop.json`（`{"exec", "max"}`，子程式退 10 就停，P-06、P-19；設定檔是唯一的位置參數，N-11）。**key 名以現行 loop.json 為準**（10-19 晚使用者定：「那就用到最新的吧」，[ideas § 22](../../thinking/2026-10/19/ideas/README.md)）：身體叫 `exec`、跑幾次叫 `max`，daemon 與窗的條文（N-06、N-07、N-11、N-28）都用這兩個字；`interval_ms`、`ctl`、`state` 也是 aos-loop 的選填 key。**起來、停下各跑一次**用選填的 `on_start`／`on_stop`（寫法同 `exec`）：`on_start` 在第一次之前跑、`on_stop` 在要退的那一刻跑，各有 `on_timeout_ms` 的期限（非負整數，0＝不限，預設 5000）；起停這兩格由 aos-loop 自己加（使用者選定，[clock-hook](../../thinking/2026-11/11/clock-hook/README.md#決定)），loop 不認得 hook，掛什麼由寫 loop.json 的人定。不論為什麼退都算停下——stop、跑完、失敗、訊號，daemon 下的 sleep、rm、收工也是（sleep 算不算，使用者「算。然後hook這邊可以細分出更多細類。目前就先這樣就好。」）；pause 不算，`kill -9` 跑不到。兩格出問題只印一行 warning，不擋起停、不改結束碼；aos-daemon 繼承 aos-loop，daemon.json 寫了也照跑（鍵名、預設期限與這兩句：代定、可翻案，[clock-hook 02](../../thinking/2026-11/11/clock-hook/02-施工結果.md#代定可翻)）。N-28、N-54 細節見 [cpp/aos-daemon](../../cpp/aos-daemon/README.md)（[ideas 10-22 § 5](../../thinking/2026-10/22/ideas/03-5-loop.md#5-loop10-22)）。state／ctl 窗在[窗](05-基礎設施-窗.md)。

> **閘（選填的 `gate`、`gate_timeout_ms`）**：跑身體之前先問一次「這拍要不要跑」的小程式，loop.json 和 daemon.json 都收（使用者 11-24「閒置輪詢這塊就是乖乖用C++重寫」、「1.a」，[規劃](../../thinking/2026-11/24/閒置輪詢C++重寫-1124/02-切法.md)）。
> - 寫法同 `exec`。`gate_timeout_ms` 是非負整數，預設 1000，0＝不限；到時間就 SIGTERM，1 秒後 SIGKILL。寫了 `gate_timeout_ms` 卻沒有 `gate`＝`CfgBad`。
> - 沒寫 `gate`＝不問，行為不變。
> - aos-loop 什麼時候問：沒暫停、到時間、在 `on_before_run` 之前。
> - 退 10＝這拍跳過：不跑身體；不算一次（`max` 不扣、`counter_runs` 不加）；`on_before_run`／`on_after_run` 不發；state 維持 `waiting`、不重寫。下一次＝現在加 `interval_ms`。
> - 退 0＝再讀一次 ctl（問的期間下的 stop、pause 照樣生效），然後照常往下走。
> - 其他碼、逾時、起不來＝stderr 一行 warning（同一個原因只印一次），照跑身體。閘只是省錢，壞了不該讓 agent 停，所以跟四個點的「失敗就收工」不同。
> - aos-daemon：在跑自己的身體（`exec`）之前問同一支閘；`aos-daemon-ctl poke --all` 提前跑的那一圈不問；沒有身體的 daemon 不問。表、信箱、子項的照顧每圈照舊，跟閘無關。
> - 細節以實作說明為準：[aos-loop docs/01](../../cpp/aos-loop/docs/01-用法.md)、[aos-daemon](../../cpp/aos-daemon/README.md)。

> **loop／daemon 不管、使用者自行承擔的事**（10-22 使用者，[ideas 10-22 § 5](../../thinking/2026-10/22/ideas/03-5-loop.md#5-loop10-22)）：
> ① 每次**沒有時間上限**：那次最後 exec 成可執行檔或 argv 陣列時，不理 SIGTERM 就一直等（那次是 inst 單子時由 aos-exec 照單子的 `grace_ms` 補 SIGKILL）——要上限自己加：在 `exec` 指的單子或 argv 檔裡 argv 前面接 `timeout`（不加 `-k` 遇到不理 SIGTERM 的照樣等），或用單子的 `timeout_ms`／`timeout_cycles`（兩者擇一；`timeout_cycles` 照 N-65 兩鐘，[tick-time 05](../../thinking/2026-11/05/tick-time/05-T5T6T8與試驗場.md)）；`exec` 陣列的第一個是 aos-exec 的目標，不能直接寫 `timeout`。
> ② 兩個 loop／daemon **共用同一份 state 檔**（本來就違反 N-09「一個 state 檔只有被控制的那個東西自己寫」）：寫的時間撞上時搶同一個暫存檔名、後到的當掉，沒撞上也會互相蓋掉內容——自己避免，或在外面接 s6-setlock 之類的鎖。
> ③ **state 寫不了**（資料夾不見、沒權限…）時，stderr 一行 `aos-loop: error: WriteFailed cannot write <檔>: <原因>`（N-43；daemon 開頭是 `aos-daemon:`）、結束碼 1，跟其他自己的錯一樣（P-21）；這時就算收到了訊號也不以 128＋N 結束。state 是在兩次之間寫的，所以發現時那次已經跑完、下一次不起（一開始就寫不了＝一次也沒跑）；檔裡的 state 停在最後寫成的那份（多半是 `running`），要看死活照 N-17 看 pid＋`started_at_ticks`。**daemon 照樣先收掉子項才結束**（P-36）：全部送 SIGTERM、等它們退，滿 10 秒還在的 SIGKILL 整群（同 N-28「收子項不阻塞」），不留孤兒；等的這段 state 照樣寫不了、不寫。一開始就寫不了時，起子項之前那份 state 就寫不了，子項一個都沒起。直接跑 aos-loop、aos-daemon 時 `$AOS_STACK` 有設但不在，起來時（設定驗過之後）自己 `mkdir -p`、建不了＝`MkdirFailed` 退 1（N-28、[N-59 第 1 件](10-基礎設施-定義與工作區/03-N-59.md)；使用者 11-11 在選項框選「loop／fsm 自己建」「也自己建」，「stack只能在aos-exec建<-這個規則刪除」，[thinking tool-cells-lazy](../../thinking/2026-11/11/tool-cells-lazy.md#線-f-裁定loopfsm-自己建11-11)），所以這條只管跑的途中資料夾被刪、沒權限這類。
> ④ loop 跑途中改 `.env`，因為 aos-exec 預設不蓋已有的環境變數（N-59 第 4 件），改過的值不生效，loop 也不會替每次加 `--dotenv-override`——要蓋就自己在 `exec` 指的單子 argv 寫旗標，旗標只管那次 aos-exec 走進的地方的 `.env`，所以要指回同一層，或重開 loop。
>
> 例：① 的上限寫 `timeout -k 5 60`；④ 指回同一層寫 `{"exec": "loop.json#/body", "body": {"argv": ["aos-exec", "--dotenv-override", "loop.json#/real"]}, "real": {"argv": ["aos-fsm", "fsm.json"]}}`。

## 分檔目錄

> 依 [STRUCTURE](../../../wf/STRUCTURE.md) 按條號拆開；N-28、N-54 再按子項拆成同名子資料夾。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-N-10](04-基礎設施-loop與daemon/01-N-10.md) | daemon：開頭（daemon 兩義）、N-10（已刪，條號留作錨點） |
| [02-N-28](04-基礎設施-loop與daemon/02-N-28.md) | daemon（續）：N-28，九份分檔在 [02-N-28/](04-基礎設施-loop與daemon/02-N-28/01-超集-命令列-exec.md) |
| [03-N-54](04-基礎設施-loop與daemon/03-N-54.md) | daemon（續）：N-54，三份分檔在 [03-N-54/](04-基礎設施-loop與daemon/03-N-54/01-手把與認的key.md) |

<a id="daemon"></a>
