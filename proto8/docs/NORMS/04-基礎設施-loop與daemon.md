← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／loop、daemon**｜概念：[CONCEPTS 基礎設施 § loop 與 daemon](../CONCEPTS/03-基礎設施/01-inst至fsm.md#loop-與-daemon)｜規範：本檔｜實作：loop＝[aos-loop](../../impls/aos-loop/README.md)；daemon＝[aos-daemon](../../impls/aos-daemon/README.md)（C++，唯一實作）

同主題：[inst](03-基礎設施-inst.md)｜loop 與 daemon｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)｜[資料夾程式與執行](10-基礎設施-定義與工作區.md)

# 基礎設施／loop、daemon

> loop 是 `aos-loop [FLAGS] loop.json`（`{"exec", "max"}`，子程式退 10 就停，P-06、P-19；設定檔是唯一的位置參數，N-11）。**key 名以現行 loop.json 為準**（10-19 晚使用者定：「那就用到最新的吧」，[ideas § 22](../../thinking/2026-10/19/ideas/README.md)）：身體叫 `exec`、跑幾次叫 `max`，daemon 與窗的條文（N-06、N-07、N-11、N-28）都用這兩個字；`interval_ms`、`ctl`、`state` 也是 aos-loop 的選填 key。N-28、N-54 都有實作（[impls/aos-daemon](../../impls/aos-daemon/README.md)；daemon 照「資料夾＝程式」重寫，使用者對計畫的五點說「照預設」，[ideas § 25](../../thinking/2026-10/19/ideas/README.md)），照程式核對後定稿（10-22，使用者「條文草稿那邊要去解決」，[ideas 10-22 § 5](../../thinking/2026-10/22/ideas/03-5-loop.md#5-loop10-22)）。state／ctl 窗在[窗](05-基礎設施-窗.md)。

> **loop／daemon 不管、使用者自行承擔的事**（10-22 使用者，[ideas 10-22 § 5](../../thinking/2026-10/22/ideas/03-5-loop.md#5-loop10-22)）：① 每次**沒有時間上限**：那次最後 exec 成可執行檔或 argv 陣列時，不理 SIGTERM 就一直等（那次是 inst 單子時由 aos-exec 照單子的 `grace_ms` 補 SIGKILL）——要上限自己加，例如在 `exec` 指的單子或 argv 檔裡 argv 前面接 `timeout -k 5 60`（不加 `-k` 遇到不理 SIGTERM 的照樣等），或用單子的 `timeout_ms`〔11-06 晚註：已實作 T5——單子也可改寫 `timeout_ticks`（跟 `timeout_ms` 擇一；有 `AOS_TICK` 數時鐘、沒有換成 ticks×`AOS_TICK_INTERVAL` 毫秒，N-65），[tick-time 05](../../thinking/2026-11/05/tick-time/05-T5T6T8與試驗場.md)〕；`exec` 陣列的第一個是 aos-exec 的目標，不能直接寫 `timeout`。② 兩個 loop／daemon **共用同一份 state 檔**（本來就違反 N-09「一個 state 檔只有被控制的那個東西自己寫」）：寫的時間撞上時搶同一個暫存檔名、後到的當掉，沒撞上也會互相蓋掉內容——自己避免，或在外面接 s6-setlock 之類的鎖。③ **state 寫不了**（資料夾不見、沒權限…）時，stderr 一行 `aos-loop: error: WriteFailed cannot write <檔>: <原因>`〔11-05 加 `error:`，N-43〕（daemon 開頭是 `aos-daemon:`）、結束碼 1，跟其他自己的錯一樣（P-21）；這時就算收到了訊號也不以 128＋N 結束。state 是在兩次之間寫的，所以發現時那次已經跑完、下一次不起（一開始就寫不了＝一次也沒跑）；檔裡的 state 停在最後寫成的那份（多半是 `running`），要看死活照 N-17 看 pid＋`started_at_ticks`。**daemon 照樣先收掉子項才結束**（P-36）：全部送 SIGTERM、等它們退，滿 10 秒還在的 SIGKILL 整群（同 N-28「收子項不阻塞」），不留孤兒；等的這段 state 照樣寫不了、不寫。一開始就寫不了時，起子項之前那份 state 就寫不了，子項一個都沒起。直接跑 aos-loop 時 `$AOS_STACK` 資料夾不在也算這種，aos-loop 不自己建——建 stack 只在 aos-exec 做（N-59 第 1 件），經 aos-exec 跑就沒事（[thinking 10-23 daemon 壓測](../../thinking/2026-10/23/daemon-bench.md)）。④ loop 跑途中改 `.env`，因為 aos-exec 預設不蓋已有的環境變數（N-59 第 4 件），改過的值不生效，loop 也不會替每次加 `--dotenv-override`——要蓋就自己在 `exec` 指的單子 argv 寫旗標，旗標只管那次 aos-exec 走進的地方的 `.env`，所以要指回同一層（例 `{"exec": "loop.json#/body", "body": {"argv": ["aos-exec", "--dotenv-override", "loop.json#/real"]}, "real": {"argv": ["aos-fsm", "fsm.json"]}}`），或重開 loop。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題（再按條號／頂層清單項）拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-N-10](04-基礎設施-loop與daemon/01-N-10.md) | daemon：開頭、N-10 |
| [02-N-28](04-基礎設施-loop與daemon/02-N-28.md) | daemon（續）：N-28 |
| [03-N-54](04-基礎設施-loop與daemon/03-N-54.md) | daemon（續）：N-54 |

<a id="daemon"></a>
