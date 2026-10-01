# aos 通用慣例：結束碼、狀態資料夾名、環境變數、設定檔頂層

← [整理區](README.md)｜[名詞](terms.md)｜[通用 tick](tick.md)｜[daemon](daemon/README.md)

這篇放 aos 自己所有程式（`aos-exec`、`aos-tick`、`aos-daemon`、`aos-ctl`，以及之後的系統級任務與普通程式）都要守的三件事（C-08～C-10），加上兩份設定檔頂層 `cwd` 與指示詞展開的對照（C-11）。各程式自己的碼表、旗標寫在各自那條，這裡只講共通的規矩。

依據：[第二十批裁定篇末 2026-10-01 各節](../../notes/verdicts/11-tick-as-unit.md)（結束碼慣例、`AOS_DIRNAME`、第二批的 tasks.json 頂層預設）；現行程式 [proto6/src/py](../../src/py/README.md)。

## C-08．aos 結束碼慣例

**一句話：0＝預料之中，非 0＝出了要處理的事。**

- **0＝預料之中。** 一切正常都歸 0，包括「該停就停」的正常中斷（例如 tick 看到停格檔、上一格還沒跑完、有擋板檔）。只有 0 是普通結束。
- **非 0＝不正常，要有人或程式額外處理。**
- **1＝通用錯誤。** 沒有特別指定碼的錯一律回 1：檔案讀不到、寫不進、格式壞，argv 用法錯（不用 2），程式起不來，其他沒接住的錯。Python 寫的程式沒接住的例外照 Python 預設回 1、traceback 進 stderr；argparse 預設的用法錯碼 2 要改成 1。
- **特別指定的碼照各自規定保留**，都算「非 0」。例如 inst 的 125（自己失敗、那次沒跑）、126（沒執行權）、127（找不到程式）、`aos-exec` 原樣傳出子程式的碼（含被訊號 N 殺的 128+N）。要新增特別指定的碼，寫在那個程式自己的條文裡。
- **沒有「2＝正常中斷」。** 這個說法用過半天就撤了（使用者 2026-10-01 同日改版）。
- **讀別人的結束碼只分 0 與非 0。** 要記下來的地方照實記原碼（例如 tick 的結束碼紀錄），但判斷時不替非 0 的碼分等級。
- **外部程式不懂這套。** 例如 `grep` 回 1 表示「沒找到」。慣例只約束 aos 自己的程式；外部程式要放進任務表又想照 aos 的意思判讀，使用者自己包一層轉碼。

現行各程式的碼（正本在各條）：

| 程式 | 0 | 1 | 其他（特別指定） | 正本 |
|---|---|---|---|---|
| `aos-tick` | 照表跑完、停格檔停下、上一格還沒跑完（`busy`）、有擋板檔（`blocked`）；任務自己回幾都不影響 | 用法錯（含目標給了檔〔使用者 2026-10-01〕）、`AOS_DIRNAME` 不合法、目標不存在或沒有任務表、任務表不合極簡檢查、tick 自用檔出錯 | 無 | [B-620](tick.md)、[P-203](protocol/tick.md) |
| `aos-exec` | 子程式回 0；`-h` | 用法錯（argv、目標不存在、資料夾找不到 inst、`AOS_DIRNAME` 不合法…）；沒接住的例外 | 125 自己失敗、那次沒跑；子程式的碼原樣傳出（126、127、128+N…） | [inst](../base/inst.md) |
| `aos-daemon` | 被 SIGINT／SIGTERM 叫停 | 用法錯、設定錯、設定檔讀不到、指示詞展開錯 | 無 | [B-640](daemon/core.md)、[P-120](protocol/daemon/core.md) |
| `aos-ctl` | 指令成功 | 其他全部（用法錯、連不上、daemon 回錯） | 無 | [B-641](daemon/control.md)、[P-121](protocol/daemon/control.md) |

整理區裡其他還沒實作的程式（系統級任務、`aos-needs`、`aos-git` 等）：用法錯一律 1；條文裡已定的 125、75 這類碼算特別指定的碼，照各條。整理區以外（kernel、agent、LLM、CLI、ops 等篇）還寫著「2＝用法錯」或拿 2 表示「不合法」的地方，這輪沒動，等那幾篇整理時逐條決定改 1 或列為特別指定。

依據：使用者 2026-10-01 原話：「結束碼這塊，我覺得不要2了，只要是正常的，不須多做處理的，通通0，0以外就是需要額外處理的東西。」「只有0才是普通結束，正常中斷也改成0。」「1就是通用錯誤，所以沒特別設置結束碼的錯誤都設1。」「任務出錯，不算在tick的錯誤內」。

**驗收：**`aos-tick` 遇到 busy、擋板、停格檔都回 0，任務回 1 或被殺時 tick 仍回 0；`aos-exec` argv 寫錯回 1、inst 壞回 125、子程式 `exit 7` 回 7；`aos-daemon` 少給 `--config` 回 1。

## C-09．狀態資料夾的名字：`AOS_DIRNAME`

