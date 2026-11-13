# 叫醒自己的計時器（線鐘 11-13 晚）：clock_register 加三種排法——after（再過 N 個 cycle 一次）、at（牆鐘某時刻一次）、cron（牆鐘五欄重複）；一次性的寄完自己消失

使用者 11-13 晚：「loop fsm有叫醒自己的工具嗎，類似crontime這種，這也可以再派設計，做好了就直接上，小工具而已。」

同晚補充（逐字）：「啊對了，說到時間，以後會很長出現這種"我xx點xx分去xx"這種指令，現在都是用cron time，aos這邊沒有工具。所以可能還要規劃看現在真實世界時間的工具，還有基於clock hook的，在指定真實世界時刻觸發的工具...或是不基於clock hook？我覺得都可以，基於clock hook的會比較不準，但比較方便，基於特定proc的會比較準，但比較麻煩，都可以做。」

調度者據此分三件：(1) 看真實世界時間——先查 `peek_now_time` 夠不夠；(2) A 基於時鐘的牆鐘觸發（方便、誤差＝檢查間隔）先做完；(3) B 專門的 proc（準、麻煩）時間夠再做，不夠就寫設計標未施工。下面二～五是 A；六是 (1)；七是 B。

> A 用的「clock hook」就是時鐘登記表本身——它正是 11-10 使用者要的「clock那邊看看能不能加上一個hook，有需要的人可以去註冊」，後來改成寄信。檢查點是根時鐘每走一格（預設 1 秒），所以 A 的誤差是一格，不是 agent 自己 `on_clock` hook 的「每一步開頭才看」。

## 一、現況盤點（讀程式核過）

| 有什麼 | 在哪 | 做什麼 | 牆鐘？ | 一次性？ |
|---|---|---|---|---|
| `clock_register`（工具） | `lib/agent/clock_register/_entry` → `cmd/aos-clock-register` → 登記表 `<根 stack>/clock_register.json`；`aos-clock` 每走一格讀表、用 `py/aos_clock_register.py` 的 `fire` 寄信 | 每 `every` 個 cycle（對齊整數倍）往一個箱子寄固定一句；不給 box＝寄自己的 queue，當一則 user 訊息叫醒自己 | 否（cycle） | 否（重複，要自己 rm） |
| `on_clock` hook（`self_hook` 加） | `lib/agent/hooks.py`、範本 `hooks.json` | 每 N cycle／ms 跑一支程式，不進對話；程式要叫醒自己就寄信到自己 queue | 否（ms 換成 cycle） | 否 |
| `self_hook.json#/daily` 範例 | 知識庫 | on_clock 每分鐘跑、程式自己看牆鐘、到點才寄信；錯過的醒來補一次 | 是（程式自己寫） | 否 |

- **fsm agent 預設拿得到**：`templates/agent-fsm/tools.json` 疊 15 包，含 `events` 包（`lib/packs/events.json`＝`clock_register`＋`self_hook`）。所以預設的 agent-fsm **能叫醒自己**：`clock_register` 不給 box。
- **拿掉 events 包就沒有**：線隊的 gpt 隊（[gpt-fsm-team](gpt-fsm-team.md) 表「self、def、events 包｜沒有」）兩份定義都拿掉 events 包，astra、sol **沒有任何叫醒自己的工具**（`clock_register`、`self_hook` 都在 events 包；別包沒有）。還能用的旁路：有 shell 包就能在 shell 裡打 `aos-clock-register add …`（要自己給 `--box` 自己的 queue），但 gpt 隊的 shell 在沙箱裡，寫不寫得到根 stack 的登記表另看沙箱設定。這件事不在本線改，攤給線隊（代定 6）。
- 缺的：**一次性**（「10 個 cycle 後叫我一次」「22:30 叫我」，用完自己消失）、**牆鐘重複**（「每週一 9 點」「每 15 分鐘」不用自己寫 hook 程式）。

## 二、做法（最小改動）：延伸既有登記表，不開新工具、不開新包

`clock_register` add 原本必給 `every`，改成 **`every`／`after`／`at`／`cron` 四選一**：

