# proto8 規範（一）：總則、時空、inst、loop 與 daemon——大家都要守的，一條一兩句

← [proto8](../README.md)｜[（二）窗](NORMS/00-規範-2-窗.md)｜[（三）指示詞、組合子、kernel、命名](NORMS/00-規範-3-指示詞-組合子-kernel.md)｜[（四）資料夾程式與執行、待定](NORMS/00-規範-4-資料夾程式與執行.md)｜概念 [CONCEPTS.md](CONCEPTS.md)｜慣例 [CONVENTION.md](CONVENTION.md)

**只收使用者親口定下的（條號 N-）。** 這四份只放規範本體；例子、原話、出處、細則在每組標題連的分檔，一兩句寫不完的限定條件照分檔全文做。四層見 [主題續](NORMS/主題-續-四層與收什麼.md)、主題見 [主題](NORMS/主題.md)。條號不重編；（草稿）（定稿）（代定、可翻案）照原文標；「待定」不算數。

## 總則

**[總則](NORMS/01-總則.md)**（[N-05](NORMS/01-總則/01-N-05.md)、[N-43](NORMS/01-總則/02-N-43.md)、[N-43 續](NORMS/01-總則/02-N-43續-11-05-兩種行與碼.md)、[N-18](NORMS/01-總則/03-N-18.md)）
- **N-05** 給別人讀的檔，先寫 `.` 開頭的暫存檔再改名蓋過去；讀的人不讀 `.` 開頭的檔（例外：aos-exec 讀入口資料夾裡的 `.env`）。
- **N-18**（草稿）實作分兩級：最小實作只做最少的步驟（aos-exec＝cd 過去→設環境變數→跑檔案），完整實作顧邊緣狀況（impls 的 aos-exec、aos-loop、aos-daemon、aos-fsm）；規範沒說的邊緣狀況在最小實作預設不應出現，出問題算使用者的事。
- **N-43**（草稿）結束碼：`0`＝正常、`10`＝正常停（要求外面的 loop 別再跑了）、其他非 0＝有錯；`10` 與非 0 是對直接收到它的那層說的，被表接住就不算。
- **N-43** aos 的程式說自己的錯一律退 1；stderr 只有兩種行：錯誤行 `程式: error: 代號 原因`、提醒行 `程式: warning: 句子`；有錯誤行就不准退 0；要分種類寫在代號裡，不另用結束碼。
- **N-43** 每層只說自己，下層的錯不往上轉述；例外只有透明轉交別人的碼（不改數字；stderr 沒有 `我的名字: error:` 那行＝下層的碼）。被訊號停掉＝128＋N；loop／fsm 收到 SIGINT／SIGTERM／SIGHUP 先轉給正在跑的那次，SIGINT 比照 SIGTERM；loop 跑滿 `max` 以 0 結束、不寫 stderr。
- **N-43** stderr／結束碼／訊號這幾句是 aos 自己那幾支程式的行為，別的 aos 函數要不要照做自己定；aos 塞進 agent 對話的文字一律 `[aos] 種類: 內容`（種類名代定、可翻案）；基礎工具的 `10`＝「查了，沒有」。

## 時空

**[設計理念／時空](NORMS/02-設計理念-時空.md)**
- **N-01** 大家都要看時鐘：aos 內部互相約的時間看時鐘（數 cycle），對人、對外、對 Linux proc（daemon）用牆上時鐘；時鐘到點寄信、不跑任意 aos 函數（時鐘檔旁的登記表，`aos-clock-register`；部分細節代定、可翻案）。
- **N-02** 資料夾別亂弄。
- **N-03** 「格（cycle）與格之間可以安全打包」是大家要遵守的規範，不強制；打包＝收工硬凍（daemon sleep），軟凍沒做；由 kernel 打包是遠期、現無實作。
- **N-65**（已定）兩鐘規則：① 期限寫 cycle 時，有 `AOS_CLOCK` 就讀它指的時鐘檔比 cycle，沒有就退牆鐘（`cycles × AOS_CLOCK_INTERVAL` 毫秒）；② 有 `AOS_CLOCK` 就只認時鐘，停了期限就不到，不自動退牆鐘、不 warning；③ 跨樹的信裡期限用毫秒（牆鐘語意、格式不限），判官排隊期限 `queue_wait_ms` 也用牆鐘；④ `AOS_CLOCK_INTERVAL` 是只會慢的標稱默契、先不補，沒設先用 1000 毫秒（暫定）。
- （無條號）時鐘停住時，判卡住、鎖租約與以 cycle 計的逾時一起停、永不到期；寫了 `stuck_after_ms` 的列判卡住用牆鐘。