**aos 放自己狀態檔的資料夾叫 `.aos`，這個名字可以用環境變數 `AOS_DIRNAME` 換掉。** aos 所有程式都照它。

| `AOS_DIRNAME` | 狀態資料夾在哪 |
|---|---|
| 沒設 | `<資料夾>/.aos/` |
| 設了但是空字串 | 不用子資料夾，直接用 `<資料夾>/` 本身 |
| 其他值（例如 `state`） | `<資料夾>/state/`：只換名字，位置仍在資料夾裡 |

- 「資料夾」指各程式自己的那個：`aos-tick` 是它的工作資料夾（命令列給的目標認出來的），`aos-exec` 是資料夾目標。
- **要分得出「沒設」和「空字串」**，兩者意思不同。
- **不合法的值**：含 `/`、或剛好是 `.`、`..`。算用法錯，stderr 一行，照 [C-08](#c-08aos-結束碼慣例) 回 1（`aos-exec` 只在資料夾目標時才擋，直接給檔不受影響）。空字串合法。
- **規格裡寫的 `.aos/…` 都是「沒設時」的樣子。** 各篇不再逐處註明；讀的時候自己把 `.aos` 換成 `AOS_DIRNAME` 的值（空字串時去掉這一層）。
- 各程式怎麼用：`aos-tick` 的任務表、鎖檔、擋板檔、停格檔、結束碼紀錄全在這個資料夾下（[B-620](tick.md)）；目標只能是資料夾，任務表只有 `<目標>/<名字>/tasks.json` 一個位置（空字串時是 `<目標>/tasks.json`）〔使用者 2026-10-01 撤回給檔〕。`aos-exec` 資料夾目標先找 `<目標>/<名字>/inst.json` 再找 `<目標>/inst.json`；空字串時只找後者（[inst](../base/inst.md)）。
- **空字串時 git 管整個工作資料夾**〔使用者 2026-10-01：「不用特別弄清單，就全部」〕：這時狀態資料夾就是工作資料夾本身，有 git 時 `aos-git` 提交與還原的範圍是整個工作資料夾，**使用者自己的檔也會被提交、還原**，不另列 aos 自有檔的清單。要保住使用者的檔就別用空字串。正本在 [B-630](tick/git.md)。
- 任務照常繼承這個變數，aos 不另外處理。

依據：使用者 2026-10-01：「aos-exec那邊，我覺得可以加上這個AOS_DIRNAME」「如果AOS_DIRNAME是空的，那就從找.aos/inst.json改成找inst.json。」

**驗收：**`AOS_DIRNAME=st aos-tick /x` 讀 `/x/st/tasks.json`、紀錄寫在 `/x/st/tick/`；`AOS_DIRNAME=` 時讀 `/x/tasks.json`；`AOS_DIRNAME=a/b` 時 `aos-tick`、`aos-exec <資料夾>` 都回 1、stderr 一行。

## C-10．aos 環境變數總表

aos 自己設或讀的環境變數，全部列在這裡。新加變數要補進這張表。命名：整格共用的叫 `AOS_TICK_*`，一格裡某一項專屬的叫 `AOS_TASK_*`，daemon 給的叫 `AOS_DAEMON_*`。

### 現行

| 變數 | 誰設 | 誰讀 | 內容 | 正本 |
|---|---|---|---|---|
| `AOS_DIRNAME` | 使用者（或外層環境） | `aos-tick`、`aos-exec` | 狀態資料夾的名字；三態見 C-09 | [C-09](#c-09狀態資料夾的名字aos_dirname) |
| `AOS_TICK_CWD` | `aos-tick` 給每項任務 | 任務 | 這一格 tick 的工作資料夾的絕對路徑（命令列給的目標資料夾）。任務要讀本格結束碼紀錄，就讀 `$AOS_TICK_CWD/<AOS_DIRNAME>/tick/current.json` | [B-620](tick.md)、[P-203](protocol/tick.md) |
| `AOS_TASK_ID` | `aos-tick` 給每項任務 | 任務 | 這一項在任務表裡的 `id`；沒寫 `id` 時是它在 `tasks` 陣列的位置轉字串 | [B-620](tick.md) |
| `AOS_TASK_INDEX` | `aos-tick` 給每項任務 | 任務 | 這一項在 `tasks` 陣列的位置，從 0 起 | [B-620](tick.md) |
| `AOS_DAEMON_SOCKET` | `aos-daemon`（掛了控制模組時）給每次 `aos-exec` | `aos-ctl` | 控制模組 socket 的絕對路徑 | [B-641](daemon/control.md)、[P-121](protocol/daemon/control.md) |
| `AOS_DAEMON_INST` | 同上 | `aos-ctl`（沒指名時用它） | 這一次跑的是設定檔 `insts` 裡哪一項（inst 字面值） | 同上 |

任務的環境會一路往下傳：daemon 給 `aos-exec` 的，`aos-tick` 與它的任務、再往下一層的 `aos-tick` 的任務都拿得到。所以任何一層跑 `aos-ctl wake`，叫醒的都是 daemon 設定檔裡最上面那一項。

### 暫緩、撤回或已被取代

| 變數 | 狀態 | 說明 |
|---|---|---|
| `AOS_TICK_LOCK_FD` | 暫緩 | 把 tick 的鎖 fd 交給任務核對；現在鎖不傳給任務（[暫緩區 B-602](deferred/tick.md)） |
| `AOS_TICK_FIRSTDO_FSYNC` | 暫緩 | daemon 叫 tick 開格時 fsync；`--firstdo-fsync` 一起暫緩（[暫緩區 B-633](deferred/tick.md)） |
| `AOS_TICK_TOKEN` | 現行控制不使用；舊通道憑證暫緩，未來另定 | 舊設計的通道憑證。現行控制模組連得上 socket 就能用、不驗身分，用不到它（[B-641](daemon/control.md)）；通道與憑證整套跟著舊 daemon 暫緩，不是永久取消（[P-117](deferred/protocol/daemon/channel.md)）〔astra 報告必修 7〕 |
| `AOS_NODE_DIR` | 改名 | 改叫 `AOS_TICK_CWD`（使用者 2026-10-01：node 這個詞留給之後的 node 模組） |
| `AOS_TICK_RECORD` | 撤回 | 本格紀錄的路徑；有 `AOS_TICK_CWD` 就找得到，拿掉（使用者 2026-10-01） |
| `AOS_DAEMON_ID` | 已被取代 | 控制模組草稿用過的名字，改成 `AOS_DAEMON_INST`（daemon 核心沒有 id） |

依據：使用者 2026-10-01：「AOS_NODE_DIR改成AOS_TICK_CWD，也就是aos-tick在跑的時候，他的cwd的絕對路徑。node這個概念目前還沒到出場的時候，那是後續aos-tick的node模組的事情。AOS_TICK_RECORD應該可以拿掉，反正有AOS_TICK_CWD，就從那邊找就好。」；控制模組裁定（`AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST`）。

## C-11．設定檔頂層 `cwd` 與指示詞展開範圍

〔使用者 2026-10-01〕aos 有兩份「頂層放預設、底下一項一項」的設定檔：daemon 設定檔與任務表 `tasks.json`。兩份的頂層 `cwd` 都**不改程式自己的工作目錄**，只是底下各項的起點；指示詞（`$ref`、`$fmt`、`$env`、`$opt`）展開的範圍則不同。這條只放對照，規則正本在各條。

| | daemon 設定檔 | tasks.json |
|---|---|---|
| 頂層 `cwd` 影不影響程式自己 | 不影響 daemon 自己（只設給 `aos-exec` 子程序當起點） | 不影響 tick 自己（tick 永遠在工作資料夾跑；只是任務的預設 cwd） |
| 相對路徑起點 | daemon 啟動時的 cwd | tick 的工作資料夾 |
| 指示詞 | 整份先展開 | 只展開到 `tasks` 這層；每一項內部跑到時才展開 |
| 頂層 `modules` | 可選，一個模組一個鍵；隨整份展開 | 可選，一個模組一個鍵，目前 tick 沒有模組、核心照收不理；只解一層，內部留給模組；不當任務預設 |
| 正本 | [B-640](daemon/core.md)、[P-120](protocol/daemon/core.md) | [B-620](tick.md)、[P-202](protocol/tick.md) |

- tasks.json 頂層能當每一項預設的只有 inst 的七個欄位（`argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`），淺層合併、項自己寫了就整個蓋過。`_metainfo`、`id`、`kind`、`modules` 都不是預設。合併與展開的細節以 B-620、P-202 為準。
- `modules` 在 tasks.json 只解一層的理由：tick 核心不讀它，整份展開只會讓寫壞的模組設定害整格 `bad_table`。

依據：使用者 2026-10-01 原話：「好，就這個。tick執行時後他自己有自己的cwd，這個頂層key cwd不會影響tick自己的cwd，但是其相對路徑由tick的cwd開始算。」「展開指示詞的時候不整份解好，而是只解到tasks。」「daemon config file也是，最頂層cwd不影響daemon自身，相對路徑也是基於daemon的cwd。但是指示詞這塊，daemon config file是全部產開」「tasks.json頂層也應該有modules。」出處：[第二十批裁定篇末「2026-10-01 第二批」](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第二批astra-審查修正tick-層改名拆篇tasksjson-頂層預設已寫入-speccommit-前由我補號)。

**驗收：**daemon 設定檔頂層 `"cwd":"w"` 時 daemon 自己的工作目錄不變、`aos-exec` 在 `w` 跑；tasks.json 頂層 `"cwd":"work"`、某項沒寫 `cwd` 時那項在 `<工作資料夾>/work` 跑，`aos-tick` 自己仍在工作資料夾；tasks.json 頂層 `modules` 是物件時，裡面寫什麼（含解不開的指示詞）照表跑都一樣。
