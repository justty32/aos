# aos 的隊形：現在怎麼做（短卡）

← [dispatch](README.md)｜選人判準 [team-model](../team-model.md)

本專案實際怎麼開隊、五件最常做的事的實際指令。只寫**今天的做法**（11-14 改寫，使用者專區「q2:move」；11-23 照 eca-aos 這邊的工作室分工改：打雜工、沒有部長、寫程式用 Claude，分工本身與下文「第 N 題」所指的七題表見 [wf/org](../../org/README.md)）；細節在分檔，舊隊形（codex 隊員、terra、sonnet 搜集）的原文已刪（11-17 刪掉各 archive/），要看去 git 歷史，最後還在的 commit 是 `31a64d4a7`（路徑 `wf/workflows/dispatch/archive/`）。改制時直接改這裡。

## 誰做什麼

- **頂層 agent 叫 `eca-aos`**（`repo-aos` 是 daemon 表上那一列的名字）**，只當調度者**：只跟使用者交流、派工、收件，不親自做內容；**可以親手做的只有三樣**：活狀態（progress、HANDOFF、筆記）、把使用者的話抄進規矩、`wf/org`，其餘照派（11-23 第 7 題）；收線＝讀隊長附的證據逐條對、不重跑，真要獨立驗證就派一條便宜的線去跑；想順手做小事時先問能不能一句話交給別人（使用者 08-30「頂層不要做太多事」、09-24「你不要自己做事，盡量交給 agent」）。**工作室沒有部長**（11-23 第 6 題）：放行與回報的對象是 eca-aos，回報寄誰仍以任務書為準。（11-14 公司那台舊樹的隊形是頂層底下分幾個部、各一位 fable 部長，線的回報與 commit 放行找部長；那是當時的安排，現在不用。）
- **現在是固定的位子加按件派**：kb、templates、core、frontend 幾個位子全是 eca claude，有活才掛，沒掛時由 eca-aos 派 Claude 子 agent 讀角色卡與筆記代班；不屬於任何位子的事按件派（見 [wf/org](../../org/README.md)）。以前「一條線＝一隻 opus 或 fable 的 eca、名字 `ok-<線名>`」是舊隊形，要再用得使用者說。不管位子還是按件派的 eca：工作區 11-22 起是 repo 根 `~/repo/aos`，自己的草稿、任務書、定義夾放私有地盤 `wf/ws/<上層>/<名字>/`，不進 git 的放地盤裡的 `temp/`，見 [wf/ws](../../ws/README.md)；掛在頂層的 kernel_gate 底下，自己也可以開 gate、在底下掛隊員。
- **打雜工＝sol 的 agent-fsm**（腦走本地 LiteLLM，`llm.json` 是 `{"model": "sol", "reasoning_effort": "high"}`）：蒐集、逐條核對、不必判斷的雜活，以及照對照表改名、搬檔、套格式這類機械式施工；**寫程式與重要的施工用 Claude**（使用者 11-23「蒐集算打雜，但施工這塊，如果是重要的部分，那確實還是得用claude」「尤其是寫程式」；第 4 題）。打雜工用到才掛，掛不起來才由 sonnet 的 Claude 子 agent 補位（第 5 題）。**不用 terra、不走 codex**（使用者 11-14「不要terra，盡量用sol，把sol作爲sonnet來用」「不要走codex」）。分工見 [wf/org](../../org/README.md)。
- **gpt 系不做設計決策**（使用者 11-07，長期；原話在 [03](aos-teams/03-使用者原話.md)）：11-07 定的是能做照已定圖紙寫碼、寫文件、雜活、網頁施工（內容題目由隊長定），11-23 起再收窄成上一條的打雜（寫程式與重要的施工用 Claude）；審查只挑實作錯、與圖紙不符。設計、架構、判斷設計對錯由 opus／fable 做，寫進任務書。
- **「簡單工作」的界線**（使用者 11-06 確認：「1.對。2.是。」）：雜活、純文字小改、查找盤點、跑指令收結果才算簡單，才給 sonnet（補位時）。**碰程式碼邏輯、改寫使用者的概念／規範條文不算簡單**，不給 sonnet（使用者 09-30「不要 sonnet」「就 opus」；見 [common/user「子 agent 模型」](../common/user.md)）。
- **一般 agent 再派子 agent，模型隨意**（使用者 11-06 第 1 句）；sol 隊員一張單只做一件事，要多人由派工的人多掛幾隻。
- **要規劃就走正統流程**：sol 蒐集 → opus 匯總 → fable 設計 → opus 細化成計劃 → Argon 審 → 採納表 → 施工（寫程式與重要的施工由 Claude 做，機械式的可給 sol；11-23）。需求還不清楚時先發想、不急著規劃。細節 [07](aos-teams/07-預設流程與agent-fsm.md)。
- **讀規矩**（使用者 11-06 第 1、5 句、11-13）：派出去的 agent 做事前先讀知識庫入口 `$AOS_HOME/knowledge/aos/_description.md`，再讀[規矩卡](../common/rules-card.md)（使用者 11-17 待裁網頁 wf-6 選 a，取代通讀 wf/ 規矩；碰程式再讀 conventions，當線隊長、要派隊員再讀本卡）；**簡單工作與雜活例外**（可免讀），對子 agent 一樣成立。任務書開頭寫明，往下派時也寫進子任務書。用配給包的蒐集員、審稿員照包裡的分級：只讀知識庫入口加站台層（[kits](kits/README.md)）。
- **開隊前先把打算講給使用者聽**，等他回應或糾正再派；他可能在手機上、回得慢，問題與選項照發、附預設建議。問他的題目寄專區（下面第 2 件）。
- **權限邊界**：agent 不加全繞過沙箱／權限的旗標，要開由使用者親自開。eca 不設 rlimit、自己收斂；agent-fsm 帶 `limits`。
- **命名**：daemon 表上的名字整台共用，掛的 agent 一律 `<eca 名>-<角色>-<編號>`（例 `ok-kf-sol-1`）。
- **Argon 是參與者**：審查之外也提案；正統流程裡在 opus 細化之後、交實作之前送審一次，每篇 fable 設計後也可以跑（指令見 [05](aos-teams/05-同機session與Argon.md)）。

