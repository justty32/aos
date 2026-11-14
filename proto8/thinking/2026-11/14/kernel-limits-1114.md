# kernel 限資源施工（線限 11-14）：非 C++ 部分的三份圖紙寫好（B1 kernel 站附限制、B2 aos-share、B3 aos-asuser＋aos-sandbox 認 sub:N），暫存樹與接 LiteLLM 的 gpt 隊搭好、試問 sol 通；還沒派工、還沒寫碼，交棒給 ok-limits

← [11-14 日索引](README.md)｜計畫 [kernel-limits-plan](../13/kernel-limits-plan.md)（K1～K18 全已裁）｜圖紙夾 [kernel-limits-1114/](kernel-limits-1114/)

## 授權與指示（頂層轉，逐字）

- 「你列的這些都可以。開始推進吧」——段 2、段 3 的非 C++ 部分可以做；段 1、段 4（C++）今天不做；段 5 不做；有 root 才能做的不做。
- 「跑一整晚...我們現在就用本地litellm proxy，使用gpt」「作爲我們要的實作」——施工隊改成暫存樹裡的 agent-fsm 接 LiteLLM。
- 「然後每條線都讓opus作爲協調，要規劃就走正規規劃流程」
- 「蒐集資料和實作都可以試試看交給sol等」「不要走codex」「不要terra，盡量用sol，把sol作爲sonnet來用」
- 「然後有需要的，可以自己掛kernel或agent。」
- 「多掛幾隻opus eca，把各條線分給他們」——本線交棒給 opus eca `ok-limits`。

## 做了什麼

1. 讀完計畫 01～09，對照現有程式（`lib/aos/kernel/procs_rules.py`、`letters.forward`、`aos-daemon` 的 `procs.cpp` `is_once`／`check_limits`、`aos-sandbox` 的 `build`），把非 C++ 的部分寫成三份施工圖紙（給 gpt 隊照做，不含設計決定）：
   - [B1-limits-rule](kernel-limits-1114/B1-limits-rule.md)：`limits_rule.py`（`limits.{default,max,by_sender}`、`users`、`groups`）、`procs_rules` 在 `load`／`dispatch` 接上、測試 13 類、README 鍵表＋一節。
   - [B2-aos-share](kernel-limits-1114/B2-aos-share.md)：六種 KIND（team／read／key／work／drop／stack，對 08 的 G1～G6，一台 daemon 一個群組）、`sub:N` 換真號、祖先警告、錯誤代號、測試。
   - [B3-aos-asuser](kernel-limits-1114/B3-aos-asuser.md)：fork＋管子＋`newuidmap`／`newgidmap`、換身分、環境白名單、`--git-safe`、`--fix`（G7）；aos-sandbox 的 `user: "sub:N"` 前面接 `aos-asuser --env-all sub:N --`。
2. 搭暫存樹 `~/code/limits-1114/`（見下面交棒一節），掛上 llm-gpt kernel，`aos-llm ask` 對 `sol-high` 回 `OK`。
3. 沒派工、沒寫任何程式碼、沒改 `proto8/lib`／`proto8/cmd`；活樹沒碰（只唯讀抄了 `~/aos-home/defs/{gpt-lead,gpt-worker,shared}` 與 `kernels/llm-gpt`）。

## 圖紙裡的實作級代定（照計畫推得出、計畫沒逐字寫的）

