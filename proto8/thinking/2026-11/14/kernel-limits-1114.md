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

### B2、B3（11-14 上午）

- B2 `aos-share`：`51dc8b931`；B3 前半 `aos-asuser`：`08ae713d8`；B3 後半 `aos-sandbox` 認 `sub:N`：`432fe6f83`。都由 sol 寫碼、ok-limits 在沙箱外重跑測試並讀 diff，頂層准後用 commit-request 交件。
- 端到端驗收（ok-limits 在家機上，用 repo 版 aos-sandbox）：設定 `{"user": "sub:5", "rw": [D]}`。
  - 沙箱裡 `id` 是 `uid=5`；
  - 寫進 D 的檔，外面看是 `100004:100004`；
  - `ro: [~/.ssh]` 時 bwrap 報 `Permission denied`，subuid 走不進使用者 700 的夾，這是預期的結果。
- **缺口：`aos-asuser` 不在 PATH 上**。`~/.local/bin` 只連了舊的指令，沒有 aos-asuser，所以 `user: "sub:N"` 會報 `CommandMissing aos-asuser not found on PATH`。驗收時是手動把 `proto8/cmd/aos-asuser/bin` 放到 PATH 前面。要正式能用，得在 `~/.local/bin` 加一條連到 `~/repo/aos/proto8/cmd/aos-asuser/bin/aos-asuser` 的連結（`aos-share` 同理）。這是動使用者的環境，交給頂層或使用者決定。
  - 11-14 09:51 頂層已把 aos-asuser、aos-share 連進 `~/.local/bin`。ok-limits 不改 PATH 重跑一次：`which aos-asuser` 找得到，`aos-sandbox {"user": "sub:5", "rw": [D]}` 退 0，`id` 是 `uid=5`，寫出的檔是 `100004:100004`，不再出現 CommandMissing。
- 交叉審（sol-1 審 aos-share、aos-asuser）進行中，結果出來後補在這裡。

### B4（段 1 daemon 收緊）圖紙與 Argon

- 事實：sol-3 蒐集 `~/code/limits-1114/notes/G1-facts.md`，計劃寫的行號都還對得上。暫存樹 build 用 42 秒；CMake 把 bin／lib 寫回原始碼夾，所以要整份抄進 `build/source` 再編。
- 圖紙：[B4](kernel-limits-1114/B4-daemon-tighten.md)。設計判斷：
  - `limits_max` 超過了就拒，不夾，丟 Error 進 reconcile 既有的單列 catch；不放進 read_procs，免得整封信被拒或整台 daemon 退出。
  - `limits_` 必須涵蓋 max 的每個鍵。
  - 列上寫了非空 `limits`，數字鍵照舊整份取代預設。
- Argon 採納表（原文 `/tmp/ok-limits-argon2/argon.out`）：

| # | Argon 說 | 採納 | 怎麼處理 |
|---|---|---|---|
| 1 高 | 測試 2 的 shell 沒用 exec，訊號被 shell 轉成退出碼 153 | 採 | 測試一律用 exec；docs 寫「看的是直接子行程」 |
| 2 高 | 整份取代會洗掉預設 user／沒封頂的鍵；fork 會讓 cpu 重新起算 | 部分採 | 預設 user 會補上（7.2-1）。沒封頂的鍵：寫進 docs，不想被取消就放進 limits_max。改成逐鍵合併要另裁 K，這次不改。fork、多檔的邊界歸段 4 cgroup，寫進 docs |
| 3 高 | 接回的 running 列不檢查 limits_max | 採（文件） | 照現狀，只在重起時檢查，寫進 docs |
| 4 高 | 驗證順序讓 user 的訊息到不了；巡鍵順序沒定 | 採 | 先擋 user，再呼叫 check_limits；照 KEYS 順序巡 |
| 5 中 | daemon 自己的 hard 比寫的小時，子行程 `_exit(1)`，被誤標 suspect | 採（連提案 1） | 父行程先用 getrlimit 預檢，超過就丟 LimitBad 走 catch |
| 6 中 | 測試的跑法、例 3、7、8、9 不穩 | 採 | 7.3 逐條改；加例 10 驗 prlimit |
| 7 低 | 註解、:202 重設、docs 01／02、知識庫源頭 | 採 | 範圍加檔；知識庫改 repo 裡的 `proto8/knowledge` 源頭，不動活樹 |
| 提案 2 | 子行程啟動失敗改用別的退出碼 | 不採 | 預檢後已經少見；改退出碼會動到別的契約 |
| 提案 3 | 預設 user 補上 | 採 | 同第 2 條 |
| 提案 4 | K11 警告每列只印一次 | 採 | `procs_warned` |
| 提案 5 | rlimit 與 cgroup 對照表 | 採 | docs/09 |

