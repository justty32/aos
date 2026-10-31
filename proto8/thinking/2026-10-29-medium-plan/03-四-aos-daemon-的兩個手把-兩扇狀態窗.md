← [入口](../2026-10-29-medium-plan.md)｜涵蓋：四、aos-daemon 的兩個手把、兩扇狀態窗（決定 2、3、20）、五、鎖：本設計怎麼用（決定 5、10、18；N-15 仍是草稿）、六、父子交代（決定 28）：現有的夠不夠｜上一份 [02-二-投遞](02-二-投遞.md)｜下一份 [04-七-身分-擁有與收屍-介質可套-人算-proc](04-七-身分-擁有與收屍-介質可套-人算-proc.md)

## 四、aos-daemon 的兩個手把、兩扇狀態窗（決定 2、3、20）

### 1. 命名與位置（C-54：窗名由程式自訂、daemon.json 的 key 跟著現行 `ctl`／`state`）

| 面向 | 手把（人寫） | 狀態窗（daemon 寫） | daemon.json 的 key（路徑，相對 `$AOS_STACK`） |
|---|---|---|---|
| loop 面向與自身屬性 | `ctl.json` | `state.json` | `ctl`、`state`（現行，不變；跟 aos-loop 同一套，N-28 超集照舊） |
| 管轄的 aos 函數 | `loops_ctl.json` | `loops_state.json` | `loops_ctl`、`loops_state`（新；沒寫＝預設這兩個名字；寫 `null`＝不開） |

- `ctl.json` 只認 loop 那幾個：`paused`、`stopped`、`max`、`interval_ms`、`seq`（N-07、N-33）。**不再認 `loops`／`loops_added`／`loops_removed`**：寫了＝不認得的 key、忽略（C-48；「不留舊名」是 NORMS 的既定做法，衝突 5）。
- `loops_ctl.json` 認 `loops`、`loops_added`、`loops_removed`、`seq`，語意照 N-54 一字不改（宣告式、先加後減、整份壞就不採用）。
- `state.json` 照 N-17／N-32：`kind`、`phase`、`counter_runs`、`max`、`interval_ms`、`paused`、`ctl_seq`、`ctl_warning`、心跳四欄（`pid`、`started_at_ticks`、`boot_id`、`recorded_at`）、收尾的 `code`。**拿掉 `loops` 表**。
- `loops_state.json`：`kind: "state"`、`loops` 表（每列照現行：`pid`、`started_at_ticks`、`phase`、`code`、`signal`；超過 100 列照 N-28 切成 `loops_state_loops/<雜湊>.json`，分頁資料夾名跟著窗名）、`ctl_seq`（回的是 `loops_ctl.json` 的 seq）、`ctl_warning`（壞的 `loops_ctl`）、`letter_warning`（信箱模式的壞信，§ 二 4）、同一組心跳四欄（同一個行程、同一個值；讀這扇窗的人才不用再開另一扇判死活，N-17「每扇 state 都帶心跳」）。
- 撞名規則（N-28 10-22 落實）跟著多兩個名字：子項不能叫 `loops_ctl`、`loops_state`、`loops_state_loops`。`adopt` 改讀 `loops_state.json`。

### 2. 同一圈兩邊都改了怎麼處理（決定 3「剩下都是細節」，這裡代定）

每圈開頭先讀 `ctl.json`、再讀 `loops_ctl.json`，各自獨立採用或不採用（一份壞不影響另一份）。順序：`stopped`＝這圈收工（照 P-36 收子項），不再看管轄；`paused`＝**整圈暫停**：不起自己的 `exec`、**也不調表**（名單的變動等解除暫停那圈才生效），但照寫兩扇 state、照讀兩份 ctl、照收已送 SIGTERM 的子項。理由：daemon 的「一次」就是「調整管轄的那一圈」（決定 2），暫停 loop 面向＝暫停那一圈；要凍結名單又讓 daemon 跑 `exec`，就別寫新的 `loops_ctl`。可翻案。

### 3. 管轄的第二種模式：信箱（aos-daemon-2，決定 4、20）