- **D1** proc 自帶 `limits` 時，`max` 有、自帶沒寫的鍵**補成 max** 並記進 `limits_clamped`（計畫「逐鍵取自帶與 max 較小的」，沒寫＝無限大，取小＝max）。不補的話寫一個鍵就能躲掉 max。
- **D2** 起點：沒帶或拿掉 user／groups 後是空＝用 default（＋by_sender）；帶了＝只用自帶的、不跟 default 合併（同 daemon「列的 limits 整份取代預設」）。
- **D3** `limits: {}` 在開了規則的站上＝用預設（K2）：沒有 default 時把 `limits` 鍵拿掉，讓 daemon 用它自己的預設。
- **D4** 字串／陣列寫法的 proc 要加份額時包成 `{"exec": 它, "limits": …}`（daemon 09 份額本來就這樣講）。
- **D5** proc 寫成 `$` 開頭的指示詞＝`BodyBad` 拒信（站解不開 `$ref`，放過去就能繞過份額）。
- **D6** `by_sender` 只認完全相等的寄件人字串，不收萬用字元；`users` 用 `fnmatchcase`、照表順序第一個對到的。
- **D7** `groups` 進信時是號碼陣列 `limits.groups`（daemon 照號 `newgidmap`）。
- **D8** aos-asuser 不給 `--group` 時主群組＝ns gid N（真 subgid 起點＋N－1），不用使用者的主群組（K6 不採 A）；`--fix` 對整段 subuid／subgid、不換 uid。
- **D9** aos-asuser 預設環境白名單＝aos-sandbox 預設那份＋`TERM`＋全部 `AOS_*`，`HOME=/nonexistent`；aos-sandbox 叫它時帶 `--env-all`（bwrap 會再清）。

## 已知的坑（施工前要知道）

- **K-a 今天的 daemon 不認新東西**：`limits_clamped` 一加到 exec 型 proc 上，`is_once` 會把它當成 loop 設定（`procs.cpp:205`，多一個鍵＝loop）；`limits.groups` 會 `CfgBad`（`check_limits` 只認五鍵＋user）；`user: "sub:N"` 起不來（`LimitBad … no such user`）。所以 B1 進 main 後，daemon 段 1、段 3 換上之前，站上 `max` 只能在夾不到的情況用、`users` 不填 `sub:N`、不用 `groups`。B1 的 README 那段逐字寫了這件事。
- **K-b 沙箱裡做不了真測試**：施工隊（sol）的 shell 在 bwrap（user ns）裡，`setfacl` 對外來 gid 會 Invalid argument、`newuidmap` 不行。B2、B3 的圖紙已要求這幾例偵測後 skip，**隊長要在沙箱外重跑全套**（暫存樹的 `work/` 上，經 `clean.sh`）。
- **K-c aos-sandbox 是活的**：`~/.local/bin/aos-sandbox` 連到 repo，存檔即生效（gpt 隊的 shell 工具就靠它）。B3 改它的那步放最後一個 commit，動手前先回報頂層等放行（aos-teams/06 硬規則 5）；今天沒有任何設定寫 `sub:N`，影響理論上是零。
- **K-d 新指令要 install**：`aos-share`、`aos-asuser` 要跑 `proto8/install.sh` 才進 `~/.local/bin`（碰使用者環境，列給使用者）；aos-sandbox 的 `sub:N` 要 PATH 上找得到 aos-asuser。
- **K-e zsh 不切字**：Bash 工具的殼是 zsh，`for f in $files` 不會照空白切（搭樹時栽一次）；搭樹與起程序一律 `bash -c` 或經 `clean.sh`。
- **K-f root 的 .env 會蓋 agent 的 AOS_LLM_KERNEL**：`.env` 是「殼裡有就不蓋」，根先設了，agent 定義的 `.env` 就失效；暫存樹的根 `.env` 已直接改成指到 llm-gpt。
- **K-g `aos-tree-start` 不在 PATH**（沒 install），改用 `aos-exec --stack stacks/root defs/root`（經 `clean.sh`，環境已清）。

## 需要使用者自己動手的系統設定

- 不需要改 `/etc/subuid`、`/etc/subgid`：家機已有 `lorkhan:100000:65536`。公司 WSL 要另查（沒有就要 root 加一行 `lorkhan:100000:65536`）。
- 圖紙做完後：`proto8/install.sh` 一次（讓 `aos-share`、`aos-asuser` 進 `~/.local/bin`）。
- 活樹權限收緊（`~/aos-home` 755→750 等）照計畫段 3 另派，不在這裡。