## inst

**[基礎設施／inst](NORMS/03-基礎設施-inst.md)**
- （無條號）沒有 aos-inst 命令列，inst 是 C lib；單子 `argv[0]` 帶 `/` 又 exec 不了＝前面插 PATH 上的 `aos-exec`（規則在 N-61）。
- **N-04** inst 單子裡可以多放東西，inst 不認的別人可以讀：aos-exec 的 `run_inst` 認 17 個 key（`id` 只是標籤），其他 key 忽略。
- **N-25**（草稿）程式內呼叫＝aos-exec 公開 API `run_inst(單子, 基準資料夾, args, ref_base)`，回 `Result`：`code`、`signal`、`timed_out`、`pid`、`ms`、`received`；loop、fsm、daemon 的 `exec` 可以是 aos-exec 的目標，也可以直接放單子物件。
- **N-27**（草稿）子程式的參數：aos-exec 把多的 args 與 stdin 原樣送到入口，怎麼進由工具自己的說明定；單子的 `stdin: "檔"` 可以把一個檔交給子程式，不加新 key。
- **N-30**（草稿）單子的結果回給行程內的呼叫者：`code`＝子程式的碼（被訊號停掉是 128＋N），訊號另放 `signal`、逾時 `timed_out: true`；inst 不開窗；單子當入口時 aos-exec 以子程式的碼結束（透明轉交），單子壞＝aos-exec 自己的錯退 1。

## loop 與 daemon

**[基礎設施／loop、daemon](NORMS/04-基礎設施-loop與daemon.md)**（[N-10](NORMS/04-基礎設施-loop與daemon/01-N-10.md)、[N-28](NORMS/04-基礎設施-loop與daemon/02-N-28.md)、[N-54](NORMS/04-基礎設施-loop與daemon/03-N-54.md)）
- （無條號）loop＝`aos-loop [FLAGS] loop.json`：身體叫 `exec`、跑幾次叫 `max`，子程式退 10 就停；選填 `on_start`／`on_stop` 起停各跑一次（期限 `on_timeout_ms`，出問題只印 warning、不擋起停；代定、可翻案）。
- （無條號）loop／daemon 不管、使用者自行承擔：每次沒有時間上限、兩個共用同一份 state 檔、state 寫不了＝`WriteFailed` 退 1（daemon 照樣先收子項）、跑途中改 `.env` 不生效。
- **N-10**（已刪，條號留作錨點）沒有指令式控制資料夾：daemon 表上有誰由 ctl 宣告（N-54），控制子 loop＝寫它的 ctl。
- **N-28** daemon.json 是 loop.json 的嚴格超集：同名 key 同義、預設值可以不同，一份合法的 loop.json 直接丟給 aos-daemon 也要能跑；多的 key 只有 `procs`、`adopt`、`procs_ctl`、`procs_state`、`procs_requests`、`procs_loop`、`procs_exec`、`procs_stderr`、`limits`、`limits_max`、`cgroup`；認不得的 key 當沒看到。
- **N-28** 名單 `procs`＝`{名字: proc}`，看寫法決定起 loop 型或 exec 型；小格預設 `$AOS_STACK/procs/<名字>/`；兩個手把（`ctl.json` 管自身、`procs_ctl.json` 管名單）、兩扇狀態窗（`state.json`、`procs_state.json`；後者就是 save 檔，表上的路徑相對 daemon 的 stack）。
- **N-28** `adopt` 預設 `true`＝重起時接回還活著的子項；子項不自動重起，自然退 0 就下表，出錯結束留 `stopped`＋`reason`（列可選 `auto_restart`）；收工時還活著的收掉、留 `sleeping`，開門時 wake；同一個 stack 已有 daemon＝`DaemonExists` 退 1；daemon 不認時鐘；沒掛 daemon＝Linux 管。
- **N-54** daemon 表上有誰，寫在管轄手把 `procs_ctl.json`：宣告的名單、不是指令（`procs`＋`procs_added`－`procs_removed`，停／起寫 `procs_stopped`／`procs_started`，`seq` 回音）；多人要改靠 Linux 權限或名單信箱 `procs_requests`；子項的 stack 歸 daemon、不放工作區。
