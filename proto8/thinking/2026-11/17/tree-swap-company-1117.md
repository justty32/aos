# 11-17 公司 WSL 換樹紀錄：把 ~/aos-home 的程式複本從 11-13 版換成 main d5f47c890（C++ 九支重編、五夾換掉），附帳格式查核與起樹前後待改清單

← 規格：[aos-teams/06「停樹換檔的做法」](../../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)｜腳本：[tree-swap](../../../extras/tree-swap/README.md)｜家機上一次：[tree-swap-1114](../14/tree-swap-1114.md)

## 結論

- **換好了**。公司 WSL 的樹 `~/aos-home` 現在 `lib templates knowledge py kernel` 五夾都是 `d5f47c890`（每夾 `.aos-source.json` 都蓋了這個章，verify 逐檔相同）；`~/.local/bin` 的九支 C++ 是同一個 commit 在 repo 外編的。
- **樹沒起**。換前換後都沒有 aos-daemon／aos-loop 行程，兩個 `state.json` 都還是 `stopped`。起樹由使用者自己下。
- **帳的格式沒有卡住的**：公司樹的 stack 裡沒有任何 `subagents.json`（c3c1877ea 那個坑在這棵樹不會發生），定義裡也沒有 `$at`／`$ref`。
- **起樹前要知道**：各 agent 定義還是 11-13 的設定（逾時 600000／900000、hooks 沒有 context_wrap／brain_notify／screen_linger、cli.json 沒有 live_mail），程式換新了、設定沒換；家機這四天做過的活樹設定修改一項都還沒做，清單在第 5 節，要使用者看過才改。不改也起得來，只是行為跟 11-13 一樣（例如一輪超過 10 分鐘會被當失敗）。

## 做了什麼

全程在 WSL、從 `~/repo/aos`（HEAD `d5f47c890`，工作樹乾淨，只有未追蹤的 `proto8/impls/aos-llm-kernel/`，沒動）跑；每支腳本開頭逐一 unset `AOS_*`（實際一個都沒有）。

| # | 指令 | 結果 |
|---|---|---|
| 0 | `pgrep -u $USER -af 'aos-daemon\|aos-loop'`；看 `~/aos-home/{.stack,ws/.stack}/state.json` | 沒有行程；兩個都是 `"phase": "stopped"` |
| 1 | 唯讀查帳格式（見下節） | 沒有受影響的舊帳 |
| 2a | `bash proto8/extras/tree-swap/build.sh --ref d5f47c890 --install`（第一次，背景） | **失敗**，2 秒就 `RED: build aos-daemon failed`；log `~/.aos/scratch/tree-swap/build-20261117-084143-8861/log/aos-daemon.log`（vcpkg 停在 `Detecting compiler hash`，接著 CMake 說找不到 make／編譯器）。原因是我用 `nohup … &` 起在背景，叫它的那個 `wsl` 一結束，背景工作就跟著斷；make、gcc、g++ 都在 `/usr/bin`。沒有東西被換（build.sh 編失敗什麼都不換） |
| 2b | 同一支，改用 `setsid nohup … < /dev/null &` 起在背景 | **成功**：九支共 313 秒，`install: 9 binaries replaced`，沒有任何 `warning:`（沒有行程在用）。編譯夾 `~/.aos/scratch/tree-swap/build-20261117-084221-9057`（`BUILD_REF`＝`d5f47c890…`），log 在 `/tmp/ts1117-build2.log` |
| 3a | `swap.sh --ref d5f47c890 check` | `check: green`；lib 改 103／新 63、templates 改 33／新 11、knowledge 改 81／新 10、py 改 9／新 4、kernel 改 5；**「只在樹裡有」每夾都是 0**，沒有 `RED:` |
| 3b | `swap.sh --ref d5f47c890 all` | check→backup→copy→stamp→verify 全綠，`verify: green (lib templates knowledge py kernel)`，五段合計不到 1 秒 |
| 4 | 唯讀核對 | 五夾 `.aos-source.json` 的 `commit` 都是 `d5f47c890233f26728089151eedaa5793f08914d`；九支 `~/.local/bin/aos-*` 都指到 `~/repo/aos/proto8/impls/<p>/bin/<p>`，跟編譯夾裡的逐位元相同，時間 11-17 08:47；九支都不認 `--version`（`FlagUnknown`），`--help` 九支都退 0 印出 usage。換後再看一次：沒有 daemon／loop 行程、兩個 state 仍 `stopped`、`ws/.stack/procs` 九格跟換前一樣 |

