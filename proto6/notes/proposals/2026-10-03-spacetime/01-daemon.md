# 01 daemon：運行層

← [入口](README.md)｜使用者筆記：[aos 的分層](../../2026-10-03-aos-layering.md)

## 1 它是什麼

〔使用者〕daemon 是 aos 與 Linux 的介面（筆記第 13 行）；空間邊界＝它能訪問的資料夾（第 33 行）；出事交給它（第 36 行）；tick 把任務和它對接（第 44 行）。它是核心設施，膨脹只為工程問題（第 50 行）；要同時跑多條 tick-tock 時間線，一條管一個資料夾＝node（第 54 行）；node id＝相對空間根的路徑（第 56 行）；重疊只管最基本的（第 55 行）。daemon 與 tick-tock 剩技術選型、邊做邊調（第 61 行）。

〔推論〕核心一句：**以路徑為鍵，同時撐多條時間線**。撐空間、發動 tick／tock、管任務、接手出事，都是工程。「最基本的重疊」＝同一 daemon 內一資料夾一條時間線；巢狀放行。這個 node 不是封存的登記樹（T-02，[terms](../../../spec/terms.md) 第 39 行）。
〔使用者，經 thread-vs-process 轉述，[README](../2026-10-03-thread-vs-process/README.md) 第 5 行〕不做 cgroup、不切帳號；用哪個使用者開就是誰的權限。
〔推論〕漏上來的 Linux 概念：uid 與檔案 mode 漏到空間（誰能寫誰的資料夾＝誰能指揮誰，T-08）；pid 留在運行層，kill 要用。

## 2 具體長相

〔使用者〕FUSE 與 tick 能碰的資料夾整合、以後者為正統、傾向整棵穿透（第 37～38 行）；任務讀寫可不經 FUSE（第 40 行）。

〔推論〕照 05 的例子：

```text
/srv/aos.d/   底層真資料夾，daemon 自己只讀寫這裡
/srv/aos/     掛載點＝空間根＝id 起點
  team/.aos/…              node「team」的表與紀錄
  team/agents/amy/.aos/d/  合成的控制與狀態檔
```

daemon 不碰自己掛的樹（[02](../2026-10-03-thread-vs-process/02-分層.md) 第 45 行）。整棵穿透後更嚴：tick 若是 daemon 內的 lib，也得走底層。

**一回合**（〔推論〕）：到點 → 起 tick → 登記 tick 啟動的任務 → 等「都完」或「時間到」→ 起 tock。回合數每 node 各算（〔使用者〕第 54 行；今天 `seq` 已是，[aos_tick_record.py](../../../src/py/lib/aos_tick_record.py) 第 101～102 行）。

**一項是什麼**（〔推論〕）：一項＝一條時間線，鍵是 node 路徑。其他程式都是某 node 表上的任務。子 daemon 也是任務。

**daemon 被控制的兩條路**（〔使用者〕第 82～85 行）：
- 路一：某時間線的 tick 生任務，任務開 daemon。子 daemon 對父時間線是普通任務；空間在 tick 給的資料夾裡；核心不知道從屬。〔推論〕10-02 的「上層 daemon 把下層當一項跑」（[kernel 03](../2026-10-02-kernel/03-推薦方案.md) 第 84～102 行）換成「下層是上層某 node 的任務」，daemon 表上不必有它。
- 路二：寫別的 daemon 的控制檔；與 kernel 用 ctl 停／續時間線（第 69 行）同一個動作。
- 控制成環不管（第 85 行）。

**同像性**（〔使用者〕第 79～81 行：時間線像大號任務，只在實作上共用）。〔推論〕可共用：控制動詞（停、續、kill、restart）、FUSE 節點形狀（ctl＋status）、狀態格式、id 規則（相對路徑）、生命週期骨架（出生、跑、結束）。不能共用：daemon 撐空間、時間線發時間，兩者不是誰的任務；時間線不能被 tick 生出來。

## 3 跟現況的差距