## 五件常做的事

### 1. commit：一律 `commit-request`，不自己 `git add`／`git commit`／跑 `index_gen`

```sh
~/repo/aos/wf/tools/commit-request claim  --line ok-x 檔…          # 開工：宣告這些檔我在改
~/repo/aos/wf/tools/commit-request submit --line ok-x --files 檔… --msg-file 訊息檔 \
    --op '{"op":"day_upsert","date":"2026-11-14","name":"x","link":"x.md","summary":"…"}'
```

- `--files`／`--rm` 的路徑從 repo 根算，`--msg-file` 從你所在的資料夾算；結果看 stdout 最後一行 JSON（`DONE` 加雜湊，或錯誤原文）；先 `--dry-run` 看會交什麼。
- 日索引（`proto8/thinking/<年-月>/<日>/README.md`）、月索引（`proto8/thinking/<年-月>/README.md`）、`wf/progress.json` 不交整檔，用 `--op`（`day_upsert`、`month_bump`、`month_set`、`progress_upsert`、`progress_delete`）。生成的 `_index.json`、code map 由排隊重生，不要列進 `--files`（`proto8/knowledge/` 底下手寫的 `_index.json` 例外，照一般檔交）。
- 交之前 `git diff -- 檔` 確認只有自己的字；**不 push**。
- **誰放行**：照你的任務書。沒寫就是（11-23 第 6 題）：掛著的位子在自己範圍內先交後報（回報附雜湊）；跨範圍、帶 `--rm`、要跑 `install.py`、動活樹的先問 eca-aos，每批寄它：檔案清單、`git diff --stat`、怎麼驗的；Claude 子 agent 與打雜工不交件，產物給派它的人。放行的前提：在乾淨複本（`git archive`）測過並附結果；要在 repo 裡跑 `install.py`（＝換掉活樹正在用的 `bin/`、`lib/`）或動到活樹直接讀的 `proto8/knowledge`、`frontend` 時先寫暫存檔再改名、跑定向測試、原檔有備份；用 commit-request（共用索引加 `--op`）；不撞別線 claim 的檔。跟鐵律有出入的，eca-aos 問使用者。（11-14 舊樹這一步由各部部長放行，工作室沒有部長。）更多：[07「commit」](aos-teams/07-預設流程與agent-fsm.md)、[patch-and-commit](../../public/patch-and-commit.md)。

### 2. 問使用者：寄專區，題目會出現在全景頁

```sh
aos-user send --kind decide --from ok-x \
    --reply-to <自己的 stack>/mailbox --title "一句話" 題目.json
```

