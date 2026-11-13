# 通用 kernel 框架開工計畫（11-13，階段 0：只出計畫、沒改程式）：圖紙十四步拆成 17 批，今天不動 C++ 能做的是框架本體三批（1a、2、3），其餘卡在別線、C++ 或待裁題

← [2026-11-13](README.md)｜圖紙：[kernel-framework](../12/kernel-framework/README.md)（[05 施工步驟](../12/kernel-framework/05-施工步驟.md)）｜[kernel-small-fixes](../12/kernel-small-fixes.md)｜[kernel-as-bridge](../12/kernel-as-bridge/README.md)（[06 手與門](../12/kernel-as-bridge/06-細聊-手與門.md)）

> 狀態：線己隊長（fable）寫的施工計畫。等調度者回覆領地與開工許可才進階段 1。這份沒有新的設計決定，批次與檔案清單都照圖紙；跟圖紙不同的只有「為了不碰跑著的樹與別線」而拆開、延後的幾處，各自標明。

## 使用者原話（11-13 上午，逐字）

> 「kernel框架現在就可以開工了。只是說我們現在只有eca能用。」

前情：11-12 收工前「kernel先這樣就好，開工等假日。我自己也要思考一下」。

### 使用者 11-13 看完架構圖後（逐字；結果在第十三節）

> 「kernel架構圖我看過了，我覺得都不錯。但有一個問題：next只能一個嗎？」

調度者答：現在 `next` 只能一個（一個信箱路徑字串，放行的信全轉給那一站）；可以串成鏈，沒有內建分岔；「多個」有三種意思——照規則分流（一封信只去一處）、備援、同時寄多站。

> 「按照規則分流吧。就用hook」

### 使用者 11-13 在待裁頁的裁定（逐字；題目與選項在 [decide_20261113_wu-top.json](decide_20261113_wu-top.json)，用 id 查）

- `kf-K-F47:A`——問腦總機用 Python 重寫成 `lib/aos/kernel_llm`、刪 C++ 的 `impls/aos-llm-kernel`。
- `kf-K-F50:B*（備註：可以用unset吧。kernel.json的next感覺有點畫蛇添足。）`——選的是「照條文 N-63：總機照舊看 `AOS_KERNEL`」，翻掉圖紙代定 K-F50。
- `kb-ctl:A*`——照現況：`aos-daemon-ctl` 是人直接敲板子的保底，「唯一的門」只約束 proc。
- `t2d-U4:A*`——條文改成現在式「打包＝收工硬凍；軟凍沒做」，kernel 打包算遠期。
- `mv-q2:C*（備註：這只是用來參考的概念。）`——通用與主觀兩句都留、不二選一。

對這條線的影響：

- K-F47 已准，但調度者代定不變：這週不開問腦那一包、不停樹，今天範圍照舊。
- K-F50 翻成 B：問腦那包（批 9）的掛信照舊看 `AOS_KERNEL`、問腦的 `kernel.json` 不加 `next`；N-63 那句不用改（批 12 少一項）。避開「總機繼承到給一般 proc 的 `AOS_KERNEL`」那個坑的辦法，照他的備註是起 llm daemon 的殼 `unset AOS_KERNEL`。
- 備註那句「kernel.json的next感覺有點畫蛇添足」有沒有連框架站的 `next` 一起講——**已結案**。調度者把兩種讀法連同「11-11 你選過寫進設定檔」拿去問，使用者 11-13 回（逐字）：

  > 「Hmmm，好啦，next也可以。只是說，我會覺得AOS_KERNEL他就是在有需要掛一個aos proc的時候，就使用的一個目標，一個通用的，基礎的目標。好比所有C語言程式使用syscall的時候，只要沒有特別指定，不然就是走linux kernel那個記憶體位置。啊如果有需要其他目標...那就自己找方法指定」

  決定：框架站設定檔的 `next` 留著，批 2 的做法已確認、不再是代定。他後半段講的是 `AOS_KERNEL` 的定位：要掛 aos proc 時、沒特別指定就用的通用基礎目標；要別的目標就自己另外指定（`next` 是其中一種指定法）。