## 交棒給 ok-limits

**做到哪**：三份圖紙定稿（B1～B3）、暫存樹與 gpt 隊的定義搭好、llm-gpt 試問通；**還沒派工、沒有任何程式碼**。正規規劃流程那條：計畫本身 11-13 已走完（fable 設計、K1～K18 使用者裁），這三份是 opus 細化到檔的施工圖；圖紙送 Argon 審**沒做**，要照「正統規劃流程」就先送 Argon 審 B1～B3 再派。

**commit**：本節與三份圖紙同一個 commit（雜湊見 `git log --oneline -- proto8/thinking/2026-11/14/kernel-limits-1114.md`）。日索引那一列是線星 `68ee51c7b` commit 時連同工作樹一起帶進 main 的（三條線同時改同一個檔），內容就是本線寫的那列。

**暫存樹** `~/code/limits-1114/`：

| 路徑 | 是什麼 |
|---|---|
| `base-commit.txt` | 抄的時候的 HEAD：`90d9a46d0` |
| `src/` | `git archive` 那個 commit 的整份 repo；`src/proto8` 是暫存樹的 `AOS_HOME`（凍結，跑樹用，不改） |
| `work/` | 同一份再抄一次、`git init` 了一個基線 commit（只在暫存樹裡，不是 main 的分支）＝**gpt 隊的工作 repo**；守門與沙箱只准寫 `work/proto8`、`work/wf`。三份圖紙**還沒抄進去**，派工前抄到 `work/proto8/thinking/2026-11/14/kernel-limits-1114/` 並在 work 裡 commit 一次 |
| `clean.sh` | 清掉全部 `AOS_*`、設 `AOS_HOME=src/proto8`、cd 到 `tree/` 再 exec；起任何東西都經它 |
| `tree/defs/root` | daemon-root 範本，`.env` 的 `AOS_LLM_KERNEL` 改成 `tree/stacks/root/procs/llm-gpt` |
| `tree/defs/gpt-lead`、`gpt-worker`、`shared` | 活樹 11-13 那兩份 gpt 隊定義的抄本，路徑全改成暫存樹（`grep aos-home` 為 0）；lead 腦 `astra-high`、工人 `sol-high`（使用者「盡量用 sol」：要改 lead 也用 sol，改 `tree/defs/gpt-lead/llm.json` 成 `{"model": "sol-high"}`） |
| `tree/kernels/llm-gpt` | llm kernel 抄本；`budget.senders` 只留 `tree/stacks/root/procs/gpt-lead` 300 次 |
| `tree/teams/L1` | 隊夾（`tickets/`、`logs/`、`mailbox/{tmp,new,cur}`、空的 `status.md`）；**`blueprint.txt` 還沒寫** |
| `tree/stacks/root` | 根 daemon 的 stack |
| `root.log`、`root.pid`、`ask.json` | 根的輸出、根的 pid、試問用的 body |

**我起過的程序**（交棒時全收）：

| pid | 是什麼 | 狀態 |
|---|---|---|
| 154506 | `aos-exec --stack stacks/root defs/root`（暫存樹的根，記在 `root.pid`） | 用 `aos-daemon-ctl -d ~/code/limits-1114/tree/stacks/root shutdown` 收 |
| 154514 | 它底下的 aos-daemon | 同上一起收 |
| 154516、154517 | `_clock`、`_sweeper` | 同上 |
| 155359 | `llm-gpt`（`--auto-restart`，記在根的表上） | 同上；下次起根時會自己醒 |

活樹的兩台 daemon（開工前 `pgrep` 看到 37179、37183）沒碰。

**重新起暫存樹**：

```sh
L=~/code/limits-1114
$L/clean.sh aos-exec --stack stacks/root defs/root > $L/root.log 2>&1 &   # 背景，記 pid
$L/clean.sh aos-daemon-ctl -d stacks/root ls        # _clock、_sweeper、llm-gpt 都 running（llm-gpt 睡下的會自己醒）
```