### B5（段 4 cgroup 可選）圖紙與 Argon

- 事實：sol-4 蒐集的 `~/code/limits-1114/notes/G4-facts.md`，在家機 user slice 底下只用 transient scope 實測，收尾確認已消失。跟 07 對不上的有 5 處：
  1. 有 swap 時 `memory.max` 不會 OOM；
  2. 沒包 systemd-run 的格不一定不可寫；
  3. 控制器要逐層開；
  4. stop 實際的路徑跟 07 寫的不同；
  5. `launch.json#/wrap` 沒有實作。
- 圖紙 [B5](kernel-limits-1114/B5-daemon-cgroup.md)，ok-limits 的設計判斷：
  - `mem_total_mb` 連 swap 一起封（`memory.swap.max=0`）；
  - stop 原本的流程照舊，最後補一記 `cgroup.kill`；
  - 每次 launch 都重建格，讓計數歸零；
  - 這次不做 wrap，由起樹的人自己用 systemd-run 包。
- Argon 採納表（原文 `/tmp/ok-limits-argon3/argon.out`）：

| # | Argon 說 | 採納 | 怎麼處理 |
|---|---|---|---|
| 1 高 | 家機上「不帶 Delegate 的 scope」一樣可寫，例 3 不會失敗 | 採 | 改用缺控制器、EBUSY 兩種確定會失敗的前提 |
| 2 高 | `prep_limits` 會對 resource -1 呼叫 getrlimit | 採 | 跳過 |
| 3 高 | bash 遇到 EAGAIN 會退避，例 2 會卡住 | 採 | 改用 python 的 os.fork |
| 4 高 | 探測太早（在鎖之前）；還原順序會撞上 no-internal-process 規則 | 採 | 移到 check_running 之後；還原改四步順序 |
| 5 高 | cgroup.kill 是非同步的，rmdir 會跟行程退出搶；看 cgroup.procs 會漏掉子格 | 採（連提案 2） | 一律看 `populated`；寫成共用函式 `cgroup_empty_cell` |
| 6 高 | 接回的列主行程先退時，孤兒收不到 | 採 | `alive()` 的 `!own` 分支也收 |
| 7 高 | 測試有殘留 failed unit 的風險，例 1、4、5 的寫法有問題 | 採（連提案 3） | `--collect`、`reset-failed`、ScopedDaemon；例 4 拆兩列；例 5 加 ready |
| 8 中 | 跟 B4 銜接處 5 個地方沒定死 | 採 | 8.2、8.3 寫死；搬格失敗改 `_exit(126)` |
| 9 中 | 同 uid 的 proc 改得動自己那格 | 採（文件） | docs/09 寫邊界；真的要防得等段 3 |
| 10 低 | 解指示詞的鍵清單、路徑正規化 | 採 | 8.1 |
| 提案 1 | 父子兩邊都寫 cgroup.procs | 不採 | 子行程在 exec 之前就進格，使用者的程式碼碰不到那個空窗；改用 126 避開誤判 |
| 提案 4 | 同格重起要冪等 | 採 | 8.1 |
| 提案 5 | unshare(CLONE_NEWCGROUP) | 不採 | 只是把路徑藏起來，不是防線；超出範圍 |

