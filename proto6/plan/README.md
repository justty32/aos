# proto6 實作規劃

← [proto6](../README.md)｜[spec 入口](../spec/README.md)｜[整理區](../spec/settled/README.md)

2026-09-30 起。spec 打磨夠了，開始實作。這份 plan 排順序、講清楚每段要做到什麼、怎麼算做完。

**分工（09-30 晚改）**：先用 Python 把整條 POC 做通，**POC 由 AI 隊寫**，使用者看結果、做裁定；daemon、runner 在 POC 也用 Python。C++11 改寫放到最後一段，那時才由使用者親手寫。

**POC 總原則（使用者 2026-10-01）**：**默認一切正常**——檔案寫得進、讀得懂、沒壞、不斷電、沒有別人同時在跑、任務表是對的、帳號是對的。POC 不為這些異常寫處理，出事就讓它自然丟錯（Python traceback，回 1）。使用者原話：「我們都默認所有東西都OK都正常，先不考慮邊緣狀況」「紀錄這邊，我們都默認紀錄是好的」「舊紀錄不管，我們都默認紀錄能讀得懂」「--firstdo-fsync...先不做吧，我們先做單純的」「別人正在跑？默認沒有別人在跑，這個不管，或是直接報錯。然後也不需要判斷上下層。」「表不合法也拿掉，回 0／1 就好」「帳號不對，也不管」。先不做的 spec 規定不刪，2026-10-01 統一更新時搬到[暫緩區](../spec/settled/deferred/README.md)。

**結束碼慣例（使用者 2026-10-01，同日改版）**：**0＝預料之中**（一切正常都歸 0，含正常中斷；只有 0 是普通結束）；**非 0＝不正常、要額外處理**；**1＝通用錯誤**，沒特別指定碼的錯都回 1；特別指定的碼（例如 inst 的 125／126／127、`aos-exec` 原樣傳出子程式的碼）照各自規定。~~0（正常結束）、1（錯誤結束）、2（正常中斷）~~ 不再有 2。全文與 `aos-tick`、`aos-exec` 怎麼對上，見 [verdicts 11 篇末「aos 結束碼慣例」](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)（已寫入 spec（commit 前由我補號））。

