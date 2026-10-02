# 第三段：daemon 核心（最核心版）

← [plan 入口](README.md)｜依據：[最核心 aos-daemon（已裁定 10-01）](../notes/2026-10-01-daemon-core-sketch.md)｜結束碼：[verdicts 11 篇末「aos 結束碼慣例」](../notes/verdicts/11-tick-as-unit/04-1001-結束碼慣例.md#aos-結束碼慣例待統一更新-spec)｜spec 正本：[B-640](../spec/settled/daemon/core.md)、格式 [P-120](../spec/settled/protocol/daemon/core.md)｜舊 spec（暫緩區，大部分先不做）：[B-601](../spec/settled/deferred/daemon/runtime.md#b-601記憶體登記與按需執行)、[B-606](../spec/settled/deferred/daemon/registration.md#b-606登記解除換父與身分額度)、[B-607](../spec/settled/deferred/daemon/registration.md#b-607叫醒暫停故障停格與格次序號)、[P-101](../spec/settled/deferred/protocol/daemon/startup-and-ipc.md#p-101啟動設定與-socket建議預設未拍板)

**做完的樣子**：沒有 root、systemd、cgroup、helper 的機器上，一般帳號跑 `aos-daemon --config F`：讀設定檔裡的 inst 路徑清單，每一項照自己的週期叫一次 `bin/aos-exec <inst 路徑>`，每次結束在 stdout 印一行 `<當下時間> inst=… exit=… ms=…`；aos-exec 的 stdout、stderr 收齊後帶一行標頭寫到設定的檔（沒設就丟掉）；非 0 時停不停照該項設定；Ctrl-C 直接退出、回 0。node 資料夾放一份 `argv` 寫 `aos-tick` 的 `inst.json`，把它加進清單，就是「daemon 定期跑一個 node」。

> **這次範圍砍到哪（使用者 2026-10-01）**：[plan 入口第三段](README.md#第三段daemon-核心)原本寫的是 spec 完整的開格核心——登記／解除／換父、叫醒／暫停、`aos-runner` 開格與格後收屍、重啟與停機收尾、通道憑證、socket 與 IPC、`state.json`、掛行程與砍掉。這次全部不做，只做[最核心草稿](../notes/2026-10-01-daemon-core-sketch.md)裁定後的版本：**一個叫 `aos-exec` 的 cron**。daemon 不認得 node，node 的事（`tasks.json`、鎖、擋板、紀錄）全在 `aos-tick` 那側（草稿「管 node 變成可掛載的模組」）。
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

## 步驟 1：讀設定檔

- **要做到**：`aos-daemon --config F` 讀設定檔，得到一份清單，每項有 `inst` 字面值（`insts` 物件的鍵）、鍵的位置、週期、非 0 停不停（沒有另外的 id）；另外算好一個「起點資料夾」給步驟 2 開子程序用。
- **依據**：草稿裁定 1、7 與[設定檔追加裁定](../notes/2026-10-01-daemon-core-sketch.md#設定檔追加裁定使用者-2026-10-01)；[B-606](../spec/settled/deferred/daemon/registration.md#b-606登記解除換父與身分額度)「頂層從設定載入」只留這條路；[P-101](../spec/settled/deferred/protocol/daemon/startup-and-ipc.md#p-101啟動設定與-socket建議預設未拍板) 的設定欄位這版不沿用（裁定 7 隨意）。
- **設定檔**（使用者 2026-10-01 認可）：

  ```json
  {
    "cwd": "/home/u/nodes",
    "interval_ms": 60000,
    "stop_on_nonzero": false,
    "exec_out_path": "<inst>/out.log",
    "exec_err_path": "<inst>/err.log",
    "insts": {
      "a": {},
      "jobs/report.json": {"interval_ms": 5000, "stop_on_nonzero": true}
    }
  }
  ```

  上例：`a` 是資料夾（aos-exec 自己去找 `a/.aos/inst.json` 或 `a/inst.json`），用頂層的 60 秒、非 0 不停；`jobs/report.json` 是檔，自己蓋成 5 秒、非 0 就停。兩項都相對 `/home/u/nodes`。aos-exec 的 stderr 分別接到 `/home/u/nodes/a/err.log`、`/home/u/nodes/jobs/err.log`，stdout 接到同資料夾的 `out.log`（見下面 `exec_err_path`、`exec_out_path`）。
  - `insts`：物件（使用者 2026-10-01 改；~~陣列、每項 `inst` 必填~~）。**鍵＝inst 字面值**，**值＝該項設定物件**：可寫 `interval_ms`、`stop_on_nonzero` 蓋過頂層，`{}`＝全用頂層。第幾項照鍵的順序（Python `json` 讀入保序）從 0 數。
  - inst（`insts` 的鍵）：**原樣交給 aos-exec**，資料夾或檔都行，只要合 aos-exec 的目標規則（見 [src/py README 改動 2](../src/py/README.md#改動-2資料夾目標怎麼找-inst)）；daemon 不檢查、不解析、不轉絕對路徑。
  - 頂層 `cwd`（可省略）：相對路徑的起點。沒寫＝daemon 啟動時的工作目錄；本身是相對路徑時也以 daemon 啟動時的工作目錄為起點。daemon 開起來時算成一個絕對路徑（`os.path.abspath`，不解符號連結）。
  - 頂層 `interval_ms`、`stop_on_nonzero`（可省略）：所有項的預設；每項自己寫的蓋過頂層。`interval_ms` 正整數，兩邊都沒有＝設定錯、回 1（沒有叫醒，沒週期就永遠不會跑）；`stop_on_nonzero` 布林，兩邊都沒有＝`false`。
  - 頂層 `exec_err_path`（可省略；使用者 2026-10-01，見待問 5）：aos-exec 子程序的 stderr（fd 2）往哪寫。相對路徑以起點為準。路徑裡的 `<inst>` 換成該項 `inst` 字面值；`inst` 指的是檔時換成它字面上的 dirname（`x.json` 的 dirname 是空的，用 `.`），是資料夾就照字面（daemon 開起來時在起點底下看一次是不是資料夾）。~~沒寫＝daemon 自己的 stderr~~ 沒寫＝丟掉（`/dev/null`，使用者 2026-10-01 改）。細節見步驟 2。
  - 頂層 `exec_out_path`（可省略；使用者 2026-10-01 加）：aos-exec 子程序的 stdout（fd 1）往哪寫，規則全照 `exec_err_path`（同一個 `err_path_for()` 算）。沒寫＝丟掉（`/dev/null`）。
  - 頂層 `modules`（可選；使用者 2026-10-01）：要是物件，不是＝設定錯、回 1。之後一個模組一個鍵（例如 `"modules": {"control": {...}}`）；目前沒有任何模組，核心照收、不看裡面。
  - 其他鍵（頂層或每一項的設定物件裡）一律忽略，所以寫 `_metainfo` 也沒關係。
  - 不驗格式（默認是對的），缺鍵或型別錯就自然丟錯、回 1。
- **整份先經 aos 指示詞展開**（使用者 2026-10-01）：跟 inst 同一套 `lib/aos_directives.py`（`$ref`／`$fmt`／`$env`）。順序：
  1. 先展開：從根一路走進物件與陣列、每格解到底（`expand()`）。`$ref` 的相對檔名**一律以設定檔所在資料夾**為準（`os.path.abspath`，不解符號連結；被引進來的檔裡再 `$ref` 也照這個資料夾）。`$opt` 物件原樣留著不走進去（核心沒有吃選項的位置）。引到祖先＝`ReferenceCycle`。
  2. 展開完才讀鍵：`cwd`（可以是引進來的值）照上面規則算起點——相對的 `cwd` 以 **daemon 啟動時的工作目錄**為準；`inst`、`exec_out_path`、`exec_err_path` 再以起點為準。
  - 兩種起點不同：`$ref` 檔名看設定檔放哪，`cwd`／`inst` 的值看 daemon 從哪開。為什麼選設定檔資料夾：指示詞規範說中心路徑由宿主給；設定檔沒有像 inst 那樣「解出來的 cwd」可當中心（daemon 的 `cwd` 是給 aos-exec 的，相對值還以 daemon 啟動目錄為準），用文件所在資料夾是 `Context` 沒給中心時的預設，最不意外。
- **沒有 id**（使用者 2026-10-01）：~~id 就是 `inst` 的字面值~~ 核心沒有 id 這個概念，一項就是它的 `inst` 字面值，印出來、標頭都照字面。`insts` 改成物件後同字面值本來就寫不出兩項（同一個鍵寫兩次，JSON 讀入只留後面那個），不檢查。
- **做法**：argv 只認 `--config F`（必填；`F` 相對路徑照常以 daemon 啟動時的工作目錄為準）；用法錯 stderr 一行、回 1（argparse 預設 2，改了：`_Parser`）。讀設定是 `load_config()`（先 `read_config()` 讀檔、`expand()` 展開），回起點與 `Item` 清單（每項記 `index`＝鍵在 `insts` 的位置、`inst`＝鍵、週期、停不停、算好的 stdout／stderr 檔路徑 `err_path_for()`）。兩邊都沒有 `interval_ms`、`modules` 不是物件時 stderr 一行 `aos-daemon: config: …`、回 1；檔不存在、JSON 壞、指示詞錯也走這條（`aos-daemon: config: <代號>: …`，例如 `ReferenceReadFailed`），缺 `insts`、`insts` 不是物件或某項的值不是物件是 traceback、回 1。
- **要使用者裁定的點**：無（原待問 1、2 已因追加裁定結案）。
- **驗收**：
  - `insts` 物件：`index` 照鍵的順序（`{"z":{},"a":{},"m":{}}` 是 0、1、2，不排序）；值 `{}` 用頂層預設。
  - inst 照字面印：`a`、`./a`、`/abs/a/inst.json` 印出來就是 `inst=` 後面這三個字串。
  - 指示詞（`Step1Directives`）：設定檔放 `conf/`、daemon 從別處開，`insts` 用 `$ref` 拆到 `conf/list.json`、頂層預設從 `conf/defaults.json` 引進、單一項的設定物件用 `$ref`；`cwd` 從別檔引進、相對值照 daemon 啟動目錄；讀不到檔、循環回 1。
  - `modules`：寫了任意內容照跑、不理；不是物件回 1。
  - 起點：沒寫 `cwd` 時用 daemon 啟動時的工作目錄；`"cwd": "sub"` 是啟動時工作目錄底下的 `sub`；`"cwd": "/abs"` 就是 `/abs`。
  - 頂層預設與覆蓋：頂層 `interval_ms` 套到沒寫的項，有寫的項用自己的；`stop_on_nonzero` 同理，兩邊都沒有＝不停。
  - 兩邊都沒有 `interval_ms`：回 1。
  - `exec_err_path`：`<inst>` 對檔換 dirname、對資料夾照字面、沒 `<inst>` 就一個共用檔；相對以起點為準。沒寫＝`None`（丟掉）；`exec_out_path` 同。
  - 沒給 `--config`、多給不認得的參數：回 1。
  - 設定檔不存在或不是 JSON：回 1（traceback 就好）。

## 步驟 2：叫一次 aos-exec、印一行

- **要做到**：對清單的一項開一個子程序 `<bin>/aos-exec <inst 字面值>`，工作目錄設成步驟 1 的起點資料夾，等它結束，stdout 印一行。
- **依據**：草稿「怎麼叫」「怎麼看結束碼」；裁定 1、8。
- **做法**：
  - 子程序自成 session（`start_new_session=True`），stdin 接 `/dev/null`；~~stdout 繼承 daemon 的~~ **stdout、stderr 有設路徑的各接一條 pipe，`communicate()` 讀到底收齊；沒設的直接接 `/dev/null`**（使用者 2026-10-01 改，下面「stdout 與 stderr」）。inst 裡任務自己的串流照 inst 規則（預設 `/dev/null`；寫 `inherit` 就跟著 aos-exec 的，也就進了這條 pipe），不歸 daemon。**子程序的工作目錄設成起點資料夾**（`Popen(cwd=…)`），`inst` 字面值原樣當參數：相對的 `inst` 由 aos-exec 照它自己的規則、從起點解析，跟人站在起點手打 `aos-exec <inst>` 一模一樣，daemon 不碰路徑。環境變數照 daemon 的。inst 自己的 `cwd` 預設是 inst 所在資料夾（資料夾目標是那個資料夾），由 aos-exec 處理，不受起點影響。
  - 一行的格式（使用者 2026-10-01 加時間，見待問 4）：`<當下時間> inst=<inst 字面值> exit=<碼> ms=<毫秒>`，例如 `2026-10-01T15:04:05+08:00 inst=a exit=0 ms=812`（~~`id=`~~，使用者 2026-10-01 改）。時間是印出那一刻的本地時間，ISO 8601 到秒、帶時區（`now()`）。寫完立刻 flush。碼照實印；aos-exec 被訊號殺（`returncode` 是負的）印成 `128+N`，跟 shell 一致。`ms` 從開子程序到 `wait` 回來。
  - **stdout 與 stderr**（使用者 2026-10-01，見待問 5；同日加 stdout、改預設）：子程序結束後，把收齊的兩條一次寫出（`write_outputs()`）；哪條沒內容或沒設路徑就不寫。寫出去的是一行標頭加原樣內容（最後沒換行就補一個），純文字、不包 JSON。標頭 `== <當下時間> <stdout|stderr> index=<鍵在 insts 的位置，照鍵的順序從 0 起> inst=<inst 字面值> ==`（~~沒有 `stdout`／`stderr` 那欄~~，加 stdout 時加上）。**接在 `exec_out_path`／`exec_err_path` 指的檔尾**（`ab`；父資料夾不在就建），~~沒寫就寫到 daemon 自己的 stderr~~ 沒寫就丟掉。同一次兩條都有就先 stdout 段、再 stderr 段。
  - **標頭一律加**（使用者 2026-10-01 同意）：使用者說有 `<inst>` 的個別檔可加可不加，這裡選「有內容就加」一條規則。理由：同一個資料夾裡的兩份 inst（`a/x.json`、`a/y.json`）換完 `<inst>` 是同一個檔，本來就是共用的；標頭也帶了時間。
  - 不交錯：daemon 的那一行與 aos-exec 的 stdout、stderr 段都在同一把鎖（`_out`）底下一次寫完，多項同時結束時誰都插不進誰。
  - 一次叫的全程是 `run_once()`。
- **要使用者裁定的點**：無（待問 4、5 已裁定）。
- **驗收**：
  - 假 inst `{"argv": ["sh", "-c", "exit 3"]}`：印 `exit=3`；`{"argv": ["true"]}`：`exit=0`。
  - 從別的資料夾啟動 daemon、設定檔寫 `"cwd"` 加相對 `inst`：照樣找得到、跑得起來；不寫 `cwd` 時相對 daemon 啟動時的工作目錄。
  - 假 inst 把 `$$`、`$PPID` 寫進檔：子程序的 session id 不等於 daemon 的。
  - 每一行合 `<ISO 時間帶時區> inst=… exit=… ms=…`。
  - ~~inst 寫 `"stderr": {"$opt": "inherit"}` 時 stderr 帶標頭印到 daemon 的 stderr~~（使用者 2026-10-01 改）：`exec_out_path`／`exec_err_path` 都沒寫時，inst 寫了 `inherit` 也看不到，daemon 的 stdout 只有自己的行、stderr 空（`test_default_discard`）。寫成 `/dev/stdout`、`/dev/stderr` 時帶標頭（`stdout`／`stderr`、`index`、`inst` 對）接回 daemon 的 stdout／stderr；inst 沒寫 `inherit` 時看不到。aos-exec 自己的錯（目標不存在）也帶標頭出現。
  - `exec_out_path` 有 `<inst>`：stdout 各寫各的檔、接在檔尾、父資料夾自動建；跟 `exec_err_path` 指同一個檔時兩段各有自己的標頭（`test_out_file_per_inst_and_shared`）。
  - `exec_err_path` 有 `<inst>`：各寫各的檔、接在檔尾（跑兩次就兩段）、父資料夾自動建、daemon 的 stderr 是空的。
  - `exec_err_path` 沒 `<inst>`：兩項各一口氣印 300 行，共用檔裡每段標頭後面只有那一項的行，不交錯。

## 步驟 3：照週期叫、各跑各的

- **要做到**：每一項 daemon 一開就立刻跑一次；之後每次結束後隔 `interval_ms` 再叫；同一項不疊著開；不同項同時跑、互不等。
- **依據**：裁定 4；[B-607](../spec/settled/deferred/daemon/registration.md#b-607叫醒暫停故障停格與格次序號) 定期那段、[B-601](../spec/settled/deferred/daemon/runtime.md#b-601記憶體登記與按需執行) 同一項只一個子程序。
- **做法**：每一項一條執行緒（`daemon=True`），跑 `loop()`：「叫 → 等 → 印 → 睡 `interval_ms`」。不補跑漏掉的次數，週期是「間隔」不是「時刻表」。
- **要使用者裁定的點**：無（已裁定）。
- **驗收**（都用短週期，例如 100 ms）：
  - 假 inst 每次在檔裡加一行：daemon 一開很快就有第一行（測試放寬到 2 秒，含 Python 起動）；之後一直加。每次叫 aos-exec 有幾十毫秒的 Python 起動時間，所以 1 秒內的次數比 10 少，測試只驗「會重複」。
  - 假 inst `sleep 0.3`、週期 50 ms：檔裡記號是 start、end 交替（不疊），每次 `ms` 都 ≥ 300。
  - 兩項，一項 `sleep 30`、一項 `true` 週期 50 ms：`true` 那項照常一直印，不被卡住那項拖住。

## 步驟 4：非 0 停不停

- **要做到**：一次跑完碼不是 0 時，`stop_on_nonzero` 是 `true` 就不再叫這一項（直到重開 daemon），`false` 就照常排下一次。
- **依據**：裁定 2、3、8；結束碼慣例「0 以外要額外處理」。
- **做法**：停的時候在那一行之後多印一行 `inst=<inst 字面值> stopped`。其他項不受影響。所有項都停了，daemon 照樣開著、什麼都不做（使用者 2026-10-01，待問 3）：主執行緒只在 `signal.pause()` 等訊號，不管還有幾項在跑。
- **要使用者裁定的點**：無（待問 3 已裁定）。
- **驗收**：
  - `{"argv": ["false"]}` 帶 `stop_on_nonzero: true`：只印一行 `exit=1` 跟一行 `stopped`（`<時間> inst=<inst> stopped`），之後不再出現這個 inst；同時另一項照跑。
  - 唯一一項停了：daemon 還開著。
  - 同樣的 inst 帶 `false`（或不寫）：一直印 `exit=1`。
  - 碼是 0 時 `true` 也不停。
  - inst 路徑不存在：aos-exec 回非 0（改好後是 1），照上面停或不停。

## 步驟 5：Ctrl-C 與 SIGTERM

- **要做到**：收到 SIGINT 或 SIGTERM，daemon 直接退出、回 0，不殺也不等正在跑的子程序。
- **依據**：裁定 5；[B-604](../spec/settled/deferred/daemon/lifecycle.md#b-604收尾停機停用與退役) 的收尾這版不做。
- **做法**：兩個訊號都當「使用者要停」，handler 直接 `os._exit(0)`（`_quit()`；每行都已 flush）。子程序在自己的 session，終端的 Ctrl-C 打不到它們，會自己跑完。
- **要使用者裁定的點**：無（已裁定）。
- **驗收**：
  - 開 daemon，等第一行後送 SIGINT：1 秒內退出、回 0。SIGTERM 一樣。
  - 退出時有一項正在 `sleep 1; touch done`：daemon 退出後那個檔照樣出現（子程序沒被殺）。

## 步驟 6：掛上 aos-tick（node 當模組）

- **要做到**：證明「daemon 定期跑一個 node」不需要 daemon 認得 node，只要一份 inst。
- **依據**：裁定 1「管 node 變成可掛載的模組」；[第一段](m1-tick-core.md)的 `aos-tick`。
- **做法**：不寫新程式，只寫測試與 README 例子。node 資料夾長這樣：

  ```text
  /n/a/inst.json         {"argv": ["aos-tick"], "stderr": {"$opt": "inherit"}}
  /n/a/.aos/tasks.json   照第一段的任務表
  ```

  inst 的 `cwd` 預設就是 `/n/a`，tick 不帶目標（原 `--node`，2026-10-01 改名 `--target`、再改成位置參數）用 `./`。測試裡 `argv[0]` 寫 `bin/aos-tick` 的絕對路徑，不靠 PATH。
- **要使用者裁定的點**：無。
- **驗收**：
  - 清單放 `/n/a/inst.json`、週期 100 ms，跑 1 秒：每次印 `inst=/n/a/inst.json exit=0`，`.aos/tick/current/record.json` 的 `seq` 一直往上加（2026-10-01 第九批：紀錄拆成資料夾，原 `current.json`）。
  - 清單改寫資料夾 `/n/a`：一樣跑得起來（aos-exec 自己找到 `inst.json`），印 `inst=/n/a`。
  - 放上擋板檔：照樣每次 `exit=0`，`seq` 不動，daemon 的 stderr 有帶標頭的 `blocked: …`（inst 寫了 `inherit`）；拿掉後又開始加。
  - 任務表寫壞：tick 回 1，daemon 印 `exit=1`；`stop_on_nonzero: true` 時印 `stopped`。
  - 同一個 node 放進兩個 daemon 同時跑：都只看到 `exit=0`，紀錄沒壞（靠 tick 的鎖）。

## 步驟 7：整段驗收

- 步驟 1～6 的驗收合成 `tests/test_daemon.py`，一條指令跑完；不需要 root、systemd、網路，全部用暫存資料夾、短週期、假 inst，每條幾秒內結束。
- 測試結束自己殺掉 daemon 和留下的子程序（daemon 不殺，見步驟 5），用 process group 殺乾淨。
- 原有的測試（tick、exec、inst）照樣全過。
- 實際：`tests/test_daemon.py` 32 條，一個類別一步（`Step1Config`～`Step6Tick`，步驟 1 另有 `Step1Directives` 4 條），整檔約 6 秒；全部 444 條（原 412；10-01 追加裁定前 440）。會留下來的任務把自己的 pid 寫進 `pids`，收尾時 `killpg` 殺掉；還要先殺它們再關 daemon 的 pipe（留下的 aos-exec 還拿著 daemon 的 stdout）。

## 這段不做的，先怎麼擋著

| 不做 | 這版的樣子 | 什麼時候 |
|---|---|---|
| 叫醒、socket、IPC、授權 | 只有週期；要馬上跑就重開 daemon | 之後第一個加 |
| 暫停／恢復 | 放擋板檔（tick 回 0、什麼都不做） | 之後 |
| 登記、上下層、身分額度 | 清單只從設定檔來，平的 | 之後 |
| runner、收屍、逾時 | 叫現成的 `aos-exec`；卡住就一直卡、留下的程序沒人收 | 之後 |
| 收尾寬限、排空、重啟清理、`state.json` | Ctrl-C 直接退出；重開就從頭來 | 之後 |
| 熱重載 | 改設定就重開 | 之後 |
| 訊息、cgroup、helper、B-615 開關 | 沒有 | 第四、五段（前提要重看） |
| `aos daemon` 子命令 | 獨立指令 `aos-daemon` | 之後 |

## 待問

1. ~~**`/n/a/.aos/inst.json` 的 id 怎麼算？**~~ **結案**（使用者 2026-10-01）：id 不另算、就是 `inst` 字面值，沒有「拿掉 `/inst.json`」這回事了。node 的 inst 放在 `.aos/` 裡時，清單直接寫 node 資料夾（例如 `/n/a`），aos-exec 先找 `.aos/inst.json`、base 是 `/n/a`，不用寫 `"cwd": ".."`。（同日再改：核心連 id 這個概念都拿掉，見開頭 10-01 追加裁定）
2. ~~**清單能不能直接寫資料夾？**~~ **結案**（使用者 2026-10-01）：能。`inst` 原樣交給 aos-exec，資料夾或檔都行，只要合 aos-exec 的規則。
3. ~~**所有項都停了，daemon 要不要自己退出？**~~ **結案**（使用者 2026-10-01）：不退出，照樣開著。
4. ~~**一行的格式夠不夠？**~~ **結案**（使用者 2026-10-01）：加**當下時間**（印出那刻），本地時間 ISO 8601 帶時區，例如 `2026-10-01T15:04:05+08:00 id=a exit=0 ms=812`。沒有開始那一行。（同日再改：`id=` 換成 `inst=`，見開頭 10-01 追加裁定）
5. ~~**inst 的 stderr 要不要 daemon 幫忙接？**~~ **結案**（使用者 2026-10-01）：daemon 接的是 **aos-exec 子程序的 fd 2**；inst 裡任務自己的串流照 inst 規則，不歸 daemon（仍不帶 `--stderr`）。設定檔頂層可選 `exec_err_path`（例如 `"<inst>/err.log"`；相對以起點為準；`<inst>` 換成 inst 字面值，指檔時換成它所在的資料夾）；每次接在檔尾、純文字、父資料夾不在就建。沒有 `<inst>`（共用一個檔）或沒寫（接到 daemon 的 stderr）時，每次有內容先加一行標頭（第幾個、inst 字面值、時間）；個別檔可加可不加，實作選一律加（見步驟 2）。多項共用出口不能交錯：收齊再一次寫出。做法見步驟 1、2。

## 做完了沒

**做完了**（2026-10-01，AI 隊）：步驟 1～7 都照上面做了，驗收都寫進 `tests/test_daemon.py`、全過；三項檢查（全部測試、`check_ids.py --strict`、`wf-lint`）都過。等使用者看。

- 程式：`bin/aos-daemon`、`lib/aos_daemon.py`；用法與設定檔例子在 [src/py README](../src/py/README.md#aos-daemon第三段最核心-daemon)。
- 沒照 plan 原字面做的：步驟 3 第一條「1 秒大約 9～10 行」放寬成「會重複」（aos-exec 每次有 Python 起動時間）。
- daemon 退出後，還在跑的 aos-exec 的 stderr pipe 沒人讀了；它之後再寫 stderr 會收到 SIGPIPE。照「默認一切正常」不處理（使用者 2026-10-01 同意）。（同日改預設後：只有設了 `exec_out_path`／`exec_err_path` 的那條是 pipe 才會；沒設的是 `/dev/null`。）
- 10-01 追加裁定（去 id、整份展開指示詞、`modules`）已照改，測試 444 條全過。
- 10-01 再追加（`insts` 改成物件，鍵＝inst 字面值）已照改：`load_config()` 改讀物件、`test_daemon.py` 全部改寫法並加一條鍵順序的檢查（條數不變），測試 444 條全過。
- 10-01 三追加（`exec_out_path`、兩條輸出預設丟掉、標頭加 `stdout`／`stderr`）已照改：`run_once()` 改 `communicate()`、`write_err()` 換成 `write_outputs()`；`test_daemon.py` 原「沒寫就進 daemon stderr」改成 `test_default_discard`（沒寫看不到）＋`test_to_daemon_streams`（寫 `/dev/stdout`、`/dev/stderr` 接回），另加 `test_out_file_per_inst_and_shared`，測試 469 → 471 條全過。