| 現況 | 去向 |
|---|---|
| 一項一條 thread（[aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 181～182 行）；一項＝inst 字面值（[core](../../../spec/daemon/core.md) 第 13 行） | 保留 thread；鍵改 node 路徑 |
| `running`＝aos-exec 未結束；週期從結束起算（run 第 102、115、122～123 行） | 改：tick 幾毫秒就回，「在回合中」＝tick 已回、tock 未到 |
| 不讀表 | 半翻：要發 tock 就得知道這 node 有誰在跑 |
| socket＋env（run 第 163～178 行；[26](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md) 第 31 行） | 翻：路徑取代 |
| cgroup、帳號模組 | 翻：搬暫緩（[06](../2026-10-03-thread-vs-process/06-裁定對照.md) 第 28 行） |
| SIGTERM 不殺不等（[aos_daemon.py](../../../src/py/lib/aos_daemon.py) 第 77～80 行）；人手跑 tick 等價（[tick](../../../spec/tick.md) 第 39 行） | 保留 |

## 4 邊緣（正常流程會發生）

1. daemon 重開時任務還在跑：舊對接斷，新 daemon 不認得它們，收不到 tock；新 tick 再啟動＝新舊並存。
2. 巢狀（team 包 amy）兩條時間線各走各的 `seq`。跨 daemon 管同一資料夾是外部世界：兩邊輪流推 `seq`，整棵穿透時第二個掛不上。
3. daemon 死後掛載點回 ENOTCONN（[plan9 03](../2026-10-02-plan9/03-daemon變成檔案伺服器.md) 第 107 行），整棵穿透連普通檔都讀不到；殘留任務會留住它（[plan9 10](../2026-10-02-plan9/10-daemon跑daemon.md) 第 49 行）。
4. 路一的子 daemon 被父時間線 kill：它掛的樹跟著斷，邊緣同 3。

## 5 LLM 可讀檢視

〔使用者〕操作與協議盡量用 JSON 或文字（第 7～9 行）。

| 項目 | 今天 | 符合 | 〔建議〕 |
|---|---|---|---|
| daemon 設定、state | JSON 檔（[aos_daemon_state.py](../../../src/py/lib/aos_daemon_state.py) 第 66 行） | 是 | 保留 |
| 控制 | socket 一行 JSON（[aos_daemon_ctl.py](../../../src/py/lib/aos_daemon_ctl.py) 第 94、100 行） | 半：是 JSON，不是檔 | 一行文字或 JSON 寫進 ctl 檔（plan9 03 第 49～59 行） |
| 狀態 | ctl 回一行 JSON；stdout 一行 key=value | 半 | status 寫成 JSON 檔（plan9 03 第 63～67 行是 key=value） |
| 停機、kill／restart | SIGTERM；爬 /proc 送訊號（[aos_daemon_kill.py](../../../src/py/lib/aos_daemon_kill.py) 第 11～35 行） | 否 | 動詞寫進控制檔，訊號留在運行層裡 |
| 任務身分 | env `AOS_DAEMON_*`（run 第 163～178 行）、`AOS_TICK_CWD`（C-10） | 否 | 出生資料寫成任務資料夾裡的 JSON |
| 互斥 | flock 空檔（aos_daemon.py 第 125～130 行） | 否：看不出誰持有 | 旁邊放 JSON 說誰持有 |
| 回合資訊 | record.json | 是 | 寫在 node 下 |
| 結束 | 只看結束碼，B-633 只記非 0 | 半 | 結束原因寫進狀態 JSON |

## 6 已由筆記定下

- 多條時間線同時跑，一條一個 node，各自計數（第 54 行）。
- node id＝相對空間根路徑（第 56 行）。
- 重疊只管最基本的（第 55 行）。
- 跨時間線控制＝daemon ctl 停／續（第 69 行）。
- daemon 可當任務開（路一），也可被寫控制檔（路二）（第 83～84 行）。
- 控制成環不管（第 85 行）。
- 同像性只在實作上共用（第 80～81 行）。

## 7 技術問題（使用者說心裡有答案，不問）

- FUSE 掛哪（整棵、側樹、不掛）。
- 一項的最終形狀。
- 鎖的粒度。
- 週期從哪起算、誰叫 tock。
- 結束碼誰記。
- daemon 重開後回合數延續與舊任務重對接。
- 時間線之間怎麼對照。
- 跨 daemon 的 id。
- node 的出生與消失。

## 8 留給之後

- tick 把任務交給 daemon 的線。
- 任務回報「做完了」的線（tock 的「都完」靠它）。
- tock 通知回合數的線。
- kill／restart：需要 pid、pgid 或 cgroup 之一。
- 控制權限（路二能不能寫）。
- daemon 接手出事的線。