### R1 審查 → T5 修補（已 commit 0586b0420）

- R1 是 sol-2 審 aos-asuser／aos-share 的結果，見 `~/code/limits-1114/notes/R1-review.md`：1 高、3 中、2 低。ok-limits 全部裁定要修，交給 sol-1 施工（T5）。
- **高**：`--fix --recursive` 給符號連結路徑加尾斜線（`link/`），會跟著連結修到連結外面去。修法是 `--fix` 的路徑先 `os.path.normpath`，再做所有檢查。
  - 有兩個測試鎖住這條，以後不會退回去：`test_real_fix_symlink_with_and_without_trailing_slash`、`test_fix_normalizes_symlink_before_checks`。
  - 另有 `test_fix_recursive_repairs_root_and_does_not_follow_symlink` 確認遞迴時不跟著連結走。
- **中**：
  - 寫成功位元組時遇到 BrokenPipe → 等子行程，回它的碼；
  - 訊號處理在 fork 之後馬上裝好，finally 裡還原；
  - aos-share 檢查上層目錄時 getfacl／stat 失敗 → 只 warning「cannot check」，不再 exit 1。
- **低**：subid 範圍檢查到 2**32-2；NotADirectoryError → PathMissing。兩處原本會丟 traceback。
- 測試：repo 裡 asuser 20、share 19 全綠（ok-limits 自己重跑過）。頂層 11-14 准，0586b0420。這兩支已經連進 ~/.local/bin，所以 commit 後立刻生效。

### 使用者裁定：limits 整份取代（11-14，選 a）

列上有寫非空 `limits` 時，照舊整份取代預設值，不做逐鍵合併，也不另開 K 題。B4 的文件要寫明兩件事：要保留的鍵放進 `limits_max`；在列上寫 `limits` 時，要的鍵都寫全。已寫進 B4 第 8 節。

### B4 施工前更正

sol-3 對照程式碼後回報 BLOCKED：圖紙把 `reconcile.cpp:202`（`refresh()` 的 catch）誤認成第二條起動路徑。實際起動路徑只有 `start()` 一條。更正寫在 B4 第 8 節：只在 `start()` 的 try 裡檢查一次，`refresh()` 不動。這是 07「圖紙跟現況矛盾時回報，不邊做邊定」的實例：sol 停下來回報，設計由 opus 改。

### B4 完工（暫存樹 → repo，等頂層准 commit）

- sol-3 照第 8 節施工，回報 DONE：新測試 12 項、全套 102 項全綠。ok-limits 重跑結果一樣，也看過 diff。
- **漂移合併**：暫存樹的基底比 repo 舊。B4 動到的 16 個檔裡，repo HEAD c4ac4867b 另外改過 5 個。ok-limits 一開始用 `git diff --name-only` 比對，中文檔名被加上引號，所以漏看了兩份 docs，改用 quotepath=false 重比才抓到。這 5 個檔：
  - `adopt.cpp`、`docs/06`、knowledge `cli/daemon.json`：自動合併；
  - `reconcile.cpp`：線雜的 kept_ws 修正，跟 `check_limits_max` 同一個 if，兩邊都留；
  - `N-28`：fixok 的原話，`limits_max` 接在它後面。
- 合完以後，整棵暫存樹的 proto8 同步到 repo HEAD（B4 的檔保留我合好的版本），重建，daemon 全套 103 項（多的那一項是 repo 新加的 test_lifecycle）、py、aos-daemon-ctl 測試全綠。17 個檔已搬進 repo，也已 claim。commit 訊息在 `wf/temp/ok-limits/msg/b4.txt`。
- **換樹時要帶**：
  - 用 repo 原始碼重建 aos-daemon binary，換的時候得停樹（daemon 本身在跑）；
  - 活樹的 knowledge `aos/cli/daemon.json` 要重抄一次。
  - 已經在跑的列不會受影響：接回（adopt）的時候不重新檢查天花板，要等那一列下次重起才套用。