| 參數 | 意思 | 存進登記表的格 | 何時寄 | 寄完 |
|---|---|---|---|---|
| `every: N`（原有） | 每 N cycle | `{"every": N}` | 新 cycle % N == 0 | 留著 |
| `after: N` | 再過 N 個 cycle 一次 | `{"at_cycle": 現在＋N}` | 新 cycle ≥ at_cycle | 自己拿掉 |
| `at: "22:30"`、`"2026-11-14 09:00"`、`"+10m"` | 牆鐘某時刻一次 | `{"at_time": "2026-11-13T22:30:00+08:00"}` | 時鐘走一格時牆鐘 ≥ at_time | 自己拿掉 |
| `cron: "0 9 * * 1"` | 牆鐘重複（五欄：分 時 日 月 週） | `{"cron": "0 9 * * 1", "next": "…"}` | 時鐘走一格時牆鐘 ≥ next | 留著，next 往後推 |

例（腦）：

```json
{"op": "add", "name": "recheck", "after": 30, "text": "Re-run the tests."}
{"op": "add", "name": "standup", "at": "+15m", "text": "Post the status letter."}
{"op": "add", "name": "monday", "cron": "0 9 * * 1", "text": "Weekly review is due."}
```

殼：`aos-clock-register add --after 30 --box STACK/queue recheck "Re-run the tests."`（`--at WHEN`、`--cron "M H D M W"` 同理）。

- **放哪**：牆鐘解析與 cron 放新檔 `py/aos_clock_when.py`；`py/aos_clock_register.py` 的格檢查與 `fire` 認四種格；`cmd/aos-clock-register` 收新旗標、`ls` 第二欄改成「排法」（every 的格照舊印數字）；工具 `_entry`／`_tooldef.json` 收新參數。誰寄信、寄到哪、信的形狀都沒變。
- **at 寫法**：`HH:MM`（今天，已過＝明天）、`YYYY-MM-DD HH:MM[:SS]`（本機時區；也收 ISO 帶時區）、`+N` 加 `s`／`m`／`h`／`d`（從現在算）。已經過去的絕對時刻＝`ArgumentsBad`。
- **cron 寫法**：標準五欄，`*`、`N`、`A-B`、`*/S`、`A-B/S`、逗號清單；週 0～7（0、7＝週日）；日與週都有限制時任一符合即可（同 Vixie cron）。不收月份／星期英文名、不收 `@daily` 這類（代定 3）。五年內排不到（如 2 月 30 日）＝`ArgumentsBad`。
- **錯誤代號**：沿用既有（`ArgumentsBad`：四選一沒給或給兩個、`after` 不是正整數、`at`／`cron` 寫不懂或已過；`EntryExists`、`EntryMissing`、`ClockMissing`、`RegisterBad`、`WriteFailed`、`DaemonMissing`、`InstanceMissing`…）；`aos-clock-register` 多一個 `ClockBad`（`--after` 讀不懂時鐘檔，同 aos-clock 的同名代號）。
- **信**：形狀不變（`role`、`content`、`from: clock`…）。牆鐘兩種的 content 多帶到期時刻：`[aos] clock: cycle 812, due 2026-11-13 22:30. TEXT`，晚超過一分鐘再加 `(late by 2h 5m)`；body 多一鍵 `due`。

## 三、時間語意

- **檢查點只有一個：根時鐘每走一格**（`aos-clock`，預設每秒）。所以牆鐘計時器最多晚一格；時鐘停（樹睡、ctl paused）就沒有人檢查。
- **after（cycle）**：樹睡著 cycle 不走，等待也不走——「再過 30 cycle」＝樹醒著的 30 格。跟樹內其他等待一致。
- **at／cron（牆鐘）**：樹睡著時錯過的，**醒來第一格補寄一次**；cron 錯過多次也**只寄一次**（不按次數補），next 從「現在」往後算。信上的 `due` 與 `late by` 讓腦知道遲了多久。這跟 `self_hook.json#/daily` 的語意一致。
- **agent 自己睡著（樹醒著）**：信照寄、在 queue 等它醒（既有規則）。
- **時區**：本機時區。at_time、next 存成帶時區的 ISO，換機器也是同一個絕對時刻；cron 每次用跑 `aos-clock` 那台的本機時區重算。

