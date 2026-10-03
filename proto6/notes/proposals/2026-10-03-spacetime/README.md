# aos 時空四層推演：daemon、tick 與回合、kernel、agent（2026-10-03）

← [筆記索引](../../README.md)｜**使用者的筆記（正本）：[aos 的分層](../../2026-10-03-aos-layering.md)**｜同日：[thread 與程序評估](../2026-10-03-thread-vs-process/README.md)、[astra 照最新筆記的評估](../../reviews/2026-10-03-astra-spacetime.md)、[astra 對早期筆記的意見](../../reviews/2026-10-03-astra-layering.md)｜10-02 提案：[kernel](../2026-10-02-kernel/README.md)、[agent](../2026-10-02-agent/README.md)、[Plan 9](../2026-10-02-plan9/README.md)

**這是推演，不是裁定。** 不改程式、不改 spec。依使用者 10-03 的筆記（到「同像性」與「LLM 可讀」原則為止），把四層推到具體，挖正常流程會發生的狀況。大方向是使用者的。

三種話分開標：〔使用者〕＝筆記或裁定原文（附行號）；〔推論〕＝從他的話推出來的；〔建議〕＝我們的建議。筆記裡沒逐字、只在 thread-vs-process 轉述的（daemon 變 FUSE、互不從屬、cgroup／帳號／權限拉出去），標〔使用者，經轉述〕。

**怎麼寫成的。** 一條 Fable 線帶五個子線起草，後來使用者筆記一路往前推，Fable 在改版途中卡住。01～05 由五條新線依同一份說明改到最新筆記；06、07、README 由 Claude 改寫。

## 一段話結論

〔推論〕照筆記落地，四層長這樣。**daemon** 以「相對空間根的路徑」為鍵，同時撐多條 tick-tock 時間線；其餘都是工程。**tick 與 tock** 是一條時間線上兩個很快結束的動作：tick 起頭並啟動任務，tock 告訴任務「第 N 回合結束」，回合數就是今天的 `seq`。**kernel** 是在 tick-tock 時刻對任務 kill、restart，並用 daemon ctl 讓別的時間線停止或繼續的排程任務。**agent** 是一個依託 tick-tock 在 idle、think、act 之間換狀態的任務。kernel 與 agent 都是看任務性質認定的角色，同一個 node 可以兩者皆是。跟現況真正衝突的只有一處：今天的 `aos-tick` 跑完所有任務才結束（`aos_tick.py` 第 161～186 行、`aos_tick_run.py` 第 75、86 行）。這一條一改，`ended`、鎖、hooks 的 `after_*`、結束碼誰記、daemon 週期都跟著動，其餘大多保留。kernel 要的「停止、繼續時間線」今天已有：ctl 的 `pause`、`resume`（`aos_daemon_ctl.py` 第 29 行），只差對象從一項 inst 換成 node 路徑。

## 四層一覽

| 層 | 是什麼 | 不做什麼 | 最先碰到的技術選型 |
|---|---|---|---|
| daemon（[01](01-daemon.md)） | 以 node 路徑為鍵、同時撐多條時間線；可以被任務開出來（路一），也可以被寫控制檔（路二） | cgroup、切帳號、判權限（轉述）；核心不知道從屬 | 控制檔與狀態檔長在 FUSE 樹的哪裡 |
| tick 與回合（[02](02-tick與回合.md)） | tick 起頭、啟動任務、給空間；tock 說「第 N 回合結束」；是 kernel 動手的時刻 | 不等任務、不殺任務、不排程 | tick 不等任務之後，誰記結束碼、tock 何時進場 |
| kernel（[03](03-kernel.md)） | 在 tick-tock 時刻 kill、restart 任務；用 ctl 停止、繼續別的時間線；資源與算法隨意 | 不啟動任務（只有 tick 能）；管轄範圍先不管 | 單一任務要有自己的控制入口（今天 ctl 只認一整項） |
| agent（[04](04-agent.md)） | 一個依託 tick-tock 換 idle／think／act 的任務 | 不排別人、不管資源；其他細節先不管 | 跨回合常駐、收 tock 換狀態，還是每回合啟動一次、狀態存檔 |

## LLM 可讀：整份報告的共同檢視

〔使用者〕第 7～9 行：操作和協議盡量用 JSON 或文字。每個分檔都有一節「LLM 可讀檢視」。合起來看：