### sbroot（沙箱 root 身分層）端到端驗收（11-14 11:10，ok-limits）

- **前提**：使用者已經跑完 `setup.sh --s6-bin /usr/bin --apply`，頂層核對過：
  - aos-run 的 uid 是 951；
  - `/srv/aos-run` 是 `lorkhan:aos-run 2770`；
  - `/usr/local/bin` 有 s6 四支；
  - sudoers 只有一條 `(root) NOPASSWD: /usr/local/bin/s6-setuidgid aos-run *`。
  - 驗收沒有改任何系統設定。sudo 只用 `sudo -n` 走這條 NOPASSWD 規則，lorkhan 另外那條要密碼的 `(ALL) ALL` 沒有碰。
- **怎麼接**：`user: "aos-run"` 交給 aos-sandbox 時要 root，非 root 跑會得到 UserBad（第 4 項確認過）。所以驗收時由 aos-sandbox 用 `--dry-run` 組出 bwrap 那串 argv（cpu 那項是 s6-softlimit 接 bwrap），再在前面接 `sudo -n /usr/local/bin/s6-setuidgid aos-run`。
- **腳本與結果**：腳本是 `~/code/limits-1114/e2e-sbroot/run2.sh`，輸出在 `run2.out`。檔案放在 `/srv/aos-run/ok-limits-e2e2/`，因為我的家目錄是 700，aos-run 進不去。**11/11 全過**：
  1. `sudo -n s6-setuidgid aos-run id -un` 印出 `aos-run`；
  2. aos-run 讀 `~/.bashrc` 得到 Permission denied；
  3. `s6-setuidgid root` 被 sudo 擋下，要求密碼，換不成 root；
  4. aos-sandbox 拿到 `user: aos-run` 又不是 root 時，報 UserBad；
  5. 沙箱裡是 `uid=951(aos-run) gid=951(aos-run)`；
  6. ro 綁定讀得到；
  7. ro 綁定寫不進去（Read-only file system）；
  8. rw 綁定寫得進去，寫出的檔是 `aos-run:aos-run 644`；
  9. 沙箱裡看不到 `/home/lorkhan`；
  10. 斷網：連 1.1.1.1:53 失敗；
  11. `cpu_s: 1` 經 s6-softlimit，以 aos-run 身分跑空迴圈，退 152（SIGXCPU）。
- **踩到的事，要寫給使用者看**：
  - **lorkhan 不在 aos-run 群組裡。** 群組外的人對目錄做 chmod，kernel 會清掉 setgid 位。第一輪我對子目錄跑了 `chmod 2770`，setgid 就沒了，裡面新建的檔變成 lorkhan 群組，aos-run 執行 probe.sh 被拒（5/11）。我也不能把檔 chgrp 到自己不在的群組。
  - **做法**：在 `/srv/aos-run` 底下只用 mkdir，不對目錄做 chmod，讓子目錄沿用 setgid 帶下來的 aos-run 群組；要給 aos-run 寫的目錄，加 `chmod g+w`（群組留著，只是那一層的 setgid 會掉）。
  - umask 022 建出來的目錄是 2755，aos-run 寫不進去，所以 rw 目錄一定要 `g+w`。
  - 這條規則 setup.sh 跟 aos-sandbox 的 README 都還沒寫。要不要把 lorkhan 加進 aos-run 群組，牽涉 /etc，留給使用者決定，我不動。