**下一步**：

1. （照正統規劃流程）B1～B3 送 Argon 審，逐條採納或不採納後改圖紙；方向性的上報頂層。
2. 圖紙抄進 `work/`、work 裡 commit；寫 `tree/teams/L1/blueprint.txt`（一行指到 B1，做完再換 B2、B3；或一份總圖紙列三份）。
3. 起 lead：`$L/clean.sh aos-agent -d stacks/root ctl add --name gpt-lead -w teams/L1 defs/gpt-lead`、`$L/clean.sh aos-agent -d stacks/root goal -t gpt-lead set "Do the blueprint named in blueprint.txt …"`；背景看門看 `teams/L1/mailbox/new/`。
4. 收 DONE 後在沙箱外重跑三份圖紙的測試（`work/` 上；B2、B3 的真跑例子只有沙箱外會跑），讀 diff 對圖紙；把 `work/` 裡新增／改的檔抄回 repo（先 `git status` 看線框、線星有沒有沒 commit 的同一批檔），`index_gen --apply`、逐檔 commit。B3 的 aos-sandbox 那步最後做、先回報頂層。
5. 撞到的 aos／gpt 隊問題記進本檔新一節（這是使用者要的產出）。

## ok-limits 接手紀錄（11-14）

### 隊形

- 工人：agent-fsm sol（腦 `sol-high`，經 LiteLLM），定義在 `wf/temp/ok-limits/defs/sol`；system text 寫進必讀清單（知識庫 `_description.json` 先讀、AGENTS.md、user.md、aos-teams.md 與 06、07）與硬規則重點（不動活樹、測試只經 `clean.sh`、不 push、不 commit、不刪檔、只 kill 自己記的 pid、只動任務列的檔、輸出英文）；拿掉範本的刪檔工具。每份任務書開頭附同一份必讀清單（`wf/temp/ok-limits/notes/brief-header.md`）。
- 沒走前任設計的 gpt-lead／gpt-worker 隊（`tree/defs/gpt-lead`）：改成 ok-limits 直接派單隻 sol，設計判斷留在 ok-limits（照 07 的 11-14 補充）。
- 命名：第一隻叫 `sol-lim1`（規矩出來前掛的）；之後一律 `ok-limits-<角色>-<n>`（頂層 11-14 通知）。

### Argon 審 B1～B3 的採納表

原文 `/tmp/ok-limits-argon/argon.out`（暫存，不進 repo）。

| # | 圖紙 | Argon 說 | 採納 | 怎麼處理／理由 |
|---|---|---|---|---|
| 1 | B3 | newgidmap 後 `setgroups([])` 必敗 | 不採 | 家機實測 newgidmap 後 `/proc/<pid>/setgroups` 是 `allow`、成功；照留，失敗就報 `NsFailed setgroups`、不准略過（B3 §6） |
| 2 | B2 | 有 ACL 時 `stat` 群組位＝mask | 採 | 測試改以 `getfacl -n` 為準、stat 期望值改 640／770（B2 §6、§7） |
| 3 | B2 | `setfacl -R -d` 遇普通檔報錯 | 不採 | 家機實測退 0（檔被略過） |
| 4 | B2 | drop 預設 ACL 缺 `X`、mask 被清 | 採 | 預設 ACL 改 `rwX`、mask 用 `wx`；README 寫寄件端要給群組位（B2 §2、§7） |
| 5 | B1 | 自帶 limits 繞過 default／by_sender；沒帶時被 max 標 `limits_clamped` | 不採 | K 裁定就是「寫了就整份取自帶、再被 max 夾」；上限靠 `max`，default／by_sender 本來就只是預設不是上限。max 補上沒寫的鍵也算「被夾」，標出來對讀者有用 |
| 6 | B1 | users 沒對到就回宿主 uid | 部分採 | 不強制 `"*"`（站可以只隔離部分名字）；README 加「users 要兜底」一句（T1b） |
| 7 | B2 | getfacl 印 `user:`／`group:` 不是 `u:`／`g:` | 採 | B2 §3 改寫比對規則 |
| 8 | B3 | fork 後沒關用不到的管子端 | 採 | B3 §2.1 第 5 步 |
| 9 | B3 | `--fix` 單檔與 PathMissing 判斷 | 採 | B3 §2.2 |
| 10 | B1 | load 選填與驗證順序沒寫 | 採 | T1b 第 1 點 |
| 11 | B1 | 只寫 users 會蓋掉 daemon 預設份額 | 採（文件） | README 加一句（T1b 第 2 點）；daemon 端逐鍵補預設是 C++，不在今天 |
| 12 | B3 | 測試 5 漏 `sub:N`、偵測過嚴 | 採 | B3 §5、§6 |
| 13 | B2／B3 | subid 檔註解行、前導 0 | 採 | B2 §7、B3 §6 |
| 提案 2 | B1 | 站上嚴格驗 own 的鍵與值 | 不採 | daemon 本來就驗；站上重驗兩份規則會分歧 |
| 提案 3 | B2 | 每次 setfacl 都顯式帶 `g::`、`m::` | 不採 | 第 2、4 條改完已經對；多寫反而跟 chmod 打架 |
| 提案 5 | B3 | 多群組 | 採（文件） | README 寫只換主群組，多群組歸段 3（B3 §6） |

