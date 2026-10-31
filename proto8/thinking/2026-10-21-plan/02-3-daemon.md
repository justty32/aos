← [入口](../2026-10-21-plan.md)｜涵蓋：3. daemon、4. fsm、5. agent、6. 實作順序與切段、7. impls（使用者自己的 C++ 版）｜上一份 [01-1-使用者回來要看的](01-1-使用者回來要看的.md)

## 3. daemon

### 3.2 已定

使用者先前「daemon先等等，loop好了之後再說」，10-21 說可以做。

### 3.3 基礎／標準拆法

- 基礎＝照表起每個子項（經 aos-exec：`aos-exec -- 小格/loop.json#/_exec`）、結束前收掉。
- 標準＝再加 ctl `children` 增減、`adopt` 接回、state 的 `children` 表與心跳、自己的 `run`、訊號。

### 3.4 簡化

- daemon **不驗**子項內容、原樣寫進小格，寫錯了子 loop 自己退 1、錯在小格的 `stderr`（N-28）。
- daemon 的命令列與 loop 共用（`--max`、`--interval-ms`、`--ctl`、`--state`＋唯一的設定檔）；`children`、`adopt` 只在 daemon.json（dict 寫不成旗標；N-11「盡量不收」）。

### 3.5 代定

- **D1 命令列**＝`aos-daemon [旗標] 設定檔`，語意同 loop；daemon 的預設 `max` 不限、`interval_ms` 200（[ideas § 9](../2026-10-21-ideas/05-7-審後的五個細縫與修正.md#9-設定檔是唯一的位置參數path-改字串拼接10-21-傍晚)）。
- **D2 `children`**：字串＝aos-exec 目標、包成 `{"run": 它}`；陣列也可以；物件＝loop 設定、原樣交出去（補 `ctl: ctl.json`、`state: state.json`，沒寫才補）；子 loop 經 aos-exec 起（小格 loop.json 蓋上 `_exec`）（[ideas § 9](../2026-10-21-ideas/05-7-審後的五個細縫與修正.md#9-設定檔是唯一的位置參數path-改字串拼接10-21-傍晚)）。
- **D3 相對路徑**：子 loop 經 aos-exec 起、cwd 是小格；daemon 寫小格時把 `run` 的目標轉成絕對路徑，所以子項設定裡 `run` 的相對路徑從 daemon 的 cwd 算（慣例下＝daemon.json 所在的資料夾）（[ideas § 9](../2026-10-21-ideas/05-7-審後的五個細縫與修正.md#9-設定檔是唯一的位置參數path-改字串拼接10-21-傍晚)）。
- **D5** loop 與 daemon 只差 `interval_ms` 預設（loop 0、daemon 200）；`max` 都預設不限（N-28）。
- **D6 adopt、ctl `children`、收工順序、訊號**照 N-28、N-54。
- **D7 收工時剛死的子項**：`finish()` 收完後把表上「不是 running 又還沒標 exited」的一併標 `exited`、記 `code`（不然最後一圈之後才死的子項在最後那份 state 留 `phase: running`）。

## 4. fsm

### 4.2 已定

使用者只說「aos-fsm……也可以開始做了」；下面全是照今天的調子推的代定。

### 4.3 基礎／標準拆法

- 基礎＝讀 state、查表、`aos-exec -- val`、0 才換狀態、以格的碼退。
- 標準＝再加 `trace.jsonl`、訊號轉給那格。

### 4.4 簡化

- trace 沒有 `timed_out`（fsm 不知道、也不該知道格裡有逾時，C-52；逾時的格被整群收掉、以 128＋15 回來，trace 的 `code`／`signal` 看得出）。

### 4.5 代定

- **F1 命令列**＝`aos-fsm [旗標] 設定檔`（目前沒有旗標），設定檔是唯一的位置參數（[ideas § 9](../2026-10-21-ideas/05-7-審後的五個細縫與修正.md#9-設定檔是唯一的位置參數path-改字串拼接10-21-傍晚)）；不加 `--start`（盡量不收旗標；要換起點改 state 檔或表）。
- **F2 `val`**：見 § 1.1。
- **F4 trace 欄位**＝`{"at","state","code","signal","ms"}`（N-39、P-07、P-38）。
- **F5 其餘**：state 檔位置與格式、0 才換狀態、出錯 state 不動、自己的錯退 1 一行、訊號 128＋N。
- **F6 fsm.json 可當 aos-exec 入口**：範本 bob／cathy 的 fsm.json 帶 `"_exec": ["aos-fsm", {"$env": "AOS_CF"}]`，loop.json 寫 `{"run": "fsm.json", "max": 20}`——每拍就是 `aos-exec -- fsm.json`。fsm 讀表時 `_exec` 照 C-48 忽略（[ideas § 9](../2026-10-21-ideas/05-7-審後的五個細縫與修正.md#9-設定檔是唯一的位置參數path-改字串拼接10-21-傍晚)）。

## 5. agent

### 5.1 proto8 現在的「agent」是什麼

**是慣例＋demo，沒有程式。** CONVENTION P-05～P-40 定了形狀（一個資料夾、`_exec`＝`exec aos-loop …`、loop.json、fsm.json 三態、stack、題目一題一檔、工具在 `tools/`）；demo 的 agent-bob／agent-ann／cathy 是範本；N-53 說 aos 的 agent 是被外面 loop 一拍一拍驅動的狀態機。沒有 `aos-agent` 這支，也不該有（C-62、C-50）。

### 5.2 兩種 kernel、tasks、tick、`tool_calls`

- tick：做了（第 4 段；10-12 你已把規格定死：`aos-tick FILE`：讀 n 寫 n＋1、先暫存再改名、沒檔＝0、內容壞退 1，說「做吧」）。
- `tool_calls`：10-23 做了（§ 1.2 第 2 題）。
- tasks：**未決**（§ 1.2 第 1 題）。
- LLM kernel：10-24 做了（§ 1.2 第 3 題）。
- 通用 kernel：**未決**（在 LLM kernel 之後；判官形狀沒定）。

## 6. 實作順序與切段

第 1～4 段（loop＋daemon 最小跟上、daemon 收尾、fsm、tick）都已做；各段採用的代定與自定點見 session log 10-21（[第 1 段](../../../wf/session_logs/2026-10/2026-10-21.md#使用者不在時代定aos-loop-收旗標計畫第-1-段10-21-下午)、[第 2 段](../../../wf/session_logs/2026-10/2026-10-21.md#使用者不在時代定daemon-收尾計畫第-2-段10-21-下午)、[第 3 段](../../../wf/session_logs/2026-10/2026-10-21.md#使用者不在時代定fsm計畫第-3-段10-21-下午)、[第 4 段](../../../wf/session_logs/2026-10/2026-10-21.md#使用者不在時代定aos-tick計畫第-4-段10-21-晚)）。

## 7. impls（使用者自己的 C++ 版）

impls 是唯一實作（`proto8/bin` 只剩 Python 的 `aos-tick`），現行行為見 [impls README](../../impls/README.md)。