- **還沒有接起來的**：
  - aos-sandbox 本身不會組出「前面接 sudo s6-setuidgid」這條鏈，要叫的那一方自己接。
  - daemon 的 `limits.user: "aos-run"` 一樣要 daemon 是 root（段 5，不在範圍）。
  - 這次沒有開新工作，只記在這裡；要不要讓 aos-sandbox 在非 root 時改走 sudo 規則，交給頂層決定。
- **環境**：沙箱裡的 PATH、AOS_* 變數照預設帶進去，值裡有 /home 的路徑，但只有名字跟字串，那些路徑本身沒有綁進去。
- **留下的東西**：`/srv/aos-run/ok-limits-e2e/`（第一輪，setgid 掉了）和 `ok-limits-e2e2/`。照不刪檔的規矩，兩個都留著，沒有刪。

### B5 施工前更正

sol-4 開工前回報 BLOCKED：主行程退 0 的列會從表上移除（`tend.cpp:166` 標成 done，reconcile 接著收掉），8.4 的 procs 例子讀不到 `limit_hit`。裁定生命週期不改，只改測試：procs 那例的主行程改成退 3，退 0 的列不留這兩欄，這條契約寫進 docs/09。寫在 B5 第 9 節。sol-3 在 B4 也是這樣停下來回報、由我改圖紙，這是第二次照 07 的流程走。

### B4 已 commit（f662b9a17）

頂層 11-14 准了。17 個檔走 commit-request 交出，另外它自動重生了 code-map 的 impls.json，沒有 push。送出前比對過：repo 裡的檔跟暫存樹 d981c4e 那份一模一樣，c4ac4867b 之後也沒有別人改過。daemon binary 重建、活樹 knowledge cli/daemon.json 重抄，頂層已經排進今晚的換樹清單。

### B6：aos-sandbox 不是 root 時自動接 sudo 身分層（使用者 11-14 准）

- 使用者經頂層答覆：「沙箱這塊可以走這條」。(a) 准做，條件是規則不符時要清楚報錯，不能默默退回；(b) 使用者自己用 usermod 把自己加進 aos-run 群組。setgid 那段文件已補上「加進群組後就不會有這個問題」。
- 圖紙：[B6](kernel-limits-1114/B6-sandbox-sudo-chain.md)。ok-limits 實測時發現 `sudo -n -l` 不能拿來預檢：因為有 `(ALL) ALL`，查換成 root 也回 0。所以預檢改成真的跑一次 `sudo -n …/s6-setuidgid USER /usr/bin/true`。sudo 放在鏈的最前面，s6-softlimit 接在後面。
- Argon 審稿在跑（`/tmp/ok-limits-argon4`），審完才派 sol 施工。
- Argon（第一次在 headless 模式下要讀檔，被擋掉沒有產出；提示加上「不要用工具」重跑後，審出 9 條）。9 條全採，第 7 條只寫進文件，修正寫在 B6 第 6 節。最重要的幾條：
  - sudo 一律帶 `-n -k`，忽略快取的憑證，免得 `(ALL) ALL` 剛好有快取時被拿來提權成 root；
  - 走 sudo 時用 passwd 擋掉 uid 或 gid 為 0 的帳號，而且只收帳號名；
  - user 加格式檢查，擋掉 `--` 跟換行注入；
  - 預檢的 true 只找 /usr/bin 和 /bin，不照 PATH 找；
  - 找 sudo、檢查環境放到 build() 最後；
  - 假 sudo 的參數位置更正。
- 已派 sol-1 施工（T7，brief 在 `/tmp/ok-limits-T7.txt`）。

### B5 完工（暫存樹 → repo，等頂層准 commit）

- **兩次 BLOCKED**：sol-4 施工時停下來回報兩次，兩次都是圖紙錯：
  1. 退 0 的列會從表上收掉，所以測試要改成退 3（第 9 節）；
  2. 命令列上的屬性名要寫 `TimeoutStopSec`，`TimeoutStopUSec` 是 D-Bus 屬性的名字（第 10 節）。