## 備份在哪、怎麼退回

- **五夾的備份**：`~/.aos/saves/tree-swap/20261117-084754/`（5.1 MB，`META` 記 ref 與時間；`LAST` 指著它）。
- **換下來的舊五夾**：`~/.aos/saves/tree-swap/run-20261117-084754-17323-swap/old/`（同一份東西，copy 那段換下來的）。同夾還留 check／stamp／verify 的暫存，合計 23 MB；先單跑的 check 另留 `run-20261117-084746-17182-swap/`（6.7 MB）。都沒刪。
- **退回五夾**（樹要是停著的）：`bash ~/repo/aos/proto8/extras/tree-swap/rollback.sh`（還原 `LAST` 那份，還原後逐檔比對）。
- **退回 C++**：build.sh 是 rename 換，**舊的九支執行檔沒有留備份**（腳本的設計：C++ 要退就用舊 commit 重編）。舊那批的確切 commit 不知道：八支是 11-13 08:22 編的、aos-daemon 是 11-13 11:21 編的（比 `42870fa27`「aos-daemon 認查詢信」11:27 的 commit 早幾分鐘，可能是從工作樹編的）。要退的話最接近的是 `bash ~/repo/aos/proto8/extras/tree-swap/build.sh --ref 42870fa27 --install`，但不保證跟舊檔逐位元相同。
- 兩個編譯夾 `~/.aos/scratch/tree-swap/build-20261117-084143-8861`（失敗那次）、`build-20261117-084221-9057` 都留著；`/tmp/ts1117-*.sh`、`/tmp/ts1117-*.log` 也留著。

## 第 1 項：帳的格式

查的範圍是 `159414053..d5f47c890`（樹裡的複本實際是 11-13 15:00 的 `159414053`，比任務書寫的 `902355b23` 早 21 筆，所以從更早的那個算；兩段差的 21 筆裡沒有改帳格式的）。

| commit | 改了什麼帳 | 公司樹現況 | 起樹後會怎樣 | 建議 |
|---|---|---|---|---|
| `c3c1877ea`＋`398f71711` | subagent／fork 的名冊（`subagents.json`）改存絕對路徑，舊的相對路徑不認、不遷移；398f71711 起讀到舊格式回 `BookOld`、名冊不動 | 樹裡沒有任何 `subagents.json`（只有 `templates/agent-fsm/subagents.json` 這份範本設定）、也沒有分身帳；九格 stack 都沒掛子 | 不受影響 | 不用處理 |
| `0c3a4f860` 回答配對 | stack 多 `letters.json`、history 列多 `aos` 鍵 | 舊 history 沒有 `aos` 鍵、沒有 `letters.json` | commit 寫明：舊 history 照讀（走退路）、沒有 letters.json 當空的 | 不用處理 |
| `75a6ca81e` B7 | 小格多一個 `stop_cause.json`（daemon 寫、loop 讀） | 沒有 | 新舊混用不壞；第一次停之前 cause 是 null | 不用處理 |
| `c3a21db8d` mail_notify | 沒有 `notified.json` 且 history 非空＝當睡醒，提醒一次等著的信 | 7 隻 eca 的 `hooks/mail_notify/notified.json` 都在 | 不會多提醒 | 不用處理 |
| `d80350a04` | 刪掉 `$at`、`$ref` 的 `#` 規則改嚴（`#aaa` 之類變 DirectiveBad） | 掃了 agents、ws/defs、root、daemon、各 stack 的 152 份 json：`$at` 0 處、`$ref` 0 處 | 不受影響 | 不用處理 |
| `fa560bca1` | daemon 的 stuck 判定預設關（沒寫＝不判） | 表上只有 `_clock`（10000）、`_sweeper`（600000）明寫，其他列沒寫 | 以前沒寫的列 10 個 cycle 沒動靜會被標 stuck，起樹後不會了；這是想要的行為 | 不用處理 |
| `8706d7398`、`e56923a97` | 腦請求的寄件人改成 stack | 公司樹沒有 LLM kernel 列（llm-gpt 那類） | 不受影響 | 不用處理 |
| daemon 表 `procs_state.json` | 這段期間 daemon 改了 limits（B4、B5）、stuck、查詢信、停止原因 | 表上 12 列都 `sleeping`，stack 用相對路徑 `procs/<名>` | **沒驗到**：沒起 daemon，不知道新 daemon 接舊表會不會有怨言。commit 說明都沒寫要重建表 | 起樹後先看 `aos-daemon-ctl -d ~/aos-home/ws/.stack ls` 是不是九列都回來 |