- **`kf-next` 裁定（11-13 第二輪待裁頁 `wu-1113-r2`）＝選 B：框架站沒寫 `next` 時改成三段——先看 `next`，沒有就看 `AOS_KERNEL`，再沒有才 `AOS_DAEMON`；哪一個指到自己就跳過。** 使用者回覆原文：「kf-next:B*（備註：如果覺得麻煩，那就直接報錯算了）」（這題來源檔沒有建議，`*` 只是頁面記號；回覆整行見[回覆檔](decide_20261113_wu-r2.reply.txt)，備註的讀法與待施工見[裁定落地-1113 § 第二輪](裁定落地-1113.md#第二輪wu-1113-r2裁定後待施工)）。還沒施工。
- kb-ctl 選 A：跟圖紙 K-F34 一致，不用改。t2d-U4、mv-q2 不碰這條線的程式。

## 一、現況盤點（唯讀查到的，影響排法）

- 兩條前提線（kernel 小修、條文）都已在 main（小修 commit `c10175bac`；N-42 已寫「收進同一份框架」）。
- 跑著的樹（`~/aos-home`，另有 `~/code/six-try-1113`）：
  - `env.sh` 有 `unset AOS_DAEMON AOS_KERNEL AOS_CLOCK`——**整棵樹沒設 `AOS_KERNEL`、沒用判官、沒有問腦總機**（只有知識庫文字提到）。
  - `~/.local/bin/aos-*` 是連到 repo 的捷徑：`cmd/*`、`py/*`、被 cmd import 的 `lib/agent/*.py`（例：`aos-mcp`、`aos-agent`、`aos-eca-turn` import 的 `hooks.py`）**存檔即生效**。
  - `~/aos-home/lib/` 是 **08:31 複製的一份**（不是捷徑；跟 repo 比只有線乙改的 do_task 不同）：腦叫的工具（`fork`、`subagent`、`hook_fire`…）跑的是那份複本，**repo 的 `lib/aos/*`、`lib/agent/<工具夾>/` 改了不會馬上生效，下次重拷才會**。反過來說：repo 的 `aos-agent` 改了、樹裡舊版 `fork`／`subagent` 還在叫它——`aos-agent` 對外的樣子（`ctl who --json` 的 `daemon` 欄、`--daemon` 旗標）在這條線裡不能拿掉（圖紙本來就留著）。
- C++ 的 `impls/aos-llm-kernel/bin/aos-llm-kernel` 已建好，可當問腦那包的對照組，不用重 build。

## 二、施工批次表

圖紙十四步照號；為了「新碼放新檔、最後才接線」把步 1、7、11 各拆兩半，共 17 批。「工時」是圖紙估的人時。測試都是各夾既有的 `python3 -m unittest`；新增的例照圖紙 05 那一格逐條寫，下表只點名檔。

| 批 | 做什麼 | 既有檔（要改／搬） | 新檔 | 怎麼驗 | 先做完 |
|---|---|---|---|---|---|
| **1a** | hook 共用引擎抽成新檔（驗格、排序、比 condition、寫 event.json、跑 handler、解回話、on_error；事件表由呼叫的人給）。**`hooks.py` 這批不動** | — | `proto8/lib/hook_run.py`、`proto8/lib/tests/test_hook_run.py` | 新測試：照 `lib/agent/hooks.py` 現有行為逐項（格的形狀、退 0／10／其他、逾時、async、intercept false、on_error 兩種、多 hook 照名字排） | — |
| **1b** | `lib/agent/hooks.py` 改用 `hook_run`，行為不變 | `proto8/lib/agent/hooks.py` | — | `lib/agent/self_hook/tests`、`templates/tests/agent-fsm`（92 例）、`cmd/aos-agent/tests/test_hook.py`、`cmd/aos-eca/tests/test_hooks.py`、`lib/agent/tests/test_cli_hook_follow.py`、`extras/gitignore-check/check.py`；改前改後手跑對照 | 1a；**排在 a2a 線與修 bug 線之後**（見四、五） |
| **2** | 判官 → 框架站：骨架 `round()`＋掛 proc 那包五個口、鎖、設定過 aos-directive、相對路徑轉絕對、`next`、`count_daemon`、`reply_via_me`（`forwarded.json`、先防重再代回）；範本與 extras 引用同一個 commit 換完 | 搬＋改：`proto8/lib/aos/judge/_entry`、`_metainfo.json`、`_tooldef.json`、`tests/test_judge.py` → `proto8/lib/aos/kernel/…`（`tests/test_kernel.py`）；`proto8/kernel/daemon-judge/{_entry,daemon.json,judge.json,.env}` → `proto8/kernel/daemon-kernel/{…,kernel.json}`；`proto8/kernel/procs-kernel/loop.json`、`judge.json`→`kernel.json`；`proto8/extras/gitignore-check/check.py`；`proto8/lib/directive_value.py`（只註解）；`proto8/kernel/docs/03-feat-proto.md`（件 4 的夾名與前綴字樣） | `proto8/lib/aos/kernel/round.py`、`letters.py`、`procs_rules.py`、`queue_fifo.py`、`README.md` | `lib/aos/kernel/tests/test_kernel.py`：原判官 142 行測試改名全過＋圖紙 05 步 2 列的 10 個新例；`extras/gitignore-check/check.py` 整棵過；`rg 'aos/judge\|judge\.json\|judge_replies\|judge_ordered'` 在 `proto8/lib`、`kernel/daemon-kernel`、`kernel/procs-kernel`、`extras` 0 命中 | —（可跟 1a 並行） |
| **3** | hook 三時機接上骨架（`before_verdict`、`after_verdict`、`before_reply`；`bodies/`） | `proto8/lib/aos/kernel/round.py`、`letters.py`、`queue_fifo.py`、`_entry`、`README.md`、`tests/test_kernel.py`（批 2 產出的） | `proto8/lib/aos/kernel/tests/test_kernel_hooks.py` | 圖紙 05 步 3 列的 11 個例 | 1a、2 |
| **7a** | 整棵鏈劇本（假腦），先做不靠查詢信的五段：1、2、4、5、6；agent 同時設 `AOS_KERNEL` 與 `AOS_DAEMON` | — | `proto8/extras/kernel-chain-check/check.py`、`README.md` | 五段都過（暫存夾起真樹，不碰 `~/aos-home`） | 2、3 |
| **11a** | 文件與條文加註（框架站部分）：`kernel/README`、`kernel/docs/02` 重寫成「框架站＋擺法」；舊名換新名；N-42 (2)、C-47 的「未實作」加註成已實作 | `proto8/kernel/README.md`、`kernel/docs/02-kernel-modes.md`、`docs/NORMS/09-kernel.md`、`docs/CONCEPTS/04-kernel.md`、`docs/CONCEPTS/01-設計理念/02-C-51.md`、`docs/NORMS/附錄4-持久檔.json`（11 處）與 `.md`、`lib/docs/02-索引-base與索引-aos.md`、`impls/docs/01-現況與地圖與依賴.md`、`impls/aos-daemon/docs/06*`、`templates/README.md`、`proto8/README.md`、`knowledge/aos/kernel.json` | — | `wf-lint` 綠（broken 不增）；`codemap_gen.py --apply` 0 stale；文件裡的指令逐條手跑；`rg 'aos/judge\|judge\.json'` 全 `proto8/`（不含 thinking、`templates/judge-llm`）0 命中 | 2、3 |
| **4** | aos-daemon 認查詢信 `procs_state_path` | `proto8/impls/aos-daemon/src/daemon/mailbox.cpp`（可能含 `daemon.hpp`）、`impls/aos-daemon/docs/05*`、`README.md` | `proto8/impls/aos-daemon/tests/test_state_path.py` | 圖紙 05 步 4 三個例 | —；**改 C++、要重 build → 等能停樹** |
| **5** | `py/daemon_ctl` 加 `state_path()`、讀表吃檔路徑、相對路徑照表檔所在夾解；`aos-agent` 查表先問再讀、寄信的有 `AOS_KERNEL` 只看回信；人殼的回信信箱；`KernelFailed` | `proto8/py/daemon_ctl/table.py`、`post.py`、`__init__.py`；`proto8/cmd/aos-agent/aos_agent/common.py`、`ctl/shared.py`、`ctl/{who,ls,state,where,add,rm,phase}.py`；`cmd/aos-agent/README.md`、`docs/` 對應頁 | `proto8/cmd/aos-agent/tests/test_kernel_state_path.py`、`proto8/py/tests/test_state_path.py` | 圖紙 05 步 5 的五個例。**不靠批 4 也能驗**：測試裡用一支會答查詢信的假 kernel；接真 daemon 的那一例等批 4 | 程式上不卡批 4；**跟修 bug 線撞檔 → 排它之後** |
| **6** | `fork`、`subagent` 以自己那列 `stack` 為基準、不帶 `--daemon`、`subagents.json` 存絕對路徑；`on_clock` 經 `aos-agent ctl ls --json` 找鐘 | `proto8/lib/agent/fork/_entry`、`fork/tests/test_fork.py`、`fork/README.md`；`lib/agent/subagent/_entry`、`subagent/tests/test_{subagent,daemon}.py`；`lib/agent/hooks.py`（`_clock_file` 一帶）；`lib/agent/{agents_ctl,self_*,goal,clock_register,mailbox_send}/_tooldef.json`（只補 env 說明） | — | 圖紙 05 步 6：只設 `AOS_KERNEL` 也能掛子與分身、`on_clock` 解得到鐘 | 5、1b；**改持久格式（`subagents.json`），見四** |
| **7b** | 鏈劇本補第 3 段（`ctl ls` 走查詢信、拿到刪減表）與「只設 `AOS_KERNEL`」 | `proto8/extras/kernel-chain-check/check.py` | — | 六段都過 | 4、5、6 |
| **11b** | 文件與條文（查詢信部分）：N-63 02「`ctl who` 只查表」改先問再讀、N-28 與附錄 4 的「壞信不回」、`cmd/aos-agent` 文件、知識庫 | `proto8/docs/NORMS/` 的 N-63、N-28 所在分檔、`附錄4-持久檔.*`、`knowledge/aos/cli/daemon.json`、`knowledge/aos/kernel.json`、`cmd/docs/03*` | — | 同 11a | 4～6 |
| **8** | 「自己跑」零件 `runner.py`（掛 proc、收成品、逾時、重掛一次） | `proto8/lib/aos/kernel/README.md` | `proto8/lib/aos/kernel/runner.py`、`tests/test_runner.py` | 圖紙 05 步 8 的七個例（真 daemon＋假端點函數，暫存夾） | 2；**只有問腦那包用它 → 跟著 K-F47 走** |
| **9** | 問腦專屬那一包 | — | `proto8/lib/aos/kernel_llm/{_entry,packs.py,order.py,slots.py,budget.py,ledger.py,_metainfo.json,_tooldef.json,README.md}`、`tests/`（從 `impls/aos-llm-kernel/tests` 複製 5 支改指新程式） | 5 支黑箱測試全過；跟 C++ 那支對同一批假信逐欄比；hook 三時機各一例 | 3、8；**卡 K-F47** |
| **10** | 切換與刪 C++ | `proto8/kernel/llm-kernel/daemon.json`、`kernel/llm-team/daemon.json`；`impls/aos-llm-kernel/`（整夾刪）；`impls/aos-llm/`（收標頭 `aos/llm_kernel.hpp`）；`impls/CMakeLists.txt`；`proto8/install.sh` | — | 圖紙 05 步 10 四件假腦整棵＋量 200 封 | 9；**動 C++、重 build、重跑 install → 等能停樹；卡 K-F47** |
| **12** | 問腦部分的條文與文件（圖紙 04 末尾清單） | N-42、C-47、N-63 01、C-52 續、`kernel/docs/01-llm-kernel.md`、`impls/aos-llm-kernel` 的 README 與 docs（搬）、`impls/docs/*` | — | `wf-lint` 綠 | 10；**卡 K-F47、K-F50** |
| **13** | 公司真腦各驗一題：eca claude haiku、codex gpt-6-luna 各一隻，`AOS_KERNEL` 指框架站，生一個 subagent、第二個排隊 | — | —（暫存樹，結果寫回本檔） | 掛信經框架站、表上多一列、排隊出隊、腦沒收到報錯 | 7a（兩個變數都設的版本）；只設 `AOS_KERNEL` 的版本等 7b |
| **14** | 回家驗問腦與試驗場（真端點、LM Studio、fsm 真腦、試驗場換身體） | 試驗場（repo 外） | — | 圖紙 05 步 14 | 10、13；**要回家** |

相依一句話：框架線 1a→2→3→7a→11a；查詢信線 4→5→6→7b→11b（5 可先於 4 用假 kernel 驗）；問腦線 8→9→10→12→14；1b 獨立、只是去重。

## 三、哪些批不靠待裁題、哪些卡住

| 待裁題 | 卡到哪幾批 | 照圖紙推薦／現況代定往下走，之後翻案要重做多少 |
|---|---|---|
| K-F47 問腦怎麼收（推薦 Python 重寫、刪 C++） | 8、9、10、12、14 | 翻成「C++ 留著」：批 8、9 整包白做（圖紙估 24 人時），批 10 不做；框架線與查詢信線一行不用改 |
| K-F50 總機掛信只看 `next`（N-63 衝突） | 9 裡一小段、12 一句條文 | 翻成「照條文看 `AOS_KERNEL`」：改去處那一個函數＋一個測試＋條文一句，一小時內 |
| bridge 題 1「上一層是硬體」嚴到哪 | 沒有 | 三個選項都不改框架零件；選 ③「全部經上一層」才會多出新零件，那是加做、不是重做 |
| bridge 題 3 要不要重畫圖紙 | 沒有 | 題 2 已結（名字都不改），重畫的唯一理由（選乙改名）已不存在；除非使用者要把「問硬體規格的信」加進框架，那也是加做 |
| `aos-daemon-ctl` 直寄 daemon、不經門的出入 | 沒有 | 圖紙 K-F34 照現況（直寄）；若改成要經門，只改 `aos-daemon-ctl` 與 `py/daemon_ctl/post.py` 的寄法，框架站不用動 |

**不靠任何待裁題就能做的**：1a、1b、2、3、4、5、6、7a、7b、11a、11b、13（通用站＋查詢信兩條線全部）。

**建議今天做到**：1a、2、3 三批（各一個 commit）；時間夠再做 7a 與 11a。停在這裡的理由：這幾批只動「樹裡沒人用的判官夾」與新檔，不動 C++、不撞別線、存檔不影響跑著的 agent。批 1b、5、6 要等別線讓出檔；批 4、10 要等能停樹；批 8、9 等 K-F47（見六的新題）。

## 四、領地清單

**這條線要獨佔寫入的（今天）**

- `proto8/lib/hook_run.py`、`proto8/lib/tests/test_hook_run.py`（新）
- `proto8/lib/aos/judge/`（搬走）→ `proto8/lib/aos/kernel/`（整夾）
- `proto8/kernel/daemon-judge/`（搬走）→ `proto8/kernel/daemon-kernel/`；`proto8/kernel/procs-kernel/`
- `proto8/extras/gitignore-check/check.py`、`proto8/extras/kernel-chain-check/`（新）
- `proto8/lib/directive_value.py`（只改一行註解）
- `proto8/kernel/README.md`、`proto8/kernel/docs/02-kernel-modes.md`、`kernel/docs/03-feat-proto.md`
- 批 11a 列的條文與文件（`docs/NORMS/09-kernel.md`、`docs/CONCEPTS/04-kernel.md`、`docs/CONCEPTS/01-設計理念/02-C-51.md`、`docs/NORMS/附錄4-持久檔.*`、`lib/docs/02-索引-*.md`、`impls/docs/01-*.md`、`impls/aos-daemon/docs/06*`、`templates/README.md`、`proto8/README.md`、`knowledge/aos/kernel.json`）
- `proto8/thinking/2026-11/13/kernel-framework-開工.md`（本檔，之後記實作結果與代定）

**之後才要、今天先保留不寫的**：`proto8/lib/aos/kernel_llm/`（新）、`proto8/impls/aos-daemon/`（批 4）、`proto8/impls/aos-llm-kernel/`、`impls/aos-llm/`、`impls/CMakeLists.txt`、`proto8/install.sh`、`proto8/kernel/llm-kernel/`、`kernel/llm-team/`（批 10）。

**跟別線撞的，逐一點名**

| 檔 | 我的哪批 | 撞誰 | 建議先後 |
|---|---|---|---|
| `proto8/lib/agent/hooks.py` | 1b（整檔換引擎）、6（`on_clock` 找鐘） | 沒有同檔的線，但線乙的 `templates/agent-fsm/cell_common.py` 叫 `hooks.clock_tick`、a2a 線的 `aos_eca/turn.py` 經 `aos_eca/hook.py` 叫 `hooks.fire`——對外函數名與行為不能變 | 線乙收尾、a2a 線進 main 之後才做 1b；不在同一時段改 |
| `proto8/py/daemon_ctl/post.py`、`table.py` | 5 | 修 bug 線（`aos-agent ctl` 的 rm／rename／set-def 走 `py/daemon_ctl/ctl.py`、`post.py`） | 修 bug 線先；它進 main 後我再開批 5 |
| `proto8/cmd/aos-agent/aos_agent/ctl/{rm,shared,phase,…}.py`、`common.py` | 5 | 修 bug 線（同上） | 同上 |
| `proto8/lib/agent/subagent/`、`fork/` | 6 | 目前三條線都沒列；`agent_def` 是修 bug 線的，不同夾 | 無撞，但排在批 5 後 |
| `proto8/templates/agent-fsm/wait.py` | 不動（圖紙：不改） | 線乙 | 無 |
| `proto8/knowledge/aos/` | 11a（`kernel.json`）、11b（`cli/daemon.json`） | 線乙動過 `knowledge aos/definition` | 不同檔；線乙收尾後再寫 |
| `wf/workflows/common/code-map/proto8/` 生成冊 | 每批 commit 前重生 | **所有線** | 生成器掃整棵工作樹，會把別線還沒 commit 的新檔一起寫進去。請調度者定：各線 commit 排隊、一次一隊跑 `codemap_gen.py --apply`＋commit；我這邊 `git add` 只點名自己的檔與生成冊 |
| `wf/SESSION-LOG.md`、`wf/WAIT_USER.md`、日誌、`thinking/2026-11/13/README.md` 日索引 | 收批時要各一行 | 調度者保留 | 我只回報要寫的那句，由調度者寫（或授權我追加自己那一行） |

## 五、對跑著的樹的影響

| 批 | 存檔即生效嗎 | 會不會讓跑著的 agent 壞 | 怎麼避 |
|---|---|---|---|
| 1a | 新檔，沒人 import | 不會 | — |
| 2、3、7a | repo 的 `lib/aos/judge`→`kernel`；樹用的是自己那份複本、而且沒人用判官 | 不會 | 改名是整夾搬，樹裡舊複本不受影響 |
| 11a | 文件；`knowledge/` 樹裡也是複本 | 不會 | — |
| **1b** | **是**：`aos-mcp`（每次工具呼叫的 before／after_tool）、`aos-agent hook`、`aos-eca-turn` 都 import repo 的 `hooks.py` | 寫錯＝跑著的 eca agent 每次叫工具都出錯 | 先在 scratchpad 的整份 `proto8` 複本上改、跑完上面那幾夾測試，再用一次原子換檔（寫暫存檔＋rename）落到 repo；或乾脆留到能停樹時。**今天不做** |
| **5** | **是**：`aos-agent`、`aos-daemon-ctl`、`aos-eca-screen` 都用 repo 的 `py/daemon_ctl` | 樹沒設 `AOS_KERNEL`，新路不會走到；風險在「讀表改吃檔路徑」這段共用碼 | 新函數 `state_path()` 先加、舊路徑不動；「沒設 `AOS_KERNEL`」那條路改前改後手跑對照；`who --json` 的 `daemon` 欄與 `--daemon` 旗標照留（樹裡舊複本的 fork／subagent 還在用） |
| **6** | 不是馬上（樹用複本）；**下次重拷 lib 時生效** | `subagents.json` 改存絕對路徑、舊帳不認：重拷那一刻有子 agent 在跑的 agent 會對不上帳 | **要重建什麼**：重拷前先收掉子 agent，或刪掉各 agent stack 裡的 `subagents.json`。這一步要跟使用者約時間（能停樹時） |
| **4** | 重 build 會換掉 `impls/aos-daemon/bin/aos-daemon`（捷徑指到它）；跑著的 daemon 還是舊的，重起才換 | 今天規矩不動 C++ | **等能停樹**。不動持久格式，不用重建 |
| **10** | 刪 `aos-llm-kernel`、重跑 install | 樹裡沒有總機，不會壞；但要重 build、重跑 install | **等能停樹** |
| 8、9 | 新檔新夾 | 不會 | — |
| 13 | 另起暫存樹（不在 `~/aos-home`），會多兩個 eca CLI 行程 | 不碰使用者的樹；吃 CLI 名額與 haiku／codex 額度 | 挑使用者說不忙時跑 |

**今天不動 C++ 也能先做的**：1a、2、3、7a、11a（建議做）；1b、5、6、8、9（做得了，但各有上面寫的理由要晚一點）。
**一定要等能停樹的**：4（daemon 加一種信、重 build）、6 的上線（重拷 lib＋清舊帳）、10（刪 C++、install）、7b 與 13 的「只設 `AOS_KERNEL`」版本（靠 4）。

## 六、「我們現在只有eca能用」怎麼讀

三種讀法，前兩種對今天的排法結果相同，差別在問腦那包現在開不開工：

| 讀法 | 意思 | 對計畫的影響 |
|---|---|---|
| 甲（調度者的讀法） | 這台真腦只有 eca 身，樹裡沒有問腦總機；真腦驗證只能靠 eca，fsm 只能假腦 | 跟圖紙 05「公司與回家的分界」一樣，什麼都不用改：批 13 用 eca，問腦那包（8、9）用假腦照做、真端點回家驗 |
| 乙 | 現在用得到框架的只有 eca agent，所以先做 eca 用得到的（通用站＋查詢信：掛子、排隊、只設 `AOS_KERNEL`），問腦那包（35 人時、這台只能假腦驗、使用者用不到）先放著 | 順序同甲，但 8、9、10、12 這週不開，K-F47、K-F50 也就不急著裁 |
| 丙 | 提醒：他正在用 eca agent 做公司工作，別把 eca 這條路弄壞 | 就是第五節的做法（今天只動沒人用的夾與新檔；1b、5 這種存檔即生效的要另約）；不改順序 |

我沒有選邊：建議的今天範圍（1a、2、3）在三種讀法下都對。甲與乙的差別留給使用者（下面新題 1）。

## 七、隊伍打算

- 隊長：fable（我）——寫任務書、審 diff、跑測試、一批一個 commit；不親手寫程式。
- 隊員 A：**codex `gpt-6.1-sol` 一個**（`-s workspace-write`、`/goal` 開頭、明帶 `-m`）——照圖紙施工，依序做 2 → 3（同一夾、不能並行）。任務書附圖紙 01、02 的對應段與「對應判官哪幾行」；點名要寫的測試就是上表那幾支，其餘不寫。它不做設計：圖紙沒寫到的地方停下來回報，由我照原則代定記在本檔。
- 隊員 B：**opus subagent 一個**——批 1a（從 `hooks.py` 抽引擎，要讀懂現有行為，算程式邏輯）；之後審 codex 的 diff 找「跟圖紙不符」、寫 11a 的條文加註與 `kernel/README`、`docs/02`（條文是使用者的，不給 sonnet／gpt 改）。
- 雜活：sonnet subagent 視需要（跑 `rg` 盤點、`codemap_gen.py --apply`、`wf-lint`、手跑文件裡的指令）。
- CLI 行程數：全機「使用者在做事」上限 3 個、另外還有三條線——我這線只要 **1 個 codex 名額**；拿不到名額就改由 opus subagent 施工（不佔 CLI）。測試（會起暫存 daemon）一律由隊長在沙箱外跑、一次一支，不跟別線的全套測試重疊。
- 7a 交 codex（照 `gitignore-check` 的寫法仿）；13 由隊長看著跑。

## 八、要使用者裁的新題（原則與圖紙推不出的）

**新題 1：問腦那一包現在要不要開工？**（就是「只有eca能用」讀法甲、乙的差別，也等於 K-F47 現在答不答）

| 選項 | 後果 |
|---|---|
| A 先不做，這週只做通用站與查詢信（eca 用得到的） | 問腦總機照舊是 C++ 那支，暫時沒有 hook；K-F47、K-F50 可以慢慢想；骨架先只有判官那一包在用 |
| B 照圖紙現在就用假腦做（Python 重寫），真腦回家再驗 | 公司這邊多花約 24 人時的施工額度；之後若 K-F47 翻成「C++ 留著」，這 24 人時白做 |

建議 A：這台驗不到真端點，使用者現在也用不到；等通用站在 eca 上跑順了、K-F47 答了再開。

**新題 1 裁定（11-13）＝選 B：現在就用假腦做（Python 重寫），真腦回家再驗**（跟建議 A、頂層代定「不開」不同）。使用者回覆原文：「kf-n1:B*」（第二輪待裁頁 `wu-1113-r2`，出處同上面 `kf-next` 那行）。還沒施工。

**新題 2：什麼時候可以停樹一次？**（不是設計題，是約時間）

批 4（aos-daemon 加「狀態在哪」這種信）要改 C++、重 build；批 6 上線要重拷 `~/aos-home/lib` 並清掉 `subagents.json` 舊帳。沒做這兩件，「只設 `AOS_KERNEL`、不設 `AOS_DAEMON`」就還是 `DaemonMissing`。

| 選項 | 後果 |
|---|---|
| A 今天收工前或明天開工前停一次 | 查詢信整條線這兩天就能通，SESSION-LOG 那句「只設 `AOS_KERNEL` 仍 `DaemonMissing`」可以消掉 |
| B 等假日回家再做 | 公司這邊先只有框架站（要兩個變數都設才能用）；程式（批 5、6）可以先寫好、用假 kernel 驗，接真 daemon 的那一步留到假日 |

建議 B 起步、隨時可改 A：批 5 本來就要等修 bug 線，今天排不到。

**新題 2 裁定（11-13）＝選 A：今天收工前或明天開工前停一次**（跟建議 B、頂層代定「等假日」不同）。使用者回覆原文：「kf-n2:A*（備註：寄信給eca_main，跟他約時間。）」（出處同上）。還沒做（信還沒寄）。

圖紙原有的待裁（K-F47、K-F50、bridge 題 1、題 3、`aos-daemon-ctl` 的出入）照舊在待裁頁上，這裡不重問；它們卡到哪見第三節。

## 九、施工中的代定（可翻案）

1. （已結案，不再是代定）K-F50 備註有沒有連框架站的 `next` 一起講：使用者 11-13「好啦，next也可以。」——`next` 留著，原話在開頭「使用者原話」段。
2. **骨架與包的介面（隊長定，圖紙只說「五個口」）**：`round.run(pack, cfg_path, name="kernel")`；包提供 `collect(ctx, before_reply=None)`、`check(ctx)`、`order(ctx, letters)`、`admit(ctx, name, letter)`、`dispatch(ctx, name, letter, detail)` 五個口，另加 `load(cfg, cfg_dir)`（驗自己的鍵）、`refuse(…)`（拒信形狀歸包）、`finish(ctx, queued)`（寫窗）；判決字串 `pass`／`refuse`／`queue`。
3. **空輪不讀 daemon 的表（照原判官的行為保留）**：所以「從 `AOS_DAEMON` 算出來的轉寄目標就是自己」這種設定錯，要等有信那一輪才報 `CfgBad`；明寫 `next` 指到自己的每輪都報。

## 十、實作結果

### 批 1a（747c48ca9）

`lib/hook_run.py`＋`lib/tests/test_hook_run.py`（10 例）。`lib/agent/hooks.py` 沒動。留給批 1b：改用引擎後「一格兩個錯時先報哪句」會變（on_clock 專用鍵的檢查排到共通鍵之後）；收行程群那段沒用 `process_group.stop`（不等價）。

### 批 2

`lib/aos/judge` → `lib/aos/kernel`：`_entry`（薄殼）、`round.py`（骨架）、`letters.py`、`procs_rules.py`、`queue_fifo.py`、`README.md`；範本 `kernel/daemon-judge` → `kernel/daemon-kernel`，兩份 `judge.json` → `kernel.json`；`extras/gitignore-check/check.py`、`lib/directive_value.py` 註解、`kernel/docs/03-feat-proto.md` 件 4 跟著換。新鍵 `next`、`count_daemon`、`reply_via_me`；代回失敗改成 warning 收掉不重試；鎖 `requests/.flock`（`LockFailed`）。

- 測試：`lib/aos/kernel/tests/test_kernel.py` 原 6 例＋新 10 例全過。
- `extras/gitignore-check/check.py` 整棵：33 項過、2 項紅——紅的是「追蹤檔含敏感字樣」掃到 `templates/eca-claude/README.md` 裡 `eca-task-subagent` 連結的 `sk-` 三個字（該檔 11-12 的 commit 就有、這批沒碰），跟框架站無關；帶框架站的那幾項（掛 proc 經站、在飛的請求留著、收工不留行程）都過。
- **要重建什麼**：正在跑的判官重起前刪掉 stack 裡的 `judge_replies/`、`judge_ordered.json`（新程式不認）；定義夾裡的 `judge.json` 改名 `kernel.json`、`daemon.json`／`loop.json` 的 `exec` 改指 `lib/aos/kernel`。`queue.json`、`requests/` 不用動。公司這台的樹沒有判官，不用做。
- 已知限制（照舊或同類）：轉寄寄出、對照還沒寫進 `forwarded.json` 就被砍的那一瞬間，重起後原信會被當成已轉寄收掉，但回信回來查不到對照、被丟掉（寄件人靠自己的逾時）。

### 批 3

`lib/aos/kernel/hooks.py`（三個事件的事件表、設定、判決回話；執行全交給 `lib/hook_run.py`）接上骨架：`before_verdict`（新信一次、可改 body、退 10 直接拒且不跑規則與 `after_verdict`）、`after_verdict`（新信判完一次、離開隊再一次；可改判 pass／refuse）、`before_reply`（代回之前、可改回信、退 10 改回 `HookRejected`）。改過的 body 進隊存 `bodies/<信名>.json`。新代號 `HookRejected`（拒信）、`HookFailed`（自己的錯，退 1、信留著）。

- 測試：`test_kernel`＋`test_kernel_hooks`（新 11 例）共 27 例全過。
- 隊長審 diff 時改回一處：codex 把「臨轉寄再驗一次期限」整段拿掉了；改成規則放行的照舊再驗、hook 改判成放行的照字面不驗。
- 代定（圖紙沒寫，照保守做）：多個 `after_verdict` 的 `condition` 比的是內建規則最初的判決，前一格改判不影響後面哪幾格會被叫（後面的看得到改過的值）；`bodies/` 讀不了、刪不掉也算 `StateBad`；設定關掉 `queue` 後，上一輪窗裡的信仍算隊中信（不重跑 `before_verdict`）、照新設定判。
- `hook_run.py` 用起來的不順：改了值時引擎不回是哪個 hook 改的，所以 `after_verdict` 一格一格叫才補得上「refused by hook <名>」；引擎沒改。

## 十一、事故：子 agent 誤停使用者的樹（11-13 10:25）

- **時間**：2026-11-13 10:25:05（台北）。
- **指令**：批 11a 的子 agent 在暫存夾手跑框架站範本，收工時下 `pkill -INT -f "aos-daemon --enable-logs daemon.json"`。這個字串不含暫存夾路徑，`~/aos-home` 根 daemon 的命令列一模一樣。
- **影響**：`~/aos-home` 的根 daemon（退 130）與領班那台（退 143）都停了，底下的鐘、清道夫與各 agent 的 loop 全停；各 agent 的 CLI 畫面與 `aos-mcp` 還在。停了約數分鐘。repo 的檔沒受影響。
- **怎麼復原**：子 agent 發現後立刻停手回報、沒自己重起；使用者自己把樹起回來，調度者核過七列都 running、沒有重複。
- **原因在任務書**：只寫了「不碰 ~/aos-home、跑完把起的行程收掉」，沒規定怎麼收。
- **之後的規則**（這條線的隊長、子 agent、codex 都適用，寫在每份任務書開頭）：
  1. 禁止 `pkill`／`killall`／`kill $(pgrep …)` 與任何按名字或命令列字串收行程的寫法；`aos-daemon-ctl` 一定帶 `-d`、而且只能指到自己的暫存夾。
  2. 收行程只准兩種：`aos-daemon-ctl -d <自己暫存樹 stack 的絕對路徑> shutdown`（下之前先印出路徑、確認在自己的暫存夾下）；或 kill 起的時候記下的 pid（kill 前 `readlink /proc/<pid>/cwd` 確認在自己的暫存夾裡）。
  3. 起任何 aos 行程前 `env -u` 掉所有 `AOS_*` 變數；暫存夾用獨一無二的路徑。
  4. 收尾核對 `pgrep -u guanyu -af 'aos-daemon'` 只剩 `~/aos-home` 的兩台，貼進回報；多了或少了立刻停手。

### 批 11a

`kernel/README.md`、`kernel/docs/02-kernel-modes.md` 重寫成「框架站＋擺法」（零件表、`kernel.json` 的鍵、三種擺法、鏈與 hook 的例子；指令都在暫存夾實跑過：daemon 的身體、排隊、loop proc、兩站的鏈、`before_verdict` 與 `before_reply`）；舊名換新名（附錄 4 持久檔 12 處、lib 索引、impls 地圖、aos-daemon docs/06、proto8/README、knowledge `aos/kernel.json`、wf code-map 地圖）；N-42、C-47、C-51 只加註現況與換路徑——N-42 (2) 收進使用者 11-13 對 `next` 的原話與 kb-ctl 裁定（`aos-daemon-ctl` 直寄照現況，「唯一的門」只約束 proc）。

條文裡跟現況字面對不上、只加註沒改的（要不要改寫由使用者或條文線定）：
- N-42 (2)「有序信經判官」說開了 `keep_ordered` 就代回；現在代回歸 `reply_via_me`、兩鍵獨立（圖紙 K-F39 代定）。
  - **`kf-t1` 裁定（11-13）＝選 A：條文改寫成照程式——兩個開關各自獨立、照字面。** 使用者回覆原文：「kf-t1:A*」（第二輪待裁頁 `wu-1113-r2`；來源檔沒有建議，`*` 只是頁面記號）。還沒施工。
- N-42 (2)「數量另指」說「下一站不是 daemon 時」才報設定錯；程式是寫了 `next`＋`max_running` 就一定要 `count_daemon`（圖紙 K-F6 代定）。
  - **`kf-t2` 未裁（11-13）**：使用者選了「還沒想好，先不選」，回覆原文：「kf-t2:U*」。維持加註現況。
- N-42 (2) 各子點仍叫「判官」、標籤仍寫「方向（已定，未實作）」；C-47 標題仍是「已裁定、未實作」。
  - **`kf-t3` 未裁（11-13）**：頁面上沒點開，回覆原文：「kf-t3:U*?」。維持加註現況。
- N-42、C-47 引的 11-12「開工等假日」原話留著，旁邊加註 11-13 已開工。
沒實跑的：`after_verdict` 的例子（只列在表裡）、`keep_ordered`。

### 批 7a

新夾 `extras/kernel-chain-check/`（`check.py`＋`README.md`）：暫存夾起根 daemon → `station_a`（loop proc 式框架站，`next` 指領班、`reply_via_me`、`before_verdict` 擋 `evil`）→ 領班（daemon 身體式框架站，`max_running` 4、`queue`），五段都過（掛子經兩站且回信經 A 代回對得上原信、超過上限排隊再出隊、`evil` 立刻 `HookRejected`、兩站重起後隊序與待代回不變且沒有信轉第二次、`ping` 穿兩站）。第 1 段用 `llm_fake` 產生工具呼叫、劇本手動跑真的 `subagent` 工具；第 2、4、5、6 段由劇本帶 agent 的環境直接寄信。第 3 段（`ctl ls` 走查詢信拿刪減表）留 TODO，等批 4。

- 隊長改掉一處：codex 把「全機只准剩 `~/aos-home` 兩台 daemon」的核對寫進了劇本（那是給施工者的規矩，不該進程式；別台機器、別條線起著測試 daemon 時會誤報），拿掉；劇本只核對自己暫存夾底下沒有殘留行程。
- 劇本收行程只用 `aos-daemon-ctl -d <暫存夾裡的 stack> shutdown` 與自己記下的 pid（送訊號前核 `/proc/<pid>/cwd` 在暫存夾裡）。

## 十二、下午接手（線己二）：使用者中午的裁定與停樹

### 使用者 11-13 中午在待裁頁的裁定（逐字；題目與選項在 [decide_20261113_wu-r2.json](decide_20261113_wu-r2.json)，用 id 查；整行見[回覆檔](decide_20261113_wu-r2.reply.txt)）

> kf-n1:B*、kf-n2:A*（備註：寄信給eca_main，跟他約時間。）、kf-next:B*（備註：如果覺得麻煩，那就直接報錯算了）、kf-t1:A*、kf-t2:U*、kf-t3:U*?、kf-1b1:U*?、kf-1b2:U*?、kf-lim:U*?

- `kf-n1:B`——問腦那一包現在就用假腦做（Python 重寫），真腦回家再驗。
- `kf-n2:A`——今天收工前或明天開工前停一次樹。調度者跟 `eca_main` 約定：**今天 15:30 停、16:00 前起回來**（硬上限 30 分鐘）；停樹、起樹的指令由使用者自己下。
- `kf-next:B`——框架站找下一站改成三段：先看 `next`，沒有就看 `AOS_KERNEL`，再沒有才 `AOS_DAEMON`；哪一個指到自己就跳過。
- `kf-t1:A`——條文改寫成照程式：`keep_ordered`、`reply_via_me` 兩個開關各自獨立、照字面。
- `kf-t2`、`kf-t3`、`kf-1b1`、`kf-1b2`、`kf-lim` 未裁：N-42 (2)「數量另指」那句、「判官」稱呼與「未實作」標籤、C-47 標題、批 1b、`hook_run` 對外的樣子、轉寄對照的已知限制——都不動。

### 代定（線己二；可翻案）

4. **kf-next 備註「如果覺得麻煩，那就直接報錯算了」的讀法**。三種讀法：(甲) 三段裡任何一個指到自己都跳過、看下一個（選項 B 的字面）；(乙) 任何一個指到自己都報設定錯；(丙) 整個三段嫌麻煩就不做、沒寫 `next` 直接報錯（跟他選 B 矛盾，不取）。做的是甲、乙各取最省事的一半：
   - 沒寫 `next`、`AOS_KERNEL` 指到自己的收件箱＝**跳過**，往下看 `AOS_DAEMON`。這是繼承來的環境變數（整棵樹 export `AOS_KERNEL` 指到這一站、站自己也繼承到），最常見，跳過只要比一次路徑。
   - 明寫的 `next` 指到自己＝照舊 `CfgBad`（明寫的值照字面、不偷偷換成別的行為；備註允許報錯）。
   - 從 `AOS_DAEMON` 算出來的轉寄目標是自己＝照舊 `CfgBad`（後面沒得跳）。
   - 三段都用不上＝`DaemonMissing`。
5. **下一站來自 `AOS_KERNEL` 時去哪數 `max_running`**：這時下一站是別的站、不是 daemon，設定寫了 `max_running` 卻沒寫 `count_daemon`＝`CfgBad`（條文「下一站不是 daemon 時設了 `max_running`＝報設定錯」與程式現有的「寫了 `next` 就要寫 `count_daemon`」在這裡結論相同，所以不碰未裁的 kf-t2）。
6. **整棵樹 export `AOS_KERNEL` 時的後果（kf-next:B 帶來的，寫進說明）**：沒寫 `next` 的站會把信轉給 `AOS_KERNEL` 指的那一站；兩站互指成環照舊不偵測。不想要就在起那一站的殼 `unset AOS_KERNEL` 或明寫 `next`（同使用者對 K-F50 的備註「可以用unset吧」）。
7. **問腦那一包的代定**（批 8、9；細節在 [`lib/aos/kernel_llm/README`](../../../lib/aos/kernel_llm/README.md)）：五個口另放 `llm_rules.py`（圖紙列的五個檔各管一塊資料，口放哪個都不對）；骨架加一個小口——包有 `read(path)` 就由包自己讀設定（問腦的設定每組指示詞用到才解，骨架原本整份先過 aos-directive 會讓一組解不開就整台 `CfgBad`）；`before_reply` 失敗重來不重複記帳，靠 `proc.json` 多一個暫時鍵 `counted`；`before_reply` 只對掛出去跑過、有結果的信跑，總機自己拒掉的不跑；hook 把驗不過的信改判放行＝沒有包可跑、照原本的錯回信；信封讀不懂的信不交給 hook；`LaunchFailed`、`DirectiveBad` 的訊息為了跟 C++ 逐字相同，從 aos-post、aos-directive 的錯誤行解代號。`runner.py` 不自己決定掛信去處、由包給信箱（K-F50 翻成 B 之後的做法）。
8. **批 4 的代定**：回信路徑照字面轉絕對、不解捷徑；壞信（不是 `true`）整封不套、回信不帶那個 key；沒問的信回信不多帶 key；多一例「沒開窗回 `null`」。
9. **批 5、6 的代定**（碼在補丁裡、還沒接線，接線時一起生效）：走 kernel 那條路的條件＝設了 `AOS_KERNEL` 且沒明給 `--daemon`；只看回信的是 add、rm（不帶 `--purge`）、stop、start、sleep、wake，`rm --purge`、`set-def`、`pause`／`resume` 仍要查表（經查詢信拿）；`--timeout-s` 只加在 `ctl ls`／`who`／`where`／`state`；subagent 看到舊帳的相對路徑報 `ReadFailed` 並指路、不默默忘掉；`on_clock` 找不到鐘時 30 秒內不重問。
10. **批 5 今天不接線**：接線後凡是設了 `AOS_KERNEL` 的都要 daemon 會答查詢信；跑著的樹沒設 `AOS_KERNEL`、今天接沒有好處，而 `cmd/`、`py/` 存檔即生效。等新 daemon 上線、挑一個樹不忙的時段再接。

### 下午的實作結果

#### 批 1：kf-next＋kf-t1（`4fcb631fd`）

`lib/aos/kernel/procs_rules.py` 找下一站改三段（做法見代定 4～6）；N-42 (2)「下一站」「有序信」兩句照裁定改寫，其餘沒動；說明與知識庫跟上；`kernel-chain-check` 改成兩站都不寫 `next`、都拿到指向領班信箱的 `AOS_KERNEL`。測試：`lib/aos/kernel/tests` 32 例 OK（新 5 例）、鏈劇本 5/5、`gitignore-check` 整棵過。
留意：範本 `kernel/daemon-kernel`、`kernel/procs-kernel` 都寫了 `max_running`、沒寫 `next` 與 `count_daemon`——繼承到指向**別站**的 `AOS_KERNEL` 時每輪 `CfgBad`（指向自己沒事）。

#### 批 4：aos-daemon 認 `procs_state_path`（`42870fa27`）

只改原始碼；repo 裡沒 build。驗法：CMake 把執行檔寫回原始碼夾的 `bin/`，所以把 `impls` 整份抄到 repo 外 `~/code/kbuild-1113/impls` 編（configure 1 分、只建 daemon 3 分 15 秒、全量約 5 分鐘；build 前後 repo 那支的 mtime、inode 沒變）。新 4 例在舊執行檔全紅、新執行檔 OK；既有 8 支與鏈劇本用新執行檔都過。`tests/support.py` 把 repo 的 bin 放 PATH 最前面，新測試另認 `AOS_TEST_DAEMON_BIN_DIR`。

#### 批 8、9：問腦那一包（`df1c25ff2`）

`lib/aos/kernel/runner.py`＋`lib/aos/kernel_llm/`。五支黑箱測試改指新程式全過、新 hook 5 例、runner 7 例；跟 C++ 逐欄比 46 輪＋真 daemon 12 封全同；200 封排隊一輪 51～64 ms（C++ 3～5 ms），不用記已知限制。C++ 那支與範本接線沒動。
跟 C++ 的已知差異（README 也列）：stderr 前綴；收到 TERM 當場結束（C++ 做完這輪）；鎖與建信箱在骨架；`kernel.json` 多認 `hooks`；`endpoints` 整張寫成指示詞時只有「單一 `$ref` 指到一份 JSON 檔」做得到每組用到才解；`deadline` 驗得較嚴；每輪多起幾個子行程。
骨架還不順、沒改的三處（等有需要再動）：`before_verdict` 在排序之後才跑（hook 改了 `priority` 的新信第一輪照舊值排）；`hooks.before_reply` 攔下時回的是掛 proc 那包的形狀（問腦包自己拿掉 `applied`）；hook `on_error: stop` 中途退 1 時 `pack.finish` 不會被叫（這輪的後端黏著記錄不落檔）。
`kernel/docs/03-feat-proto.md` 件 2、3 寫的「兩列 running、8 秒後 4 封」跟範本（`slots` 2、`reserved.high` 1）對不上，實際 1 列、2 封；兩支行為相同，是文件的問題，批 12 一起修。

#### 批 5 前半（`bb4204242`）與批 5 接線、批 6（補丁，沒進 main）

進 main 的只有新模組 `py/daemon_ctl/state_path.py` 與兩支測試（沒人 import，行為不變）。接線與批 6 在 repo 外：`~/code/kf2-1113/a4/batch5-wiring.patch`（12 檔）、`batch6.patch`（22 檔），在 repo 複本驗過：沒設 `AOS_KERNEL` 的 39 步改前改後 rc／stdout／stderr 一致（只有 `--help` 與 usage 字串多了 `--timeout-s` 與 `AOS_KERNEL` 的說明）；只設 `AOS_KERNEL` 經假 kernel 能掛子、分身；接線＋批 6＋新 daemon 時鏈劇本 5/5，接線＋舊 daemon 時第 1 段 `KernelFailed`（所以接線要排在新 daemon 之後）。`on_clock` 沒做真 daemon 端到端。
批 6 上線要重建什麼：各 agent 的 `<stack>/tools/subagent/subagents.json`（帳；`<stack>/subagents.json` 是配額設定、不要刪）舊帳不認——先 `aos-agent ctl rm` 掉列在裡面的子 agent 或接受它們不再歸工具管，再刪帳、重抄 lib；沒清不會壞資料，工具報 `ReadFailed … relative stack path`。

#### 批 10 備料（補丁，沒進 main）

`~/code/kf2-1113/a2/batch10.patch`（50 檔：兩個範本換身體、標頭與 `letter.cpp` 搬進 `impls/aos-llm`、刪 `impls/aos-llm-kernel`、CMake、測試與 extras 換身體）。Python 部分在 repo 複本驗過（`judge-llm`、`image-move-check`、`reviewer`、`measure`、`review_round`、agent-fsm 幾支都過）；**C++ 部分沒 build 過**，所以今天不做。照做的步驟：套補丁 → `rm -rf proto8/impls/aos-llm-kernel proto8/impls/build` → 重 build → `install.sh`＋手動 `rm ~/.local/bin/aos-llm-kernel`（install 不會自己清斷掉的捷徑）→ 跑 `lib/aos/kernel_llm/tests`、`impls/aos-llm/tests`、`templates/tests`、兩支 extras；退＝`git apply -R` 後重 build、重 install。`~/aos-home` 沒有問腦總機，不用重建樹裡的東西。

### 停樹時照做（11-13 15:30；腳本在 repo 外 `~/code/kf2-1113/stop-tree/`）

停樹、起樹由使用者下指令；樹停後由線己二隊長跑腳本。腳本不含任何 kill／shutdown，每段先確認「cwd 在 `~/aos-home` 底下的 aos-daemon／loop／fsm／exec 一個都不在」才動。

| 步 | 指令 | 必做／可延後 | 實測 |
|---|---|---|---|
| 停之前 | 15:08 釘一個 commit 當 `ST_REF`、在乾淨檢出上跑全套（`~/code/kf2-1113/fullsuite.sh <ref>`，約 13 分鐘）；核對 `~/code/kbuild-1113/impls` 的原始碼＝該 commit | 必做 | — |
| 1 | `ST_REF=<hash> swap.sh precheck backup copy`：備份樹的 `lib`、`templates`、`knowledge`、`py` 與十支 C++ 執行檔到 `stop-tree/backup-<時間>/`，再從 `git archive <hash>` 把四夾換進樹（先抄到旁邊再改名） | 必做 | 各不到 1 秒 |
| 2 | `ST_REF=<hash> swap.sh daemon`：把預先編好的 `aos-daemon` 原子換到 `~/repo/aos/proto8/impls/aos-daemon/bin/aos-daemon`（`~/.local/bin/aos-daemon` 實際指到的檔）；原始碼不等於該 commit 就不換 | 可延後 | 不到 1 秒 |
| 起樹後 | `ST_EXPECT_STATE_PATH=1 verify.sh`：兩台 daemon 在、八列 running 不重複、ping、查詢信有答、elsa-watch 三件（一個實例、有 `scan_complete`、`last_success` 有更新） | 必做 | 1.4 秒 |
| 退回 | 樹停著時 `rollback.sh all`（或 `tree`／`bin`）：還原備份 | — | 0.4 秒 |

- 批 6 上線、批 10 刪 C++ 問腦：今天不做（腳本裡是佔位段，叫了直接報錯）。
- `install.sh` 不用重跑（`--dry-run`：would link 0, already 25）。
- 換檔之後 repo 的 `impls/build` 比執行檔舊；之後在 repo 重 build 會從已 commit 的原始碼編出等價的檔。
- 重抄等於把當天所有線已 commit 的 `lib`／`templates`／`knowledge`／`py` 改動一次帶進樹；樹裡這四夾 08:32 之後沒人改過（跟 `2e8eb6736` 逐檔相同），不會蓋掉使用者的東西。`agents/*`、`ws/defs/*` 不動。
- 預演：在暫存樹（根 daemon＋ws daemon＋鐘＋兩列假 proc）完整跑兩輪都過，含「樹在跑時被擋」的紅燈與 rollback 後逐位元相同。

## 十三、照規則分流（線未）：hook 替單封信指定下一站

使用者原話在最上面「看完架構圖後」。結論：`next` 維持一個不變；分流規則寫在 `after_verdict` hook 裡，hook 的 stdout 回 `{"next": "<信箱的絕對路徑>"}`，這一封放行時就寄去那裡，一封信只去一處；沒回（或回 null）照原本三段（`next` → `AOS_KERNEL` → `AOS_DAEMON`）。

### 改之前的現況

三個時機都換不了下一站。`hooks.py` 的事件表只收 `before_verdict` 的 `body`、`after_verdict` 的 `verdict` 與 `error`、`before_reply` 的 `body`；共用引擎對不在表上的鍵直接略過、不報錯，所以 hook 回 `next` 沒有任何效果。圖紙也沒寫過「hook 換下一站」（圖紙的「換路徑」指的是查詢信的表檔路徑），整鏈劇本沒寫的第 3 段是查詢信，不是分流。證據：新測試檔在改之前的程式上跑，12 例裡 16 處失敗（test_01 信照舊進原本的下一站），只有 test_02（另兩個時機回 `next` 不被理會）、test_08、test_11 過。

### 做了什麼

- `lib/aos/kernel/hooks.py`：`after_verdict` 能改的鍵加 `next`；會轉寄的包事件多一欄 `next`（null）；最後判決是 pass 才把路徑記進 `ctx.route[信名]`。
- `round.py`：`ctx.route`，以及包有 `check_next(ctx, box)` 才收 `next`（沒有這個口的包——問腦那一包——遇到 hook 給 `next` 算 hook 自己失敗；`lib/aos/kernel_llm` 一行沒動）。
- `procs_rules.py`：`check_next`（下面代定 3、4、5）；`dispatch` 把這一封的路徑交給轉寄。
- `letters.py`：`forward` 多一個選填的信箱；`in_box` 從 `already_forwarded` 抽出來，指定的站裡已有同名信就不寄第二次。
- 新測試 `lib/aos/kernel/tests/test_kernel_route.py` 12 例；`extras/kernel-chain-check` 加第 7 段（一個站、兩個下一站、兩種信各到各的、回信都經原路代回），結尾改印 `6/6 ok`。
- 說明：`lib/aos/kernel` README（「分流」一節、hook 表、包的口、錯誤代號）、`kernel/README.md`、`kernel/docs/02`（「分流的例子」，指令在暫存夾實跑過：`kid4` 掛到旁站、`kid3` 掛到後站、兩封回信都是 `{"applied": true}`）、知識庫 `knowledge/aos/kernel.json` 一句、N-42 (2) 一處加註（沒改條文意思）、`_entry` 的 help 一行。

### 代定（線未；可翻案）

1. **時機選 `after_verdict`**：它是「判決定下來的那一刻」，下一站是「放行之後去哪」，同一件事；排隊的信出隊時它本來就會再跑一次，所以不用另存「這封要去哪」。選 `before_verdict` 的話排隊信要多一份落檔。
2. **欄位名 `next`**，跟 `kernel.json` 的鍵同名；值只收絕對路徑或 null。相對路徑有兩種算法（設定檔所在夾、hook 自己的小格），不猜，直接算 hook 失敗。
3. **指到自己的 `requests/`**＝hook 自己失敗（`HookFailed`，照 `on_error`；預設 stop：這輪退 1、信留著）。照使用者 11-13 對同類情形的備註「如果覺得麻煩，那就直接報錯算了」；不報 `CfgBad` 是因為錯的是 hook 的回話、不是設定檔。
4. **數量上限**：hook 給了 `next`、設定有 `max_running`、沒寫 `count_daemon`＝`CfgBad`（現有「寫了 `next`＋`max_running` 就要 `count_daemon`、不猜下一站是哪台」最保守的延伸；沒寫 `next` 時原本預設數 `AOS_DAEMON` 的那條不沿用到被分流的站）。寫了 `count_daemon` 就照字面：不管信去哪一站都算進同一個上限。
5. **有序信**：`keep_ordered` 開著時 hook 給 `next`＝`CfgBad`（不分那一封是不是有序信）。分到不同站的信沒有先後保證；而且各站各自編有序信名，兩站可能編出同名，`forwarded.json` 的對照會撞。沒開 `keep_ordered` 照舊：有序只保證到本站門口。
6. **留隊、被拒時給的 `next` 不記**（沒有信要寄；留隊的出隊時 hook 再跑一次）。
7. **站自己仍要有原本的下一站**：三段都用不上照舊 `DaemonMissing`，即使 hook 會替每一封指定。
8. **防重**只認「指定的站裡還有同名信」；hook 對同一封信前後兩次給不同答案時認不出來，寫進說明當限制。
9. **`forwarded.json` 格式沒改**：不記信去了哪一站（代回只靠轉寄後的信名，夠用）。

### 要使用者裁的

- **各下一站各自的數量上限**：分流後如果要「甲站後面那台最多 N 個、乙站後面那台最多 M 個」，現有設定只有一個 `max_running`＋一個 `count_daemon`，原則推不出該怎麼寫（每個下一站各寫一組？還是一律交給各站自己管？）。這次沒做：現在的行為是全部算進同一個上限，要分開管就在各下一站自己的 `kernel.json` 設。
- **`keep_ordered` 與分流同時要**：現在直接報設定錯。真有需要時要先定「有序」的範圍（同一個下一站之內？）與對照表怎麼分站。

### 結果

`lib/aos/kernel/tests`：`Ran 51 tests`、`OK`（原 39＋新 12）；`lib/aos/kernel_llm/tests`：`Ran 32 tests`、`OK`；`kernel-chain-check: 6/6 ok`。
- **13:05 追加（調度者轉使用者確認「好，5、6、7都照你的看法。」第 7 題＝抄本也抄 `kernel/`）**：重抄多一夾 `proto8/kernel/` → `~/aos-home/kernel/`（知識庫 `aos/kernel.json` 說範例在 `$AOS_HOME/kernel/`，樹裡原本沒有這一夾）。腳本改四處：樹裡原本沒有的夾，precheck 只報告、backup 記進 `tree/ABSENT`、copy 照建、rollback 把它刪掉。暫存樹再預演一次：抄完 `kernel/` 25 檔與該 commit 相同；rollback 後 `kernel/` 不見、其餘四夾內容與模式位元跟抄之前相同。沒有東西會掃 `$AOS_HOME` 底下的夾（`env.sh` 只 export；讀 `AOS_HOME` 的 `aos-tools`、`aos-mcp-launch` 只拼 `lib` 路徑）。兩個提醒：`kernel/docs` 與 README 連到 `../thinking`、`../docs` 的相對連結在樹裡會斷；範本 `llm-kernel`、`llm-team` 的身體仍是 C++ 那支 `aos-llm-kernel`。
- 另加一段 `swap.sh stray`（調度者交辦、樹停著才做）：`~/aos-home/ws/.stack/procs/repo-aos/` 被別線測試誤寫的 `interfaces.json`、`observed.jsonl` 先備份到備份落點的 `stray-repo-aos/` 再刪；內容不是「`{"aos-observed": {"file": "observed.jsonl"}}`＋兩行、第一行 `ws` 在 `/tmp/`」就不刪（預演驗過這個紅燈）。`daemon_reply/` 不動。