## 四、邊緣狀況

1. **寄不到**（箱子不是信箱、aos-post 失敗）：跟 `every` 一樣只 warning 一次、不重試——一次性的格照樣拿掉、cron 照樣往後推（代定 1；否則每秒一行 warning）。箱子資料夾已不在：既有自我檢查每 100 格清掉。
2. **寫回失敗**（一次性拿不掉、next 推不動）：warning；下一格會再寄一次（同 self_check 的寫不回）。
3. **同時改表**：`fire` 寫回前重讀，只動自己剛寄的那幾格，而且只在那格沒被別人換掉（內容跟寄時一樣）時才動；跟 `aos-clock-register add` 同一瞬間寫仍是「後寫的蓋過先寫的」（既有已知）。
4. **時鐘往回撥**（牆鐘）：at 還沒到就不寄；cron 的 next 不會往回算，等到 next 才寄。**時鐘檔被手改**（cycle）：after 用 ≥，往前跳一定寄，往回跳就等。
5. **登記時沒有時鐘檔**（才起樹）：`after` 從 0 算，跟 `aos-clock-register` 原本「沒有時鐘檔」的 warning 一起印。
6. **手改登記表**：一格裡 `every`／`at_cycle`／`at_time`／`cron` 只能有一個；cron 的格缺 `next` 或寫壞＝那格跳過、warning（同既有壞格）。
7. **舊的活樹工具配新指令**：活樹 `lib` 是複本，舊 `_entry` 只會送 `--every`，新 `aos-clock-register` 照收；新 `fire` 對只有 `every` 的格行為一字不變（既有測試照綠）。

## 五、代定清單（照最保守的做）

1. 寄不到不重試（一次性照拿掉、cron 照推）——跟 every 一致。
2. 不另開工具名（不叫 `wake_me`／`schedule`），延伸 `clock_register`；不開新包。
3. cron 只收數字五欄，不收英文名、`@daily`、秒欄、`L`／`W`／`#`。
4. at 的已過時刻報錯，不當「馬上寄」。
5. 錯過的牆鐘計時器醒來只補一次，不按次數補。
6. gpt 隊拿掉 events 包後沒有叫醒工具：本線不動定義，攤給線隊決定（可只把 `clock_register` 加回、`self_hook` 不給；clock_register 不能關 hook，不碰守門）。
7. `ls` 第二欄由「EVERY」改成「WHEN」：every 的格照印數字（舊輸出不變），其他印 `cycle N`／`at ISO`／`cron EXPR next ISO`。
8. 看本機時間不開新工具，`peek_now_time` 加可省的 `local`（不給＝照舊 UTC）。
9. B（專門 proc）不施工，見七：A 已到一格的準度，B 只在要秒以下或 paused 照響時才值得，等使用者定。
10. 時鐘檔讀不懂時 `--after` 報新代號 `ClockBad`（沿用 aos-clock 同名代號），不當 0。

## 六、看真實世界時間：`peek_now_time` 夠不夠

- 原本只印 UTC（`2026-11-13T12:57:45Z`）。腦要接「我 21:30 去做 X」得自己知道本機時區，不夠。
- 最小補法（已做）：`peek_now_time` 收一個可省的 `{"local": true}`，改印本機時間帶時區與星期：`2026-11-13T20:57:45+08:00 Friday`。不給參數輸出一字不變（範本測試、llm_fake 照舊）。這是 `clock_register` 的 `at`／`cron` 用的同一個時間。
- 知識庫：`clock.json#/wake_at` 寫「現在本機幾點：peek_now_time {"local": true}」；`packs.json` 的 gadgets 一句跟著改。

## 七、B：專門的 proc（設計，未施工）

使用者說「基於clock hook的會比較不準，但比較方便，基於特定proc的會比較準，但比較麻煩，都可以做」。查完之後的事實要先攤：**A 已經不是「不準」的那種**。