另外：換前 `~/.local/bin` 的 `cmd`／`py`（連到 repo、存檔即生效）早就是新版，樹裡的 lib 卻是 11-13 的；這次換完兩邊對齊了。

## 第 5 項：起樹前後還要做的事（都沒動，要使用者看過才改）

公司樹的定義：`agents/eca_main`、`agents/ops-agent`、`ws/defs/agent`（repo-aos、wf-agent 共用）、`ws/defs/me-agent` 是 claude；`ws/defs/codex`、`ws/defs/gpt-price`、`ws/defs/gpt-soap` 是 codex；`elsa-watch` 是一支 run.sh。**沒有 agent-fsm 定義、沒有 `kernels/`、沒有 `ws/tools`**。各 stack 底下沒有自己的 `hooks.json`／`cli.json`。

| # | 檔 | 現值 | 建議改成 | 依據 | 不改會怎樣 |
|---|---|---|---|---|---|
| 1 | 7 份定義的 `cli.json`（上列七個） | `"timeout_ms": 600000` | `0`（不限） | SESSION-LOG 11-15「三線施工」的「換樹時要做」；`740895b65`（沒寫、null、0＝不限） | 一輪超過 10 分鐘就被當 CliFailed |
| 2 | 同 7 份的 `loop.json` | `"exec": {"timeout_ms": 900000}` | `0` | 同上；新範本 `templates/eca-claude/loop.json` 是 0 | 一輪超過 15 分鐘 loop 會砍掉 |
| 3 | 4 份 claude 定義的 `hooks.json` | 只有 `timer`、`mail_notify` | 加 `context_wrap`（on_clock、every_ms 5000、config.percent 35），照新範本 | SESSION-LOG 11-15「各 eca 定義 hooks.json 加 context_wrap」；`17be4fe8f`；ok-small「從沒跑過 -p 的 agent 要設 config.window」 | 用量到 35% 不會自動收尾＋compact |
| 4 | 同 4 份 `hooks.json`（codex 3 份要不要也加，待定） | 沒有 `brain_notify` | 加 `brain_notify`（event `brain_failed`） | 線星 AK17、ok-ecaretry（永久錯照舊停並由 brain_notify 寄 BLOCKED）；SESSION-LOG 11-16「已複製出去的定義沒有 brain_notify hook」 | 腦永久出錯時停下，但沒人收到 BLOCKED 信 |
| 5 | 同 4 份 `hooks.json` | 沒有 `screen_linger_start／stop` | 加兩格（after_start／after_stop），照新範本 | `f23cae72b`（C′ A 包）；tree-swap-1114 第 6 步 `hooks` | 畫面不會照 screen_linger 的規則留／收 |
| 6 | 4 份 claude `cli.json` | 沒有 `live_mail` | `"live_mail": true` | SESSION-LOG 11-16 live_mail 那條（家機五份都開了） | 回合中途來的信要等下一輪才看到 |
| 7 | 4 份 claude 定義 | 沒有 `compact_hook` 檔，`cli.json` 沒有 `settings.hooks` | 要不要抄新範本的 `compact_hook`＋`settings`（PreCompact／SessionStart）待使用者定 | `17be4fe8f`；新範本 cli.json 有這段 | 對話被 compact 時 aos 不知道 |
| 8 | agent-fsm 定義 | 公司樹沒有 | 不用做 | SESSION-LOG 11-16「舊 fsm 定義都換成新範本」 | — |
| 9 | 全景頁 aos-view | 沒裝：沒有 `ws/tools/`、沒有 `~/.config/systemd/user/` | 要的話抄 `proto8/extras/aos-view` 到 `~/aos-home/ws/tools/aos-view`，再裝 `systemd/aos-view.service`（systemctl 要使用者同意；使用者 11-15 也說過「不要誰都能掛 systemd」） | SESSION-LOG 11-15、11-16 全景頁各條 | 沒有全景頁，專區的題目看不到 |
| 10 | 使用者專區 aos-user | 沒裝：沒有 `~/.aos/user`、沒有 `ws/tools/aos-user` | 要的話從家機抄（repo 在 `d5f47c890` 裡找不到 aos-user 這支工具的原始碼，只有 archive 舊版與 `knowledge/aos/user_zone.json` 說明） | AGENTS.md 鐵律 2、common/user「問他的題目寄進使用者專區」 | 公司樹裡的 agent 沒辦法 `aos-user send` 問使用者 |
| 11 | `~/aos-home/env.sh` | 跟 repo `proto8/extras/aos-home/env.sh`（`d5f47c890`）逐字相同 | 不用改 | — | — |
| 12 | `~/.local/bin` | 少 `aos-asuser aos-comm aos-json-view aos-kit aos-share aos-tree-start` 六條連結；`aos-llm-kernel` 還連著 repo 裡未追蹤的殘留夾 | 跑一次 `~/repo/aos/proto8/install.sh` 補連結；`aos-llm-kernel` 已被 `726f73952` 移除，連結要不要搬走待使用者定 | tree-swap-1114 換後清單 3、8；SESSION-LOG 11-14 ④ | 新指令打不到；起樹用 `aos-tree-start root` 會擋繼承的 `AOS_*`（`41f06e9a4`），沒裝就只能照舊 `aos-exec root` |
| 13 | 起樹 | — | 照舊 `cd ~/aos-home && source env.sh && aos-exec root`；起完 `aos-daemon-ctl -d ~/aos-home/ws/.stack ls` 看九列 | aos-teams/06 | — |