- **已經符合**：inst JSON、`tasks.json`、`record.json`、daemon 設定 JSON、ctl socket 上的一行 JSON。
- **格式對但不是檔**：ctl 要靠程式連 socket。〔建議〕同一行文字或 JSON 也能寫進控制檔，[plan9 提案](../2026-10-02-plan9/03-daemon變成檔案伺服器.md)第 47～69 行已有 ctl 與 status 的樣子。
- **不符合**：kill、restart 走 Linux 訊號；重讀設定走 SIGHUP；路徑與任務身分走環境變數；`.aos/tick.lock` 是空檔；`task-exits.json` 只記非 0 的數字。
- 〔建議〕方向一致：控制動詞寫進控制檔，狀態寫成 JSON 檔，任務的出生資料（誰啟動、第幾回合、屬哪個 node）寫成任務資料夾裡的 JSON，回合資訊寫成 node 下的 JSON。訊號、pid、fd 可以留在運行層內部。欄位都不定。

細表見 [06](06-跟現況與裁定的差距.md) 的「LLM 可讀」一節。

## 完整例子的摘要（[05](05-交叉例子.md)）

daemon D 在 `/srv/aos`，三個 node：`team`（kernel）、`team/agents/amy`、`team/agents/bob`（agent），三條時間線各自計數。第 3 回合 amy 的 tick 啟動任務 A，A 數到第三次 tock 自行結束。kernel 任務 K 在 team 的 tick-tock 時刻動手：第 4 回合 restart bob 卡住的任務，第 5 回合停止 bob 的時間線，第 7 回合讓它繼續。第 7 回合 team 的 tick 生任務開子 daemon D2（路一）。每一步留下的都是 JSON 或一行文字。

〔推論〕例子裡碰到一個正常流程的後果：停止一條時間線不會殺掉它的任務，但那些任務會收不到 tock。

## 已由筆記定下、不再問

回合數每條時間線各自數（第 54 行）；重疊只管最基本的（第 55 行）；node id＝相對空間根的路徑（第 56 行）；kernel 管任務、時間單位是 tick-tock（第 66～67 行）；管時間線用 ctl（第 69 行）；agent 是狀態機任務（第 74～75 行）；daemon 控制兩條路都要、成環不管（第 83～85 行）。

## 技術問題（使用者說心裡有答案，不問）

跨 daemon 的 id；daemon 重開後回合數延不延續；回合節奏與 tock 進場時機；不同時間線的回合怎麼對照（含起始回合的 tock 算不算）；node 怎麼出生與消失；kernel 怎麼看見各 node 的任務；kernel 量不到真實資源；任務表誰能改；外部事件和人怎麼進來；失敗與結束碼怎麼被看見；FUSE 掛哪、鎖的粒度、週期起算、新舊任務並存。

## 問使用者的問題

**這一輪沒有方向題。** 剩下的都是技術選型，或使用者說留給之後的（控制塊細節、訊息交流、權限、agent 細節、管轄範圍，見 [07](07-留給之後.md)）。

## 分檔

| 檔 | 內容 |
|---|---|
| [01-daemon](01-daemon.md) | 運行層：多時間線、路一與路二、同像性能共用的、差距、LLM 可讀 |
| [02-tick與回合](02-tick與回合.md) | 時序、任務一生、對接的線、差距、LLM 可讀 |
| [03-kernel](03-kernel.md) | 收→判→動、kill／restart 與 ctl、多層、10-02 差距、LLM 可讀 |
| [04-agent](04-agent.md) | 狀態機任務的兩種讀法、被 kernel 管的方式、LLM 可讀 |
| [05-交叉例子](05-交叉例子.md) | 一 daemon、一 kernel、兩 agent、七回合逐步表，標每步留下的形式 |
| [06-跟現況與裁定的差距](06-跟現況與裁定的差距.md) | 保留／改／翻／技術選型總表；LLM 可讀不合處；翻案清單 |
| [07-留給之後](07-留給之後.md) | 控制塊、訊息交流、權限：各層在哪裡會碰到；八條線 |

## 來源

使用者筆記（到第 86 行）；spec；程式 `proto6/src/py/lib`；裁定 09、10、11；10-02 三份提案；10-03 thread-vs-process、astra-layering、astra-alt。