| | A（已做）：根時鐘每走一格看登記表 | agent 自己的 `on_clock` hook（`self_hook.json#/daily` 那種） | B：專門的 proc |
|---|---|---|---|
| 誤差 | 一格（根 daemon 範本 `interval_ms` 1000＝最多晚 1 秒） | 該 agent 每一步開頭才看＋every_ms 進位成整格（daily 範例一分鐘看一次＝最多晚 1 分鐘多；agent 在等腦回話時不看） | 可到毫秒級（睡到到期時刻） |
| 時鐘 paused 時 | 不寄（沒人看） | 不跑 | 照寄（看牆鐘不看 cycle） |
| 樹睡著 | 醒來補一次 | 醒來補一次 | 醒來補一次（proc 也在睡） |
| 麻煩 | 沿用登記表、工具、包 | 要自己寫程式 | 新 proc、新指令、daemon 範本多一列、活樹要重抄範本＋停樹加列 |

使用者說的「比較不準」對應的是中間那欄（agent 自己的 hook）；A 走的是根時鐘，誤差只剩一格。所以 **B 只在兩種情況值得做**：要秒以下的準度、或要「時鐘 paused 也照響」。這兩件使用者都還沒說要，照最保守先不施工，等使用者看完這張表再定。

若要做，形狀這樣（給下一條線）：

1. 指令 `aos-clock-alarm [-d D] CLOCK`（`cmd/aos-clock-alarm/`），常駐：讀同一張登記表，只管牆鐘兩種（`at_time`、`cron`）且格上標 `"precise": true` 的；算最早的到期時刻，`sleep` 到那時（最長睡 1 秒就重讀表，接住新加的格），到了用同一個 `aos_clock_register.send`／`body` 寄、同一個 `write_back` 拿掉或推 next。
2. `aos_clock_register.fire` 跳過 `precise` 的格（不重寄）；`clock_register` 多一個 `precise: true` 參數，`aos-clock-register add --precise`。
3. 根 daemon 範本 `templates/daemon-root/daemon.json` 加一列 `_alarm`：`{"exec": {"argv": ["aos-clock-alarm", {"$env": "AOS_DAEMON", "$path": "clock"}]}, "auto_restart": true}`（不給 interval_ms＝一次起來常駐；要先核 daemon 對常駐列的寫法）。
4. 待裁：paused 時要不要照響（B 的好處之一，但跟「樹內時間停就停」的時間觀不同）；沒有 `_alarm` 列的舊樹，`precise` 的格誰寄（建議：fire 看不到 `_alarm` 心跳就自己寄，退回 A）。
5. 活樹要有：重抄 templates 不夠（daemon.json 是起樹時抄的），要在活樹的根 daemon.json 加列、重起根 daemon——由使用者下指令。

## 八、施工紀錄

- 改／增的檔：`py/aos_clock_when.py`（新）、`py/aos_clock_register.py`（四種格、fire、write_back、when）、`cmd/aos-clock-register/bin/aos-clock-register`（新旗標、ls 第二欄）與 README、`lib/agent/clock_register/_entry`／`_tooldef.json`、`lib/base/peek_now_time/_entry`／`_tooldef.json`／`_metainfo.json`、測試四份（`py/tests/test_clock_when.py`、`cmd/aos-clock-register/tests/test_clock_once_cron.py`、`lib/agent/clock_register/tests/` 加一則、`lib/base/peek_now_time/tests/test_peek_now_time.py`）、知識庫 `knowledge/aos/clock.json`（新節點 `wake_at`、`choose` 改兩句）與 `packs.json`（兩句）。
- 什麼時候生效：`py/`、`cmd/` 存檔即生效（活樹的根時鐘每格 import `py/aos_clock_register.py`；只有 every 的格行為一字不變，既有 7 則測試照綠）。`lib/agent/clock_register`、`lib/base/peek_now_time`、`knowledge` 在活樹是複本，**活樹要重抄才有** `after`／`at`／`cron` 參數與 `local`；重抄前，活樹的 agent 只能從殼 `aos-clock-register add --at …` 用。