## 沒驗到、沒把握的

- 沒起 daemon，新 daemon 讀舊 `procs_state.json`、新 lib 配舊定義跑一輪，都沒實跑過；起樹後第一輪才知道。
- 舊 C++ 九支沒有備份，退回只能用舊 commit 重編，確切是哪個 commit 不確定（見上）。
- 第一次 build 失敗我判斷是背景起法的問題，第二次換了起法就過了；沒有回頭去證明第一次真的是被斷掉的（看時間：08:41:43 開始、08:41:45 失敗，正好是叫它的 `wsl` 結束的時候）。
- 第 5 項 4、7 兩條，codex 定義要不要也加 brain_notify、compact_hook 要不要開，家機那邊也還沒定。
- 本紀錄檔沒有加進 `proto8/thinking/2026-11/` 的日索引與月索引（任務書只准寫這一個檔）。

## 設定更新（第 1～6 項）

使用者 11-17 看過第 5 節清單後回「改 1～6 項」。09:38 做完，樹全程停著（動手前、做完後 `pgrep -u $USER -af aos-daemon`／`aos-loop` 都只抓到自己那行；兩個 `state.json` 都是 `stopped`；殼裡沒有 `AOS_*`，腳本開頭照樣逐一 unset）。

**結論**：六項都改了，沒有哪份跳過。第 1、2 項 7 份都改；第 3～6 項只改 4 份 claude；codex 3 份只改第 1、2 項。每份的現值都跟清單一樣（600000／900000、沒有那四個 hook、沒有 live_mail），沒有遇到要跳過的格。

### 改了什麼

| 定義 | `cli.json` | `loop.json` | `hooks.json` |
|---|---|---|---|
| `agents/eca_main` | `timeout_ms` 600000→0；加 `"live_mail": true`（diff 3 行） | `exec.timeout_ms` 900000→0（diff 2 行） | 加 `brain_notify`、`screen_linger_start`、`screen_linger_stop`、`context_wrap`（diff 30 行，全是新增） |
| `agents/ops-agent` | 同上（單行檔，diff 2 行） | 同上（2 行） | 同上（30 行） |
| `ws/defs/agent` | 同上（3 行） | 同上（2 行） | 同上（30 行） |
| `ws/defs/me-agent` | 同上（單行檔，2 行） | 同上（2 行） | 同上（30 行） |
| `ws/defs/codex` | `timeout_ms` 600000→0（2 行） | 同上（2 行） | 沒動 |
| `ws/defs/gpt-price` | 同上（單行檔，2 行） | 同上（2 行） | 沒動 |
| `ws/defs/gpt-soap` | 同上（單行檔，2 行） | 同上（2 行） | 沒動 |