- **ok-limits 驗收**：重建，再跑 test_cgroup 9/9 全綠；跑全套 112 項，有 2 項 error，都在 test_ctl：
  - `test_agent_phase_body_accepts_exec_rows`
  - `test_agent_off_table_does_not_claim_a_known_failure_disappears`
  - ok-limits 拿 repo HEAD f84462e48 的乾淨複本、清掉 AOS_DAEMON 重跑，這兩項照樣報錯；帶著 AOS_DAEMON 就會過。
  - 原因：線框 039292202 把 aos-agent ctl 改成用 `table_ref()`，測試 mock 的還是 `daemon_path`。跟 B5 無關，另外轉報。B4 驗收時之所以沒看到，是因為那次是在帶著 AOS_DAEMON 的環境裡跑的。
  - `list-units 'aos-limits-test-*'` 是空的。
- **讀過的程式碼**：cgroup.cpp 全檔；child、tend、table、adopt 的 diff。都照圖紙：子行程在 apply_limits 之前先進格，失敗退 126；`limit_hit` 照優先順序判；接回的列也收孤兒；SIGKILL 那步補 cgroup.kill；drop 清整格。
- 20 個檔已搬進 repo，也已 claim；commit 訊息在 `wf/temp/ok-limits/msg/b5.txt`。換樹時要帶的跟 B4 一樣：重建 binary，重抄活樹的 cli/daemon.json。
- **工作區一隻一格**：頂層提醒 sol-1～4 共用同一個 ws，正在施工的兩隻我判斷不搬，因為檔案範圍沒有重疊。以後派任務時一隻一格，規則寫在 `wf/temp/ok-limits/notes/naming.md`。
- **已 commit：1082418f0**（頂層 11-14 准，沒有 push）。test_ctl 那兩項紅燈，頂層轉給 ok-kf 處理。暫存樹另外記了一筆 commit，當作 B6 之後的基底。

### B6 完工（等頂層准 commit）

- sol-1 回報 DONE：24/24 全綠，真的換身分那例印出 `aos-run`，換成 root、nobody 都被拒。ok-limits 在暫存樹和 repo 各重跑一次，結果相同；`/tmp` 底下的 `aos-sandbox-sudo-*` 暫存夾都已收掉。
- **讀過的 diff**：sudo 一律帶 `-n -k`；passwd 檢查擋掉 uid 或 gid 為 0；帳號名有格式檢查；預檢的 true 只從 /usr/bin、/bin 找；sudo 那段放在 build() 最後；乾跑不預檢；`if __name__ == "__main__"`，讓測試能用 importlib 載入。
- README 有一處漂移：其實是 ok-limits 自己在 6679f0171 交的 setgid 段落，暫存樹的 5ff8d2a 沒有收進去，但工作區裡有。比對過，跟 repo 只差 sol-1 這次的改動。
- **注意**：`~/.local/bin/aos-sandbox` 是指到 repo 的符號連結，所以搬進 repo 的那一刻新版就生效了。影響只有「非 root、user 寫帳號名」這一種設定：以前直接 UserBad，現在改走 sudo。已經在申請信裡寫明。
- commit 訊息在 `wf/temp/ok-limits/msg/b6.txt`。
- **已 commit：1fcc33920**（頂層 11-14 准，沒有 push）。新版留著不退：使用者早上答了 (a)，要的就是這個行為。

## 11-14 午：修 wf/advices 的 daemon 類小條（頂層派，使用者准）