- 一封最多 7 題，每題 `id`、`question`、`eli5`、`options`（`key`、`label`、`consequence`）、`recommend`；每小時最多 10 封。
- 回信用 `mailbox_read` 讀（專區回信自動留在 `mailbox/archive/<信名>/`），再跑 `aos-user verify <那個夾>`，看到 `ok: matches` 才算數。push、刪檔的授權一定要驗。更多：[user-zone-mail](../../public/user-zone-mail.md)、知識庫 `aos/user_zone.md`。

### 3. 掛 sol 隊員

`subagent` 這支工具不是每隻 eca 都有：現成的範本（eca 與 agent-fsm）都不帶 `subagent` 包，也不帶 `agent_def`（def 包），要用就 `self_tools add` 自己加（知識庫 `aos/agents.md`）。公司那台 11-23 的現況：eca-aos 用 `self_tools add` 自己加了 `subagent` 與 `agent_def` 兩支（`{"$env":"AOS_HOME","$path":"/lib/tools/agent/subagent"}`，`agent_def` 同理）。以前線用的定義（公司那台舊樹 `~/aos-home/agents/` 的 `opus-kernel`、`fable-kernel`）多掛了 `subagent`、`kernel_gate` 兩包，那個夾 11-23 已經不在；家機 11-22 起新做的定義放 `wf/tree/` 或上層的地盤 `wf/ws/…`，兩處現在都還沒有這兩份。`self_state {"parts":["tools"]}` 看得到自己有沒有。

1. `agent_def {"op":"new","template":"agent-fsm","path":"defs/gather"}`，把 [kits/gather/](kits/README.md) 的 `system.txt`、`tools.json`、`llm.json` 蓋過去，`agent_def check`（包裡沒有 `.env`，`AOS_LLM_KERNEL` 由上層 daemon 那一列傳下來，見 [kits/card](kits/card.md) 第 1 步）。任務書寫知識庫的絕對路徑（card 第 3 步）。
2. `subagent {"op":"add","def":"defs/gather","name":"ok-x-sol-1","ws":"wf/ws/<上層>/<你的名字>/temp/ok-x-sol-1","limits":{"mem_mb":1024,"files":256}}`（`ws` 從你的工作區算；11-22 起 eca 的工作區是 repo 根，照舊寫 agent 名會落在 repo 根底下，所以放進你自己地盤的 `temp/<agent 名>/`——11-23 提案，沒試過；`procs` 別設；開檔的鍵是 `files`）。
3. 任務書一張單只做一件事：唯一目標、可讀可寫的路徑、交付物、完成條件；寫明「讀完同一回合就動手」。
4. 驗收讀它的 `out/`，逐條對證據；它不 commit。收隊 `subagent rm`（stack 留著）。完整步驟：[kits/card](kits/card.md)、心得 [sol-crew](../../public/sol-crew.md)。

### 4. 等隊員：不要卡在同一回合

`subagent say` 之後就結束這一回合；用 `clock_register {"op":"add","name":"…","at":"+10m","text":"…"}` 叫醒自己再看，或等它寄來的信。`subagent listen` 預設不限時一直等（11-15 起，以前 600 秒），別讓它卡著這一回合：帶 `"timeout_s": 60`，或用 `"last": 1` 只看最後一則不等。

### 5. 活樹旁邊：repo 那棵是使用者正在用的樹