### B1（kernel 附限制）

- sol（`sol-lim1`）照 B1＋修正單 T1b 寫四個檔：`proto8/lib/aos/kernel/limits_rule.py`（新）、`procs_rules.py`（只在 import、load、dispatch 三處接）、`tests/test_limits_rule.py`（新，21 單元＋5 整站）、`README.md`。
- 它回 BLOCKED：暫存樹 `work/` 是 `git archive` 出來的，沒有建好的 `proto8/impls/*/bin`，整站測試找不到 `aos-post`。它沒越界自己補，對。ok-limits 把 repo 裡建好的 bin 抄進 `work/`（`cp -a`，只讀 repo），重跑 kernel 全部測試 105 個全綠。
- ok-limits 讀過 diff 對圖紙：照規格，無退件。抄回 repo（base `90d9a46d0` 到 HEAD 之間 kernel 夾沒有別人改）。
- **坑**（給之後的暫存樹）：`git archive` 不帶 build 產物；起暫存樹時要順手抄 `proto8/impls/*/bin`，不然整站測試全掛。

### sol 有沒有真的讀必讀（使用者 11-14「這些agent，都要讓他們知道aos體系，和wf規矩。」）

| 任務 | 照讀了沒（工具紀錄） | 回報裡的證據 | 表現差異 |
|---|---|---|---|
| T1（B1） | 有：開頭依序 `read` 了 `_description.json`、AGENTS.md、user.md、aos-teams.md、06、07，之後還自己去讀 `kernel.json` 與 `conventions.md` | 六份各寫一句相關點（例：「kernel 的拒絕是決定，不繞過；活樹只讀」「施工隊只照圖紙實作，不自行改設計」） | 有：缺執行檔時沒自己補檔、沒改舊測試、沒跳測試，照「只動四個檔」停手回 BLOCKED；開工收尾都比對活樹 daemon 與頂層 stack，看到頂層 stack 多了 `autoreply`、`quiet`（頂層裝 quiet）也照規矩停手回報而不碰。缺點：第一輪只回計劃不動手，要第二份任務書明說「不要只回我會做」才做完 |

### 換樹要帶的檔（頂層 11-14：lib 換樹才生效）

B1 進活樹 `~/aos-home` 要帶這兩支：`lib/aos/kernel/limits_rule.py`（新）、`lib/aos/kernel/procs_rules.py`。README 和測試不用帶。kernel 站沒寫 `limits`／`users` 時，轉寄出去的 body 跟以前一樣，所以帶過去之後，沒開新鍵的站不受影響。