- 改法：文字層替換（不重新 dump，原排版、鍵順序、結尾換行都不變），寫同夾暫存檔再 `os.replace`，權限照舊 644；寫之前先把改完的內容解成 json，跟「原檔解出來再改那幾個鍵」逐鍵比對（值與順序都要一樣）才寫。
- 四個新 hook 是從 `templates/eca-claude/hooks.json` 原文整段抄的（含它的排版），放在 `timer` 前面，順序同範本：brain_notify、screen_linger_start、screen_linger_stop、context_wrap。context_wrap 是 `every_ms` 5000、`config: {"percent": 35}`。
- `live_mail` 範本裡沒有，放在 cli.json 最後一個鍵（多行的兩份另起一行，單行的兩份接在同一行）。
- `hooks.json` 的 `description` 沒改：新範本那段說明多寫了 brain_notify／screen_linger／context_wrap 的用法，舊定義還是舊說明。只影響說明文字，不影響行為。
- `config.window` 沒設：五格 claude stack（eca_main、ops-agent、me-agent、repo-aos、wf-agent）的 `claude/live.jsonl` 都記過 `contextWindow`（跑過 `-p`），照 `lib/agent/context_use.py` 的說法，沒給 window 就用 live.jsonl 舊 result 記的，所以不用設。

### 備份與退回

- 備份：`~/aos-home/backups/defs-1117/<定義名>/`（`eca_main`、`ops-agent`、`agent`、`me-agent`、`codex`、`gpt-price`、`gpt-soap`），共 18 檔，`cp -p` 原樣，清單與 sha256 前 16 碼在 `~/aos-home/backups/defs-1117/FILES.txt`。
- 退回（樹停著時）：照 FILES.txt 每行把左邊的備份 `cp -p` 回右邊的原位置，例 `cp -p ~/aos-home/backups/defs-1117/eca_main/hooks.json ~/aos-home/agents/eca_main/hooks.json`。注意 `ws/defs/agent` 的備份夾叫 `agent`。
- 腳本留在 WSL `/tmp/d1117_backup.sh`、`/tmp/d1117_edit.py`、`/tmp/d1117_verify.sh`，沒刪。

### 驗了什麼

- 18 檔都重新讀成合法 json；`diff` 對備份只有上表那幾行；沒有殘留暫存檔。
- 唯讀載入（`PYTHONDONTWRITEBYTECODE=1`、沒設 `AOS_STACK`）：`lib/agent/cli_cfg.load_cfg` 七份都過（claude 四份讀到 `timeout_ms=0`、`live_mail=True`；codex 三份 `timeout_ms=0`）；`lib/agent/hooks.load`（stack 給不存在的路徑＝只讀定義那份）七份都過，claude 四份是六個 hook，codex 三份還是 timer、mail_notify。
- `lib/aos/defs/_entry` 的 `check`（即 `agent_def check` 轉叫的那支）七份都 `{"problems": []}`、退 0。這支查的是 README、_metainfo、interfaces、tools，不查 cli／loop／hooks 的內容。

### 沒做、沒驗、要使用者知道的

- **沒驗到實跑**：樹沒起，新 hook 真的觸發（context_wrap 到 35% 寄收尾、screen_linger 收畫面、brain_notify 寄信）、live_mail 中途收信、逾時 0 都要起樹後才看得到。loop.json 由 C++ aos-loop 讀，沒有不起樹的檢查可跑，只驗了 json 與值。
- **brain_notify 可能寄不出去**：它把 BLOCKED 信寄到 `$AOS_NOTIFY_BOX`，沒設只印 warning、不寄。公司樹的 `env.sh`、兩份 `procs_state.json` 都沒有這個變數（`subagent add` 才會自動設成上層信箱，這幾隻是 daemon 表上的列）。要真的收到信，得另外給這幾列設 `AOS_NOTIFY_BOX`——沒動，待使用者定。
- 四個 hook 的 handler（`lib/agent/brain_notify`、`screen_linger`、`context_wrap`）在早上換好的 lib 裡都有；不用加工具包、不用動 `tools.json`。
- `templates/` 底下只有 `eca-claude`，沒有 codex 的 eca 範本，所以沒有「codex 範本帶了哪個 hook」可列；codex 三份照家機做法沒加第 3～6 項。
- 第 5 節第 7 項（compact_hook＋cli.json 的 `settings.hooks`）沒做，不在這次範圍。
- stack 底下沒有自己的 `hooks.json`／`cli.json`，所以這次改的定義起樹後就是生效的那份（repo-aos、wf-agent 共用 `ws/defs/agent`）。