- 活樹＝兩台都是 `~/aos-home/.stack/procs/repo-aos`（公司那台 11-24 起、家機 11-24 晚起，repo 裡都已經沒有 `.stack`）（每台各有各的，不跟著 git 搬，使用者 11-23；定義 `wf/tree/root/`，資料夾名字還叫 `root`，但 11-23 起它是子 daemon、不帶鐘）。`~/aos-home`：兩台都是整棵樹的根（公司那台 11-23 起、家機 11-24 晚起；`~/aos-home/.stack` 是根的 stack，鐘只在這裡），底下除了 llm kernel 與 repo 這棵，還掛著使用者自己別的專案的子 daemon；家機的舊樹退路 `~/aos-home.old-1122/` 已經不在。這些一樣不碰（[06「現況」](aos-teams/06-公司WSL活樹與任務書硬規則.md#現況)）。
- 活樹不碰（06 第 1 條）：不寫活樹底下任何檔（連同 `~/aos-home`、`~/aos-home.old-1122/`）、不對它的 daemon 與 agent 下任何指令、不寄信進去（任務書點名的回報對象與使用者專區除外）；唯讀查看只限任務書點名的，與 06 第 9 條的核對。
- 不在共用工作樹跑 `git stash`、`git reset --hard`、`git checkout -- .`、`git clean -fdx`（06 第 7 條）：`.stack` 被根 `.gitignore` 忽略，`git clean -fdx` 會連活樹一起刪。
- 清掉 `AOS_*` 之後，`aos-daemon-ctl`、`aos-mailbox` 這類指令不帶 `-d` 會找 cwd 的 `./.stack`：站在 `~/repo/aos` 下指令＝打到活樹。暫存樹的指令一律帶 `-d <暫存樹 stack 的絕對路徑>`。
- 你的 shell 帶著活樹的 `AOS_*`：跑任何 aos 指令或測試，一律經一支 bash 腳本（不是 bash 就拒絕 → 逐一 unset `AOS_*` → 還有殘留就拒絕 → exec）。shell 是 zsh，要分詞的寫法包 `bash -c`。
- 不把整份環境變數寫進檔、log 或信（`env`、`printenv`、`/proc/*/environ` 都不行，裡面有 API key）；要看只列變數名或只列 `AOS_*`。
- 不刪檔（連自己的暫存也不刪）。收行程只准兩種（06 第 4 條）：`aos-daemon-ctl -d <自己暫存樹 stack 的絕對路徑> shutdown`，或 kill 自己記下的 pid（kill 前 `readlink /proc/<pid>/cwd`）；禁 `pkill`、`killall` 與任何按名字收行程的寫法。
- 改 `proto8/py/`、`cpp/` 存檔不會動到活樹，要在 repo 裡跑 `install.py` 才換（那一步先回報，06 第 5 條）；`proto8/knowledge`、`frontend` 存檔當下活樹就在用；`templates` 要重抄進樹才生效。
- 任務書必貼的九條硬規則全文：[06](aos-teams/06-公司WSL活樹與任務書硬規則.md)；踩過的坑：[活樹旁邊](../../public/活樹旁邊.md)、[行程與環境](../../public/行程與環境.md)、[pitfalls](../../public/pitfalls.md)。

## 回報、經驗、意見

- **回報**寄任務書指定的對象（工作室是 eca-aos；11-14 舊樹是各部部長）：標題寫你的判斷與要什麼（`NEEDS-USER`／`BLOCKED`／`PROGRESS`／`DONE`），卡住的信先寫已排除的（[07「寄信怎麼寫」](aos-teams/07-預設流程與agent-fsm.md)）。
- **別隊也用得上的做法、坑** → 投 [wf/public](../../public/README.md)；**aos 本身哪裡該改** → 投 [wf/advices](../../advices/README.md)。先查這兩處再動手，常見做法一覽在 [recipes](../../public/recipes.md)。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-公司WSL](aos-teams/01-公司WSL.md) | 公司那台（WSL）特有的：帳號、監看門檻 |
| [02-指令沙箱與試玩](aos-teams/02-指令沙箱與試玩.md) | 每段做完派人試玩；Claude API 不穩時 |
| [03-使用者原話](aos-teams/03-使用者原話.md) | 隊形相關的使用者原話（11-06、11-07、11-13；11-14 的幾句引在 07），檔尾有一節「已被取代的原話（留底）」 |
| [04-進度回報](aos-teams/04-進度回報.md) | 桌面看板已停用（使用者 11-14），只留指標；回報寄任務書指定的對象 |
| [05-同機session與Argon](aos-teams/05-同機session與Argon.md) | 同機 session 傳話、Argon 的指令、agy、LM Studio |
| [06-公司WSL活樹與任務書硬規則](aos-teams/06-公司WSL活樹與任務書硬規則.md) | 活樹現況、任務書必貼的硬規則、停樹換檔 |
| [07-預設流程與agent-fsm](aos-teams/07-預設流程與agent-fsm.md) | 正統規劃流程、sol 走 agent-fsm、commit 與回報的細節 |

<a id="指令與沙箱"></a>
<a id="codex-呼叫與沙箱"></a>
<a id="codex-可用-slug"></a>
<a id="每段做完派人試玩2026-09-13-起"></a>
<a id="使用者-11-06-原話現行隊形的出處"></a>

## 交接

- 派線流程、領地表、收線 → [dispatch](README.md)；任務書 checklist → [派線與任務書](../../public/派線與任務書.md)；配給包 → [kits](kits/README.md)。
- 各層派哪級模型 → [team-model](../team-model.md)；隊伍會撞的資源 → [resources](../resources.md)；模型端點 → [dev-env](../dev-env.md)。