- 程式放 `proto6/src/`，跟探針原型 [proto/](../proto/README.md) 分開。
- 語言：POC 全部用 **Python 3.9**（只用標準庫），daemon、runner 也是；換 C++11 見[第六段](#第六段c11-改寫)。
- inst 的解析與指示詞（`$ref` 等）和 `aos-exec` **直接從 proto5 原樣複製**，放 [proto6/src/py/](../src/py/README.md)：`lib/aos_inst.py`（讀驗解 inst）、`lib/aos_directives.py`（指示詞）、`lib/aos_exec*.py`（開程序）、`bin/aos-exec`。改動只剩「資料夾目標」那一處：先找 `.aos/inst.json` 再找 `inst.json`，而且（2026-10-01）這個 `.aos` 照環境變數 `AOS_DIRNAME`（設成空字串時只找 `inst.json`），用法錯由 2 改 1（結束碼慣例）；~~認得頂層 `user`（跟目前身分不同就 125）~~ 2026-10-01 撤回，回到 proto5 原樣（`user` 當陌生鍵忽略）（跟 aos-tick 共用 `lib/aos_dirname.py`；細節見 [src/py README](../src/py/README.md)）。各段把它當現成的東西用，不重寫。

## 怎麼用這份 plan

1. 一次做一段。每段有自己的細部檔（目前寫了[第一段](m1-tick-core.md)與它之後的 [hooks（外掛掛點）](m1h-hooks-module.md)、[第二段（草稿，等使用者裁定）](m2-system-tasks.md)、[第三段](m3-daemon-core.md)與它之後的[控制模組](m3n-control-module.md)、[五個模組](m3m-daemon-modules.md)，其他段開工前再寫）。
2. 每段拆成幾步，每步都寫：要做到什麼、對哪幾條 spec、**要使用者裁定的點**（沒有就寫無）、驗收。
3. 每段由 AI 隊實作，照驗收那一欄試跑；做完交使用者看。
4. 使用者看結果、裁定該段的待問；裁定後 AI 隊照改。檔案怎麼切、函式叫什麼 AI 隊自己定，標「建議」的只是參考。
5. 碰到 spec 講不清或互相打架的，看該段的「待問」；不在清單上的，記下來問，AI 隊不自己裁。

## 六段總覽

前五段是 Python POC，第六段才換 C++11。

### 第一段：tick 核心

- **目標**：`aos-tick` 直接跑得動一格：照任務表依序跑、每項結束碼紀錄（含 `seq`、停格檔、擋板檔），~~整格回 0／1~~ 照表跑完、擋板、busy 都回 0，tick 自己出錯 1（2026-10-01 結束碼慣例改版）。B-626 原本的核心四件事裡，同資料夾互斥與上下層判定〔使用者方向 2026-10-01：POC 先不做〕。
- **主要 spec**：[B-626、B-602、B-620、B-633、B-627](../spec/settled/tick.md)（B-628 上下層判定已搬[暫緩區](../spec/settled/deferred/tick.md)）；結束碼與 `AOS_DIRNAME` [C-08、C-09](../spec/settled/conventions.md)；格式 [P-202、P-203、P-213](../spec/settled/protocol/tick.md)。
- **可單獨跑的樣子**：不要 daemon、git、cgroup、helper。手建一個資料夾、寫 `.aos/tasks.json`，`aos-tick <資料夾>`（2026-10-01：原 `--node`，再改 `--target`，再改成位置參數） 或 cron 直接跑，看結束碼與 `.aos/tick/current.json`。
- **界線**：核心不認得任何系統級任務，也不清任務留下的後代。細部見 [m1-tick-core.md](m1-tick-core.md)。
- **之後的外掛掛點**：tasks.json 頂層鍵 `hooks`（不是模組；目前只開 `after_all`：照表跑完、含被停格檔停下之後跑一串 inst）見 [m1h-hooks-module.md](m1h-hooks-module.md)〔使用者 2026-10-01 第六批〕。

### 第二段：不靠 daemon 的系統級任務與普通程式

- **目標**：掛在任務表上的 `aos-git open／mark／close`、~~`aos-publish`~~（2026-10-01 第五批搬[暫緩區](../spec/settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)）、`aos-clean`，普通程式 `aos-tick-check-task`（2026-10-01 第五批由 `aos-needs` 改寫），以及 tick 外的 ~~`aos-config-add`~~（2026-10-01 使用者裁定搬[暫緩區](../spec/settled/deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)）、恢復前驗證；兩版標準任務表範本跑得起來。細部（草稿）見 [m2-system-tasks.md](m2-system-tasks.md)。
- **主要 spec**：[B-630、B-622、B-632、B-621、~~B-624（發摘要）~~、B-625、B-629](../spec/settled/tick/git.md)；[B-404](../spec/base/storage.md)；格式 [P-204、P-205、P-210](../spec/settled/protocol/tick.md)（~~P-207~~ 隨 `aos-config-add` 搬暫緩區）。
- **可單獨跑的樣子**：一樣直接跑 `aos-tick`。有 git 的機器上每格最多一個 commit；沒 git 時 `aos-git` 只印 `no_git`、回 0。
- **界線**：全部是「讀寫檔案」就做得完的事，不碰通道。恢復前驗證只寫檢查本身，送 `node.resume` 等第三段。

### 第三段：daemon 核心

> **範圍已砍到最核心**（使用者 2026-10-01）：這段實際只做「一個叫 `aos-exec` 的 cron」——設定檔一份 inst 清單、照週期叫 `aos-exec`、印一行、非 0 可停，不要 socket。下面原本列的登記、叫醒／暫停、runner 收屍、收尾、通道憑證等全部挪到之後。細部 plan 與完成狀態見 [m3-daemon-core.md](m3-daemon-core.md)；spec 正本 [B-640](../spec/settled/daemon/core.md)、格式 [P-120](../spec/settled/protocol/daemon/core.md)。之後的**控制模組**（設定檔寫 `modules.control` 就多開一個 unix socket，收 wake／pause／resume／status，每個只對一項；小工具 `aos-ctl`）**已做**（2026-10-01），見 [m3n-control-module.md](m3n-control-module.md#做完了沒)；spec 正本 [B-641](../spec/settled/daemon/control.md)、格式 [P-121](../spec/settled/protocol/daemon/control.md)。再之後的五個模組見 [m3m-daemon-modules.md](m3m-daemon-modules.md)（2026-10-01 第十一批）：**重讀設定**（`modules.reload`，SIGHUP 重讀，spec [B-642](../spec/settled/daemon/reload.md)）、**記住狀態**（`modules.state: {"$ref": …}`，暫停與已停跨重開，spec [B-643](../spec/settled/daemon/state.md)）**已做**；收屍／cgroup 待裁定；訊息、helper／帳號暫緩；node 模組不做。

- **目標**：`aos daemon` 能登記 node、照週期開格、叫醒／暫停、用 `aos-runner` 開每一格並在格後收屍、重啟與停機收尾、發通道憑證、掛行程與砍掉；沒 cgroup、沒 helper 也跑得起來。
- **主要 spec**：[B-601、B-504](../spec/settled/deferred/daemon/runtime.md)、[B-606、B-607](../spec/settled/deferred/daemon/registration.md)、[B-603、B-604、B-611](../spec/settled/deferred/daemon/lifecycle.md)、[B-610、B-612、B-613](../spec/settled/deferred/daemon/channel.md)、[B-608](../spec/settled/deferred/daemon/reload.md)；格式 [舊 daemon 協議](../spec/settled/deferred/protocol/daemon/README.md)（P-101～119，不含 helper 那幾條）。以上 2026-10-01 都搬到暫緩區。
- **可單獨跑的樣子**：一般帳號開 `aos daemon --config F`，登記第一段做好的 node，看它照週期出格、`node.wake` 叫得醒、Ctrl-C 收得乾淨。
- **界線**：訊息佇列、cgroup 是第四段的部件，這段先當「開關關著」；B-615 的開關鍵這段就要認得。helper 動作回 `helper_unavailable`。

### 第四段：daemon 部件——訊息與 cgroup

- **目標**：B-615 的兩個可掛部件。訊息：`node.send`／`node.take`、急件叫醒，加上 tick 那側的 `aos-mq get`／`post`。cgroup：node 框與上限、格後與重啟清框，加上普通程式 `aos-cg`。
- **主要 spec**：[B-615](../spec/settled/deferred/daemon/components.md)、[B-614](../spec/settled/deferred/daemon/messaging.md)、[B-623、B-624（佇列）、B-634](../spec/settled/tick/mq.md)、[B-605 與各條 cgroup 部分](../spec/settled/deferred/daemon/cgroup.md)；格式 P-119、[P-206、P-211](../spec/settled/protocol/tick.md)。
- **可單獨跑的樣子**：兩個 node 在同一個 daemon 底下互送訊息；`enable_messaging:false` 時 `mq-post` 回 1、檔搬到 `.aos/mq/failed/`。用 `systemd-run --user --scope -p Delegate=yes` 開 daemon 看框；`enable_cgroup:false` 時退回第三段的做法。
- **界線**：每個部件各自可關，關掉時跑的就是第三段的樣子。

### 第五段：helper 與跨帳號

- **目標**：sudo 開 daemon 時 fork 出 root helper、主程式降權；佈建固定動作；普通程式 `aos-as <帳號> -- 原指令` 經 helper 用別的帳號開程序、交鎖 fd；多帳號之間用群組交接檔案。
- **主要 spec**：[B-303](../spec/settled/deferred/helper.md)、[B-609](../spec/settled/deferred/daemon/helper-actions.md)、[B-301、B-302](../spec/base/identity-resources.md)；格式 P-102、P-107、P-108、[P-208、P-212](../spec/settled/protocol/tick.md)。
- **可單獨跑的樣子**：在可丟棄的機器上建兩個測試帳號，sudo 開 daemon，任務包 `aos-as` 以另一個帳號跑，任務裡核對得到同一把鎖。
- **界線**：只做 tick／daemon 基礎用得到的帳號切換；kernel 分配身分額度那一側不在這裡。

### 第六段：C++11 改寫

- **目的**：照 spec 的依賴原則，把 POC 裡該換的換成 C++11——daemon、runner、helper 這類常駐或管程序的部分。spec 本來就寫 Python 3.9 的（tick 核心、系統級任務、CLI 等）留 Python。確切換哪些，開工前對著 spec 再列一次。
- **前提**：前五段 POC 都做通、試跑過，待問都裁定了。
- **分工**：程式由使用者親手寫；AI 隊只規劃、答疑，POC 當對照組。
- 細部等前五段做完再寫。

## 順序上的調整

照原本排的 1→5，只挪了三樣，都是因為 spec 的相依關係：

| 東西 | 原本 | 挪到 | 為什麼 |
|---|---|---|---|
| `aos-mq get`／`post` | 第二段 | 第四段 | 它只走通道；第二段沒有 daemon，寫出來只會「沒通道、回 0」，等於空殼。跟訊息部件一起做才驗得到 |
| `aos-needs`（2026-10-01 改寫成 `aos-tick-check-task`） | 沒排 | 第二段 | 只讀結束碼紀錄，不靠 daemon；也是第一段紀錄格式的第一個使用者 |
| `aos-cg` | 沒排 | 第四段 | 有 cgroup 時要在 daemon 開的 node 框裡才有意義；沒 cgroup 的退回做法可以先寫，但驗不到主路線 |

## 跨段待問

1. **C++ runner 的 inst 解析怎麼辦？** POC 的 runner 是 Python，直接用 `lib/aos_inst.py`，第三段不受影響。到第六段換 C++ 時：spec 說 runner 要「照 inst 執行一次」，包含解指示詞、驗欄位（[inst](../spec/base/inst.md)「路徑、環境與指示詞」）；C++ runner 要自己重寫一套，還是交給 Python 解完再開程序？第六段開工前要定。
2. **清理的正本還在整理區外。** `aos-clean` 照 [B-404](../spec/base/storage.md)，但整理區 README 的疑點表把 B-401、B-402、B-404 列為「還寫著舊保證、下一輪要改」。第二段做 `aos-clean` 前，先確認照哪一版。
3. ~~**daemon 設定的五個開關還沒進 schema。**~~ **結案**（2026-10-01 統一更新）：B-615 的開關已被 [B-640](../spec/settled/daemon/core.md) 的 `modules` 取代；新設定檔的 schema 是 `daemon-core-config`（[P-120](../spec/settled/protocol/daemon/core.md)）。