挑了三條，都在 daemon與行程.md，動手前已寄給 xiaosi：
1. after_stop 分不出停止原因 → 圖紙 [B7](kernel-limits-1114/B7-stop-reason.md)，交 sol-5 施工（T8）。
2. 子 agent 不知道誰生了它，只做 who 那段。我自己改：`ctl who --json` 和 `ctl state` 的 who 部分加一欄 `notify_box`，只有查自己時才照實給 `$AOS_NOTIFY_BOX`，否則 null，並註明不是身分證明。「表的列記 parent」留給 ok-astra。
3. files／nofile，連帶 cpu_s 的說明。只改文件：subagent、agents_ctl 工具說明和知識庫 aos/agents/subagent 的 limits 例子改用 files，並寫明哪些鍵按程序計、哪些管整隻、沒有總 CPU 的鍵。不加 nofile 別名，因為 limits 鍵有三處各自驗（daemon limits.cpp、daemon_ctl、kernel limits_rule），加別名容易漏掉一處。

暫存樹先同步到 repo d38a0d36f（a93b2bc）。第 2、3 條的測試：aos-agent 全套 118 項 OK（含 2 項預期失敗），新加 2 項；self_state、subagent、agents_ctl 的測試都 OK。

### 第 3 條 limits 說明：已 commit 50e7a35bc（head-core 放行）

- **新的回報路線**（11-14 13:2x 起）：ok-limits 歸底座部，部長是 head-core，進度、請示、commit 放行都改寄 head-core。
- **欄位名**：ok-devt 管整套「身分與事件」設計。who 的 notify_box、B7 的 reason 等欄位名，要等兩邊定稿才 commit。
- **拆件**：limits 這件拆出來先交。ok-devt 正式同意「nofile 照舊報錯、不收別名」。
- **順手補 B5 漏的**：py/daemon_ctl 的 LIMIT_INTS 原本不認 mem_total_mb、procs_total，經 ctl add 或 subagent add 給這兩個鍵會被 ArgumentsBad 擋下。現在補上，新增 test_limits_keys.py，共 3 項。
- **乾淨複本測試**：git archive f966d3fa6，經 clean.sh 跑，五夾全 OK——daemon-ctl 35、subagent 26（skip 2）、agents_ctl 4、py/tests 37、aos-agent 129（2 項預期失敗）。
- **entry.py 進 repo 的那一刻就生效**：活樹的 aos-agent、aos-daemon-ctl 都指到 repo 的 cmd，起來後會往上找到 repo 的 proto8/py。換檔步驟：
  1. 備份到 ~/code/limits-1114/backup/entry.py.f966d3fa6；
  2. 新版寫成同資料夾的暫存檔，再 mv 蓋上；
  3. 立刻 import，LIMIT_INTS 裡有兩個新鍵；
  4. 跑 daemon-ctl 35 項，OK；
  5. 跑 `aos-agent ctl ls`，正常。
- **換樹**：活樹的 lib、knowledge 複本要重抄，已寄給 ok-kf。
- **wf/advices 改「已解」**：只寫成 diff，放在 wf/temp/ok-limits/aos-advice/advices-limits-solved.diff。要由我交還是頂層交，頂層還沒定。

### B7：after_stop 分得出 stop／sleep／rm（11-15 交件）

- 11-14 碼已完成，頂層 15:26 定換樹凍結期間不交；ok-limits 11-15 收樹。11-15 由 Claude 線 claude-b7 接手（使用者 11-15「能做的先做」），在 git archive 的乾淨複本上套 diff、自己編 bin、`env -i` 跑全套後交件。
- 名字照 ok-devt 定稿：`stop_cause.json`、鍵 `cause`、`AOS_LOOP_CAUSE`、事件欄 `cause`；值 `stop`／`sleep`／`remove`／`shutdown`／`stuck`／`signal`／`max`／`body_exit`／`error`。
- 交接列的六件、真 daemon 九種情況的事件輸出、沒測到的（stuck、sudo／bwrap）都在圖紙 [B7](kernel-limits-1114/B7-stop-reason.md) 第 9 節。
- 生效：aos-loop、aos-daemon 是 C++，進 main 不會改到活樹，要下次換樹編新的 bin；lib（hook_fire、self_hook 的說明）同樣跟換樹走。新舊混用不會壞（第 9.3 節）。
