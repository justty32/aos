# daemon 核心：定期叫 aos-exec

← [daemon 目錄](README.md)｜[整理區](../README.md)｜[慣例](../conventions.md)｜[名詞](../terms.md)｜格式：[P-120](../protocol/daemon/core.md)｜控制模組：[B-641](control.md)

本篇只有 B-640，寫 `aos-daemon` 核心**做什麼**。argv、設定檔每個欄位的型別、輸出行的確切樣子、結束碼，寫在格式篇 [P-120](../protocol/daemon/core.md)。

依據：[第二十批篇末「2026-10-01：最核心 daemon」整節](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01最核心-daemon待統一更新-spec)、[daemon 核心草稿](../../../notes/2026-10-01-daemon-core-sketch.md)、[plan 第三段 m3](../../../plan/m3-daemon-core.md)；現行程式 [aos-daemon](../../../src/py/README.md#aos-daemon第三段最核心-daemon)（`lib/aos_daemon.py`，有出入以程式為準）。

## B-640：最核心 daemon：定期叫 aos-exec〔使用者方向 2026-10-01〕

**daemon 就是一個定期叫 `aos-exec` 的 cron。** 設定檔裡列一串 inst，每一項照自己的週期叫一次 `aos-exec <inst>`，等它結束，在 stdout 印一行結果。

- daemon **不認得 tick 的工作資料夾**（舊稱 node；〔使用者 2026-10-01〕改名），也不讀任務表、不碰鎖、不看擋板檔。那些全是 `aos-tick` 自己的事（[通用 tick](../tick.md)）。
- 要定期跑一個 `aos-tick`，就放一份 `argv` 開頭是 `aos-tick` 的 inst（例如 `["aos-tick", "<資料夾>"]`，或只寫 `["aos-tick"]`），再把這份 inst 加進 daemon 的清單。對 daemon 來說它跟別的 inst 沒有兩樣。
- 「daemon 管 node」之後另做成可掛的模組，不在核心裡（[第二十批「node 模組方向」](../../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。
- 舊設計的登記、socket／IPC、runner、收屍、重啟清理、`state.json`、通道與憑證，第一版都不做，搬到[暫緩區](../deferred/daemon/README.md)。

### 清單：一項就是一個 inst 字面值

- 設定檔的 `insts` 是一個物件。**鍵就是 inst 字面值**，**值是這一項自己的設定**（寫 `{}` 就全用頂層預設）。
- inst 字面值**原樣**交給 `aos-exec` 當參數。資料夾或檔都行，只要 `aos-exec` 認得（[inst 目標](../../base/inst.md)）；daemon 自己不檢查、不解析、不正規化。
- **核心沒有 id。** 一項就是它的 inst 字面值；印出來也是 `inst=<字面值>`。另外照鍵在 `insts` 裡的順序從 0 數一個「第幾項」，只用在 `aos-exec` 輸出的標頭上。
- 同一個字面值不會寫兩次（默認設定檔是對的）；真的寫了，JSON 讀進來只留後面那個。

### 起點：相對路徑從哪裡算

daemon 有一個「起點」資料夾，用在三處：

1. 開 `aos-exec` 子程序時，工作目錄就是起點。
2. 相對路徑的 inst 字面值，以起點為準（因為 `aos-exec` 就在起點跑）。
3. 相對路徑的 `exec_out_path`、`exec_err_path`（下面），以起點為準。

起點怎麼定：設定檔頂層的 `cwd`；沒寫就是 daemon 啟動時的工作目錄。`cwd` 本身寫相對路徑時，也以 **daemon 啟動時的工作目錄**為準，**不是**設定檔所在的資料夾。

〔使用者 2026-10-01〕頂層 `cwd` **不影響 daemon 自己**：daemon 不 chdir，自己的工作目錄一直是啟動時那個，`cwd` 只拿來設 `aos-exec` 子程序的工作目錄、當相對路徑的起點。tasks.json 的頂層 `cwd` 也是同一個意思（不改 tick 自己）；兩邊差在相對路徑起點與指示詞展開的時機，對照表見 [C-11](../conventions.md)。

### 設定檔先展開指示詞，再讀

整份設定檔先用 aos 指示詞展開（跟 inst 同一套：`$ref`、`$fmt`、`$env`，見 [inst](../../base/inst.md)），展開完才讀裡面的鍵。這樣大設定檔可以拆成幾份檔互相引用，不會太肥。〔使用者 2026-10-01〕這點跟 tasks.json 不同：tasks.json 讀表時只展開到 `tasks` 那層，每一項內部跑到才展開（[C-11](../conventions.md)）；daemon 設定檔是**整份一次展開完**。

- **`$ref` 的相對檔名，一律以設定檔所在的資料夾為準。** 被引進來的檔裡再寫 `$ref`，也照這個資料夾算，不換中心。
- **展開完才套 `cwd`。** `cwd` 也可以是 `$ref` 引進來的值。
- 所以同一份設定檔裡有兩種起點：`$ref` 的檔名看「設定檔放在哪」；inst、`cwd`、`exec_out_path`、`exec_err_path` 看「daemon 從哪裡開（或 `cwd`）」。
- `$opt` 選項物件原樣留著、不走進去。核心沒有吃選項的地方，留給之後的模組。
- 指示詞錯（引的檔讀不到、循環引用、位置找不到……）算設定錯，daemon 不開始跑（碼與訊息見 [P-120](../protocol/daemon/core.md)）。

### 週期：從上一次結束起算，不補跑

- **開起來時每一項先各跑一次**，不等第一個週期。
- 之後每一項在**上一次結束後**隔 `interval_ms` 再跑。漏掉的不補（例如某次跑了比週期還久，下一次照樣從結束算起）。
- **每一項各跑各的。** 同一項同時只會有一個 `aos-exec` 在跑；不同項互不等待。
- `interval_ms` 頂層寫的是預設，每一項自己寫的蓋過頂層。兩邊都沒寫就是設定錯。
- 時間用毫秒：週期是外部世界定的時間，daemon 本身也不在任何一格裡，照 [C-01](../../contracts.md)「外部規定的時間保留毫秒」。

### 非 0 時停不停

- `stop_on_nonzero` 為 true 時，這一項的 `aos-exec` 回非 0，這一項就**不再叫**，stdout 多印一行 `stopped`。
- 頂層寫的是預設，每一項自己寫的蓋過頂層；兩邊都沒寫＝false（照樣繼續叫）。
- 0 與非 0 照 [C-08](../conventions.md)：只看是不是 0，不替非 0 的碼分等級。
- **所有項都停了，daemon 照樣開著**，不自己退出。要救回停掉的項，掛了控制模組時可以用 `resume`（[B-641](control.md)）；沒掛控制模組就重開 daemon——〔2026-10-01 第十一批〕但**掛了記住狀態模組時重開救不回**（已停會跨重開，[B-643](state.md)），要刪掉狀態檔（或檔裡那一項）再重開。

### 輸出

- **daemon 自己的 stdout**：每次 `aos-exec` 結束印一行：印出那一刻的本地時間、inst 字面值、結束碼、花了幾毫秒。被訊號 N 殺掉的，碼印成 128+N。停掉時在那次的 exit 行之後另印一行 `stopped`；兩行分開印，中間可能穿插其他項的行〔astra 報告必修 8〕。
- **`aos-exec` 的 stdout、stderr** 兩條各由頂層一個鍵決定寫到哪：`exec_out_path` 管 stdout、`exec_err_path` 管 stderr。〔使用者方向 2026-10-01〕**沒寫就丟掉**（等於 `/dev/null`），不再接到 daemon 自己的 stdout／stderr；想接回來就寫 `"/dev/stdout"`、`"/dev/stderr"`。
- 兩個鍵規則一樣：接在檔尾、父資料夾不在就建；相對路徑以起點為準；裡面的 `<inst>` 會換成這一項的位置：inst 是資料夾就換成字面值本身，是檔就換成它字面上的資料夾部分（沒有資料夾部分就用 `.`）。兩個鍵可以指同一個檔。
- 每次**收齊**（讀到底）再一次寫出，有內容才寫；前面一律加一行標頭，寫明時間、是 stdout 還是 stderr、第幾項、inst 字面值。寫出跟 daemon 自己那一行共用一把鎖，多項同時結束也不會交錯。
- inst 裡任務自己的 stdout／stderr 照 inst 規則（預設丟掉，寫 `{"$opt":"inherit"}` 才會跟著 `aos-exec` 出來）。
- 確切格式見 [P-120](../protocol/daemon/core.md)。

### 停機：Ctrl-C 直接退出

- 收到 SIGINT（Ctrl-C）或 SIGTERM，daemon **直接退出、回 0**。
- **不殺也不等**正在跑的 `aos-exec`。每次 `aos-exec` 都開在自己的 session 裡，終端機的 Ctrl-C 不會順帶打到它。
- daemon 退出後，還在跑的 `aos-exec` 若有設 `exec_out_path`／`exec_err_path`，再寫那一條會因為沒人讀而被 SIGPIPE 殺掉（沒設的那條接的是 `/dev/null`，不會）。照「POC 默認一切正常」不處理（使用者 2026-10-01 同意）。
- 舊設計的收尾寬限、排空停機、`state.json` 都不做（[暫緩區 B-604](../deferred/daemon/lifecycle.md)）。

### 模組：`modules`

- 設定檔頂層可以有 `modules` 物件，**一個模組一個鍵，有寫就開**，沒寫就是沒掛。
- 核心只認得 `modules` 這個位置，不解讀裡面的內容；不認得的模組鍵照收、不理。
- 目前有六個模組：控制模組 `control`（[B-641](control.md)），讓人或任務能叫醒、暫停、恢復、查詢某一項；重讀設定 `reload`（[B-642](reload.md)），SIGHUP 重讀設定檔；記住狀態 `state`（[B-643](state.md)），暫停與已停跨重開；收屍／cgroup `cgroup`（[B-644](cgroup.md)），每項一個 cgroup 框、跑完清掉殘留、可設上限；訊息 `mq`（[B-645](mq.md)），每項一個信箱、`aos-mq` 收發；帳號 `account`（[B-646](account.md)），用 root 開、主程式降權、別的帳號的項由 root 端開。
- 跟某一項有關的模組設定寫在 `insts` 那一項裡、用模組名當鍵（例如 `"a": {"cgroup": {"memory.max": "512M"}}`）；模組沒掛時核心照「不認得的鍵」忽略。
- 沒掛任何模組時，daemon 就是上面寫的樣子：不開 socket、不多傳環境變數、SIGHUP 照 Python 預設（daemon 被殺）、不讀寫狀態檔、不碰 cgroup。
- 這取代了舊設計的五個開關鍵（[暫緩區 B-615](../deferred/daemon/components.md)）。

### 第一版默認一切正常

〔使用者方向 2026-10-01〕POC 默認環境一切正常：設定檔讀得懂、路徑都對、`aos-exec` 叫得起來。daemon 自己查的只有幾件事（缺 `interval_ms`、`modules` 不是物件、指示詞錯），其他出事就讓程式自然丟錯、回 1。哪些算設定錯、怎麼報，見 [P-120](../protocol/daemon/core.md)。

依據：使用者方向 2026-10-01（daemon 叫 `aos-exec`、管 node 變成模組、週期與停機、設定檔追加裁定、m3 待問裁定、m3 實作後追加裁定、`insts` 改成物件、`exec_out_path` 與輸出預設丟掉）。

**驗收：**兩項各自照自己的週期跑、互不等待；剛開時每項立刻跑一次；某項回非 0 且 `stop_on_nonzero` 時印 `stopped`、之後不再叫，其他項照跑，全部停掉 daemon 仍開著；相對的 inst、`cwd`、`exec_out_path`、`exec_err_path` 照起點算，`$ref` 照設定檔資料夾算；沒寫 `exec_out_path`／`exec_err_path` 時 `aos-exec` 的輸出不出現在 daemon 的 stdout／stderr；兩項同時結束時寫出不交錯；Ctrl-C 後 daemon 回 0、正在跑的 `aos-exec` 沒被殺。測試見 `proto6/src/py/tests/test_daemon.py`。
