# 第三段：daemon 核心（最核心版）

← [plan 入口](README.md)｜依據：[最核心 aos-daemon（已裁定 10-01）](../notes/2026-10-01-daemon-core-sketch.md)｜結束碼：[verdicts 11 篇末「aos 結束碼慣例」](../notes/verdicts/11-tick-as-unit/04-1001-結束碼慣例.md#aos-結束碼慣例待統一更新-spec)｜spec 正本：[B-640](../spec/settled/daemon/core.md)、格式 [P-120](../spec/settled/protocol/daemon/core.md)｜舊 spec（暫緩區，大部分先不做）：[B-601](../spec/settled/deferred/daemon/runtime/01-B-601-socket與IPC授權.md#b-601記憶體登記與按需執行)、[B-606](../spec/settled/deferred/daemon/registration/01-B-606-登記與上層.md#b-606登記解除換父與身分額度)、[B-607](../spec/settled/deferred/daemon/registration/03-B-607-叫醒暫停與故障停格.md#b-607叫醒暫停故障停格與格次序號)、[P-101](../spec/settled/deferred/protocol/daemon/startup-and-ipc/01-P-101-指令與結束碼.md#p-101啟動設定與-socket建議預設未拍板)

**做完的樣子**：沒有 root、systemd、cgroup、helper 的機器上，一般帳號跑 `aos-daemon --config F`：讀設定檔裡的 inst 路徑清單，每一項照自己的週期叫一次 `bin/aos-exec <inst 路徑>`，每次結束在 stdout 印一行 `<當下時間> inst=… exit=… ms=…`；aos-exec 的 stdout、stderr 收齊後帶一行標頭寫到設定的檔（沒設就丟掉）；非 0 時停不停照該項設定；Ctrl-C 直接退出、回 0。node 資料夾放一份 `argv` 寫 `aos-tick` 的 `inst.json`，把它加進清單，就是「daemon 定期跑一個 node」。

> **這次範圍砍到哪（使用者 2026-10-01）**：[plan 入口第三段](readme/01-六段總覽-一至三段.md#第三段daemon-核心)原本寫的是 spec 完整的開格核心——登記／解除／換父、叫醒／暫停、`aos-runner` 開格與格後收屍、重啟與停機收尾、通道憑證、socket 與 IPC、`state.json`、掛行程與砍掉。這次全部不做，只做[最核心草稿](../notes/2026-10-01-daemon-core-sketch.md)裁定後的版本：**一個叫 `aos-exec` 的 cron**。daemon 不認得 node，node 的事（`tasks.json`、鎖、擋板、紀錄）全在 `aos-tick` 那側（草稿「管 node 變成可掛載的模組」）。
>
> **挪到之後**（還沒排進哪一段，等這版做完、使用者看過再排）：叫醒（第一個要加，要 socket）、暫停／恢復、登記與上下層、runner 與收屍、逾時、收尾寬限與排空停機、重啟清理與 `state.json`、通道與憑證、事項、熱重載、B-615 五個開關、`aos daemon` 子命令。第四、五段（訊息、cgroup、helper）原本建在完整第三段上，開工前要重看前提。

> **10-01 追加裁定（使用者，原話節錄）**：「關於印出來的樣子，其實不用是id，應該是inst=j/r.json這樣。id這個概念其實可以不存在於daemon核心了。」「daemon config json的頂層可以加上一個key: modules。然後整份daemon config都可以用aos dirictive去解析」「$ref 照建議，從設定檔所在資料夾算，算完之後才讓cwd那個key被應用。」另同意實作回報三點：stderr 標頭一律加（含 `<inst>` 個別檔）、inst 沒有資料夾部分時 `<inst>` 換成 `.`、daemon 退出後 aos-exec 寫 stderr 吃 SIGPIPE 不處理。下面各步已照改：**核心沒有 id**（一項＝`inst` 字面值＋在 `insts` 的位置）、**整份設定檔先展開指示詞**、**頂層 `modules` 認得不解讀**（步驟 1）、印 `inst=…`（步驟 2、4、6）。

> **10-01 再追加：`insts` 改成物件（使用者原話「daemon config中，其實可以是{"insts":{"jobs/report.json":{...},"haha.json":{...}}}」）**：鍵＝inst 字面值，值＝該項設定物件（可為 `{}`）；陣列寫法與項內 `inst` 鍵撤掉、不相容。第幾項（stderr 標頭的 `index`）照鍵的順序從 0 數。步驟 1、2 與測試已照改；verdicts 11 篇末同步記了（已寫入 spec（commit 前由我補號））。

> **10-01 三追加：`exec_out_path`、輸出預設丟掉（使用者原話「aos-exec的輸出，也可以放在aos daemon config的頂層，類似exec error path那樣去設定。不設定的話默認/dev/null。然後exec error path沒設定的話也幫我改成默認/dev/null。」）**：頂層新鍵 `exec_out_path` 接 aos-exec 的 stdout，規則全照 `exec_err_path`；兩個鍵沒寫都是丟掉（`/dev/null`），不再接到 daemon 自己的 stdout／stderr，要接回就寫 `/dev/stdout`、`/dev/stderr`。標頭多一欄 `stdout`／`stderr`。步驟 1、2 與測試已照改；verdicts 11 篇末同步記了（已寫入 spec（commit 前由我補號））。

> **POC 總原則**：默認一切正常——設定檔讀得懂、路徑都對、`aos-exec` 叫得起來、沒有兩個 daemon 跑同一份清單。不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。

> **結束碼**（使用者 2026-10-01）：0＝預料之中；0 以外＝要額外處理；1＝通用錯誤，沒特別設的錯一律 1。`aos-tick` 的忙、擋板、停格都回 0；`aos-exec` 用法錯回 1（這兩處程式改動另有人做，本段當它已改好）。

- 由 AI 隊實作、照各步驟驗收試跑，做完交使用者看；每步的「要使用者裁定的點」集中在文末待問。
- Python 3.9、只用標準庫。放 [src/py](../src/py/README.md)：入口 `bin/aos-daemon`（薄殼，`.gitignore` 擋 `bin/`，要 `git add -f`）、`lib/aos_daemon*.py`；測試 `tests/test_daemon.py`，用 `unittest`。檔案怎麼切 AI 隊自己定。
- 叫的是**同一個 `bin/` 資料夾裡的 `aos-exec`**（不靠 PATH），參數只給 inst 路徑，不帶 `--stderr`、`--timeout-ms`。
- 做完要補 src/py README 的檔案表（proto6 的逐檔表就在那裡；[code map](../../wf/workflows/common/code-map.md) 目前不收 proto6，沒動）。
- **實作**（2026-10-01）：全部在 `lib/aos_daemon.py` 一個檔；各步對到的函式寫在各步「做法」。

## 分檔目錄

> 2026-10-02 整理：原檔約 27 KB 超過 8 KB 門檻，按標題逐字拆進 `m3-daemon-core/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-步驟1-讀設定檔.md](m3-daemon-core/01-步驟1-讀設定檔.md) | 步驟 1：讀設定檔 |
| 2 | [02-步驟2-4-叫exec與週期.md](m3-daemon-core/02-步驟2-4-叫exec與週期.md) | 步驟 2：叫一次 aos-exec、印一行；步驟 3：照週期叫、各跑各的；步驟 4：非 0 停不停 |
| 3 | [03-步驟5-7與待問做完了沒.md](m3-daemon-core/03-步驟5-7與待問做完了沒.md) | 步驟 5：Ctrl-C 與 SIGTERM；步驟 6：掛上 aos-tick（node 當模組）；步驟 7：整段驗收；這段不做的，先怎麼擋著；待問；做完了沒 |
