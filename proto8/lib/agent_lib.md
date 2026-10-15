# agent 的現成格庫（`aos_agent_lib.py`）

← [agent.md](agent.md)｜[proto8/lib](README.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)

> 10-15 晚從 [agent.md](agent.md) 拆出來（整檔超過 8 KB）；內容沒改。**實作慣例，還不是規範。**

## 用法

```
aos agent think|tool|route [--done 名]|intake|done|fsm [NAME]      （＝python3 aos_agent_lib.py …）
```

- 不是 agent 本體（agent＝fsm＋表，不變）；是表裡可以直接拿來用的幾格。檔名：使用者 10-15 說「aos-agent-lib.py」，proto8/lib 的模組一律底線（連字號 import 不了），所以叫 `aos_agent_lib.py`。
- **設定從哪來**（10-15 收工後改：fsm 不再餵格 stdin，N-37）：stdin＝那張格 inst 自己 `stdin` 指的檔（沒寫＝空）；那份的 key 優先，沒寫的照 frame（＝cwd）找——`lookup()`：先找 cwd，找不到照 cwd 裡 `frame.json` 的 `parent` 往上找（C-46，繞圈或超過 16 層就停）。`brain`＝`brain.json`、`tools`＝`tools/*.json`（`lookup_dir()`：各層逐項合併、近的蓋過遠的；名字＝檔名去掉 `.json`）、`system`＝`system.md`（有才帶）、`history`＝cwd 的 `history.json`、`work`＝cwd 的 `work/`。stdin 不是物件＝`ConfigMissing`、退出 1。相對路徑從格的 cwd 算。定義資料夾的格都不寫 stdin，全靠 frame 找。

- **think**：讀 history、組請求（`tools` 從各工具 inst 的 `_tool` 來；沒工具就不帶）、蓋 stdin 跑腦（`aos_methods.run_cell`）、把 assistant 訊息（拿掉頂層 `usage`）接進 history，stdout `{"data": {"content", "tool_calls": [工具名]}}`。不吐 `next`：下一格寫在表上。history 最後已經是 assistant（上一拍接好才被殺）＝不再叫腦。腦結束碼非 0＝`BrainFailed`（白話只有「腦 X 結束碼 N」；腦的 stderr think 不讀，C-52 切乾淨，要看原因就在 brain.json 寫 `stderr` 檔）、回的不是 assistant 訊息＝`ReplyBad`，這格退出 1，fsm 那行的 `error` 是 `CellFailed: 格 ask 結束碼 1`（fsm 也不讀格的 stderr）。**連錯停住是格自己的事**（N-38）：次數記在 `work/think.json`（`{"val": 次數, "error"}`，think 自己的私檔，成功一次就刪），到 `halt_after`（預設 3）次＝不報錯，**think 自己**把要交出去的錯寫成 cwd 的 `ret.json`（`{"error": {"code", "msg"}}`），再吐 `{"next": halt_state（預設 "halted"）, "data": {"error"}}`——halt_state 寫在表的 `end`、**不寫進 `states`**（N-40：next 不在表裡、在 end 裡＝fsm 結束，不經 done 格）；表上沒寫＝fsm 報 `NextUnknown`、每拍再叫一次腦（10-15 使用者「都同意。」，[盤點第 8 條](../thinking/2026-10-15-principles.md)；原本 halted 接 done 格，done 讀 think 的私檔寫錯誤）。
- **tool**：找最後一則 assistant 還沒回的 `tool_calls`，一拍內照順序全部跑、每跑完一個就接一則 tool 訊息，stdout `{"data": {"tool", "result", "tools", "results"}}`（`tool`／`result`＝第一個，`tools`／`results`＝全部）。每個工具跑前寫 `work/.tool-running.json`（記 tool_call id）、跑完刪：下一拍看到它還在、是還沒回的第一個 id＝上一拍被殺一半。工具只是一張 inst：在 `work/<n>/` 跑、`args.json` 進、`stdout.json` 出；裡面是什麼（另一個 agent？）這格不知道、不傳東西下去（C-52）。
- **route**：看最後一則 assistant，有 `tool_calls`＝`{"next": "tool"}`，否則 `{"next": "idle", "data": {"reply"}}`（`--done 名` 把 idle 換掉，定義資料夾寫 `--done done`）。單層表用（demo 的 `clerk/`）。
- **intake**：把 cwd 的 `args.json`（實引數）接進 history，接完把 `args.json` 改名成 `args.taken.json`、刪掉上一輪的 `ret.json`（同一份不會接兩次；呼叫方下次再寫一份新的 `args.json` 就是新問題）。`{"question"}`：frame 還沒有 `history.json`＝生一份 `[user 訊息]`；已經有＝接在後面當一則新的 user 訊息（同一個 frame 續聊，10-15 使用者「按照建議」）；history 最後一則已經是同一句 user 訊息（上一拍接好了、改名前被殺）＝不再接。`{"history"}`＝整段換掉。沒有 `args.json`：已經有 history＝照舊往下（呼叫方綁了 history，或接著上次的）；也沒有＝`HistoryMissing`。
- **done**：寫 cwd 的 `ret.json`＝`{"reply": 最後一句}`，只看自己的輸入（history），不讀別格的私檔（10-15 使用者「都同意。」，[盤點第 8 條](../thinking/2026-10-15-principles.md)）。不碰 ctl：done 在表的 `end` 裡，fsm 結束那拍那行帶 `"end": true`，拍它的 loop 寫了 `stop_on_end` 就停（N-44）。
- **fsm**（不是格，給 loop.json 用）：照 `lookup()` 找 `NAME`（預設 `fsm.json`），跑一拍 aos_fsm（格的名字從找到的那份所在的資料夾算、窗從 frame 算）。這樣定義資料夾的 `loop.json` 不必寫自己在哪：`{"inst": {"argv": ["aos", "agent", "fsm"]}, …}`；內層 fsm 的格也一樣寫 `aos agent fsm think/fsm.json`。找不到＝`FsmMissing`、退出 1。
- stdin 給的 `brain`、`tools` 值除了 TARGET，也可以是內嵌一張 inst。

## 邊緣狀況（使用者 10-15 定）

| 情況 | 基礎實作 |
|---|---|
| 工具名不認得 | 回模型一則 tool 訊息 `{"error": {"code": "ToolUnknown", "msg": "不認得這個工具：名"}}`，不算 fsm 的錯 |
| 一次回好幾個 `tool_calls` | 一拍內照順序全部跑，每個都回對應 `tool_call_id` 的 tool 訊息（OpenAI 要每個 id 都有回才能再問）；跑完一個就接進 history。（10-15 使用者「都按照推薦」，[litellm 實跑 #3](../thinking/2026-10-15-litellm-live.md#拍板10-15)；原本只跑第一個、其餘回 `Skipped`） |
| 引數不合 schema | 不驗；工具自己報錯（code≠0），照樣回模型 |
| tool 格被殺一半（`work/.tool-running.json` 還在、同一個 id，N-38） | 跑到一半的那個不重跑、回 `{"error": {"code": "Interrupted", …}}`；它前面跑完的已經接進 history，後面的照跑 |

動工時自己定的（等使用者看）：`arguments` 不是 JSON＝回 `{"error": {"code": "ArgumentsBad", …}}` 不跑；工具的 inst 起不來（aos_inst 出錯）＝回 aos_inst 的錯（同形狀、原代號）；工具 inst 沒寫 `_tool`＝空說明、不收引數。
