# adapt 任務包（最新值轉接）第一版

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)｜細部規則：[spec.md](spec.md)｜依據：[loop6 藍圖](../../notes/blueprint-loop6.md) §3、[r3 綜合](../../../proto7/notes/thinking/2026-10-04-r3-synthesis.md)（轉接包草案）、[r5 骨架](../../../proto7/notes/thinking/2026-10-04-r5-synthesis.md) §4、[r6 綜合](../../../proto7/notes/thinking/2026-10-04-r6-synthesis.md)、[r2 綜合](../../../proto7/notes/thinking/2026-10-04-r2-synthesis.md)（出處、依據版本）

**一個普通 `keep` 任務，每收到自己的 tock 就把鄰居 node 發布的最新值經一條確定性鏈重算一次，寫成自己 node 的三態暫存器 `in/<sense>.json`，附依據版本與出處。** 通用任務包（原則 5、8）：把 LLM 換成 cron 仍成立；不帶 LLM、事件、資源。daemon／tick 核心零新增：搆得到＝核心 §4.5 掛載、自己的鐘＝`tock.json`、來源的鐘＝來源 `.aos/round.json`、三態＝`aos7_fs.fact`。

| 項目 | 內容 |
|---|---|
| 分類 | 通用任務包（`layer: kernel`），單 node 視角（消費端的 node 跑它） |
| 接法 | A 普通 keep 任務：`{"name": "adapt-<sense>", "mode": "keep", "argv": ["python3", "<proto7-2>/packs/adapt/bin/aos7-adapt", "run", "adapt/<sense>.json"], "mounts": {"src": "<來源 node>/out", "srcclock": "<來源 node>/.aos"}}` |
| 預設 | 不裝就不存在；`max_age: null`（只報年齡）、`patience: 0`、`stall: null`（只報不翻）——見 spec §2 |
| 依賴 | 工具包（`aos7_taskside.task_env`／`wait_tock`／`resolver`）、核心 `aos7_fs`（`fact`、`write_json`、`read_round`） |
| 程式 | `aos7_adapt.py`（宣告、檢查器、鏈、時鐘、暫存器、人手 `status`）、`bin/aos7-adapt` |
| 範例 | `examples/temp/`：發布者 `sensor.py`、宣告 `temp.json`、消費者 `fan.py` |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py packs/adapt/tests`；全套預設就收） |

## 契約卡

- **職責**：把來源的一份事實檔（位準型：最新值）投影成消費端吃得下的窄格式；每次都從**固定版本的依據**重算（不吃上一跳）；標出依據版本 `basis`、出處 `src`、鏈版本 `chain.sha`、來源鐘的年齡、來源狀態；交付三態 `ok／unknown／absent`。
- **前置條件**：自己是 `max_live: 1` 的 keep；來源檔經 mounts 掛進來（空間路徑，`mount_allow` 放行）、由來源用原子 rename 寫（核心 `write_json`）、內容是 JSON 物件且帶整數 `round`（建議帶 `seq`）；來源 node 的 `.aos/round.json` 也掛得到；鏈宣告 `<node>/adapt/<sense>.json` 過了檢查器、工作中不改；`in/<sense>.json` 只有本包寫；槽內 `state.json` 只有本包寫。
- **保證**：
  - 暫存器要嘛完整要嘛舊版（rename）；每個自己的 tock 寫一次（`my_round` 前進），pause 時不動。
  - `state: ok` 時 `value` 一定是從 `basis.sha` 那一版算出來的；鏈每步可重算（`trace`）、列出 `omitted` 與誤差界 `err`。
  - 來源讀不到、半寫、缺欄、路徑指不到、選不到、型別不對＝同一條 unknown 分支：**先靠耐性撐住舊值、到期才翻 unknown**（不假造值、不丟 `last`）；來源檔確定不存在＝`absent`。
  - 效期 `max_age` 用來源回合數算、耐性 `patience` 用自己回合數算（pause 時都不走）；來源回合倒退＝`reset`、舊依據作廢；來源慢**不是**錯（只是年齡）、來源快只是漏取樣（記 `skipped`，不補）。
  - 門檻判斷時誤差區間跨過門檻＝那一欄 `null`、`state: unknown`、`why: within_error_band`，不硬判。
  - 鏈用精確十進位算；發布的數字不失真（整數原樣、float 的表示誤差算進 `err`），超出 float 範圍＝`out_of_range` unknown，不發布 `Infinity`（spec §2「數值」）。
  - 被殺重起：從槽內 `state.json` 接回 `since`、`last_seq`、`skipped`，不重算、不把同一版當新版。框架先寫、暫存器後寫。
- **明確不管**：來源說的是不是真話；消費者拿到 unknown 之後怎麼辦；事件／窗口（只有最新值）；不可重算的（LLM）步驟；跨子 daemon 交付；來源沒帶 `seq` 時漏了幾版；掛載權限；人手改 `in/`、`state.json`、鏈宣告。

## 界線

- **不分辨來源是 paused、慢、還是死了**：v1 只看來源鐘有沒有前進（`advancing`／`stalled`），不讀 daemon status；`stall` 設整數才在停太久時翻 unknown（v2 選項：掛 `.aosd/status.json` 再分）。
- **不做事件**：只轉最新值；「期間曾經異常、現在已恢復」對本包是同一個輸入，要分辨得另做事件／窗口包。
- **不接 LLM**：鏈只有確定性的三種步（`select`／`scale`／`threshold`），不開運算式；摘要、翻譯之類的模糊步驟屬之後的 `adapt-llm` 子包。
- 回合內誰先醒沒保證（同一個 tock，adapt 與消費者都在等）：消費者改等暫存器的 `my_round` 前進（`examples/temp/fan.py`），不等 tock。
- 不接 step、budget 也能用：step 的 `wait` 條件 `{"num": "in/<sense>.json", "key": "value.c", …}` 直接吃暫存器；`state` 不是 `ok` 時 `value` 是 `null`，條件自然不成立。

## 人手指令

- `aos7-adapt check <宣告>`：欄位型別、步種類、`need` 在產出裡、`max_age`／`patience`／`stall` 是非負整數或 null；不執行；有錯退出碼 1。
- `aos7-adapt status <宣告>`（cwd＝node）：印暫存器摘要（`state`、`value`、`why`、`age_src_rounds`、`src_state`、`my_round`）。