- daemon.json 多一個選填 key `loops_mailbox`（路徑，相對 `$AOS_STACK`，例 `"loops_mailbox": "loops_mailbox"`）。**寫了＝信箱模式**：daemon 建好四格、每圈照 § 二 4 處理全部的信；這時 `loops_ctl` 不開（兩個都寫＝`CfgBad` 退 1——決定 20 說哪個負責由設計者定，aos-daemon 這支就定「二選一」）。
- 信的 `body` 就是管轄手把的片段：`{"loops_added": {...}}`、`{"loops_removed": [...]}`，寫法同 N-54。沒有 `loops`（整份名單）那個 key——信是「增減」，整份宣告留給 ctl 模式。
- **期望表**＝daemon.json 的 `loops` ＋ 重起時 `adopt` 接回的子項 ＋ 依序套用每封信的增減。接回的子項留在名單上，直到有信把它 `loops_removed`（方向題 1）。
- 每圈：全部認領 → 照名字順序套用 → 對一次表 → 信刪掉（預設）或進 `done/`。壞信照 § 二 4。
- 誰能寄：純靠 Linux 檔案權限（C-64、N-54 末；sandbox S17）——信箱 `new/`、`tmp/` 開給誰寫，誰就能寄。aos 不另做名單。
- 回信：寄信人要知道「加進去了沒」，標準做法是**讀 `loops_state.json`**（窗）；寫了 `reply_to` 的，daemon 套用完回一封 `body: {"applied": true}`（或 `{"applied": false, "reason": …}`）。失敗不另外通知（決定 27）。

## 五、鎖：本設計怎麼用（決定 5、10、18；N-15 仍是草稿）

本設計**只有一個地方需要鎖**：有順序的投遞的 `order.lock/`。投遞本身（rename 認領）、窗（N-05 暫存改名）、兩個手把（N-54：多人寫靠 Linux 權限）都不用鎖。鎖的形狀照 medium「留待實作」的頂層四點，只改一處：

1. 只做一種獨佔鎖、不分讀寫；讀的人靠 N-05 暫存改名拿到完整檔。（採）
2. 資料夾的鎖是 `<資料夾>/.lock/`、檔的鎖是 `<檔>.lock/`，`mkdir` 成功＝拿到；不檢查上下層。（採；`order.lock/` 就是「`order.json` 這個檔的鎖」）
3. 名牌 `holder.json`：**多一欄 `holder`＝持有者的身分路徑（決定 22；程式＝`$AOS_WS`、人＝`~/`）**，其餘照四點——`pid`、`started_at_ticks`、`boot_id`（N-17 判死活用）、`acquired_at`、選填 `lease_ms` 與 `note`。放鎖＝先把鎖資料夾改名成獨一無二的名字（`.lock.releasing.<信號>`）再刪，別人不會 mkdir 到一個正在被刪的資料夾。（採，加 `holder`）
4. flock 只拿來同機加速，不當正確性依據。（採）

收屍（N-15）：想拿鎖的人 mkdir 失敗時讀 `holder.json`，持有者 pid＋`started_at_ticks`＋`boot_id` 對不上（死了）或 `lease_ms` 過期，就照 3 的放鎖步驟替它收，再重新 mkdir；兩人同時收也沒事（改名只有一個會成功）。「約定、不必擋得住」（決定 10）：從 Linux 繞過去 aos 不管。

## 六、父子交代（決定 28）：現有的夠不夠

現有的標準：進＝args、stdin、aos-exec 保證的六個環境變數（N-57）＋hub 型變數（N-63，繼承），參數怎麼進由被叫的程式自己說（N-27、P-26）；出＝結束碼（N-43）、stdout、stack 裡的檔（N-13）。巢狀怎麼給 stack 與工作區（P-32、P-39）。

結論：**夠，缺的只有「集中說一次」**——這三樣散在五條裡，沒有一條說「這就是父子交代」。補一條 N-64（草稿）把它們點名，加兩句：① 下一代要自報身分就報 `$AOS_WS`（決定 22、23），上一代給的工作區就是它的名字；② 上一代要讓下一代找到自己的信箱或窗，用 hub 型變數（N-63）或 args 明給，不另加新的環境變數（C-69 aos 只訂那幾個）。用不用都可以（使用者原話）。

daemon 起子 loop 就是父子交代的一個實例：寫小格 `loop.json`、`AOS_STACK=小格`、起 `aos-exec 小格/loop.json#/_entry`——完全在現有標準內。
