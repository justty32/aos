> 這份是蒐集員交回的原文（kb-1114，11-14）。路徑裡的家目錄已換成 ~，其餘逐字。

# ok-kb 蒐集 claude-2：wf/ 其餘部分的事實盤點（2026-11-14，家機）

唯讀蒐集，只寫這一份。路徑都從 repo 根 `~/repo/aos` 算；`W` ＝ `wf/workflows`。
每條：**類**｜**在哪**｜**什麼**｜**證據**｜**多確定**。只寫事實，不寫改法。
檢查用的唯讀腳本：`/tmp/okkb-claude2/linkcheck.py`（md 連結）、`/tmp/okkb-claude2/tools.py`（工具對文件）。

常引的「較新規則」出處（下面用代號）：

| 代號 | 規則 | 出處 |
|---|---|---|
| R-commit | 各線不自己 `git commit`、不 `git add`、不自己跑 `index_gen`，改 `wf/tools/commit-request`；直接 commit 被 hook 擋 | `W/dispatch/aos-teams/06-…硬規則.md:24`、`W/dispatch/aos-teams/07-…agent-fsm.md:30`、`.git/hooks/pre-commit:2-5` |
| R-zone | 要使用者裁／驗／做的新題寄使用者專區（`aos-user send`／`user_send`），不再加進 WAIT_USER | `AGENTS.md:52`、`W/common/user.md:14`、`wf/WAIT_USER.md:16` |
| R-main | 只有一個 `main`，不開分支、不開 worktree 分支 | `W/common/user.md:10` |
| R-gpt | gpt 系只用 sol、不用 terra、不走 codex，走本地 LiteLLM 上的 agent-fsm | `W/dispatch/aos-teams/07-…:27`、`:54` |
| R-v1 | 單一執行檔 `aos`（根 CMake、`build/bin/aos`）11-05 封存；repo 在 `~/repo/aos` | `AGENTS.md:3`、`AGENTS.md:45`、`wf/INDEX/01-repo-layout.md:11,21` |
| R-noctest | 鐵律 1（改完跑 ctest）11-04 刪 | `AGENTS.md:35` |

注意：R-commit 只寫在 `aos-teams/06`、`07`（另 `dispatch/kits/card.md`、`wf/public`、`wf/advices` 有提）；`AGENTS.md`、`W/common/user.md`、`W/common/conventions.md`、`wf/WORKFLOWS.md`、`wf/STRUCTURE.md` 全文 grep `commit-request` 都是 0 筆，`AGENTS.md:37`（鐵律 3）與 `user.md:12` 仍寫「commit 前跑 `index_gen.py --apply`」。（入口鏈歸另一位蒐集員，這裡只當證據列。）

---

## A. 各工作流資料夾

### A0 大小總表

「最後 commit」是 `git log -1 --format=%cs -- <路徑>`。11-13 那幾筆多半是全庫性的 commit（鋪 index `418e17927`／收回 `fe4908ba9`、刪 wf-lint `70e6d4fd8`、code map 搬家 `a03d38739`），不代表內容有人重讀過；所以另列「最後一筆只動這個工作流內容的 commit」（從 `git log -4` 判讀）。

| 路徑 | 檔數 | bytes | 最後 commit | 最後一筆內容性 commit | 其中 archive／reports |
|---|---|---|---|---|---|
| `W/feature-dev/` | 1 | 4,933 | 11-13 | 11-13（改連結、改指令名） | — |
| `W/refactor/` | 88 | 691,432 | 11-13 | 11-13 | `reports/` 80 檔 665,895；`archive/` 6 檔 20,595；入口＋專章共 4,942 |
| `W/tidy/` | 24 | 133,516 | 11-13 | 11-13（f14c851a9 交接書六條原則） | `reports/` 20 檔約 113 KB |
| `W/spec/` | 1 | 336 | 11-14 | 11-14（改成轉址） | 本體在 `W/common/archive/spec/`（74 檔 667,501） |
| `W/ideas/` | 1 | 364 | 11-14 | 11-14（改成轉址） | 本體在 `W/common/archive/ideas/`（99 檔 772,874） |
| `W/hackathon/` | 143 | 340,686 | 11-14 | 11-14（97cda3435 加一句「來源都已封存」）；規則本體 08-26 | `archive/` 130 檔 300,513；現役 13 檔約 40 KB |
| `W/experiments/` | 17 | 59,403 | 11-13 | 2026-09-25（拆檔） | — |
| `W/digest/` | 18 | 101,150 | 11-13 | 11-04／11-01（第二批） | — |
| `W/workshop/` | 140 | 430,265 | 11-13 | 11-12（刪一句）；規則本體 08-25 | `archive/` 134 檔 405,036；現役 6 檔約 25 KB |
| `W/investigations/` | 4 | 22,393 | 11-13 | 11-04（改封存連結） | — |
| `W/dev-env/` | 2 | 6,759 | 11-13 | 11-13 | — |
| `W/team-model/` | 5 | 11,816 | 11-13 | 11-12（刪沿革） | — |
| 入口單檔 | | | | | `dev-env.md` 6,187（11-13）、`team-model.md` 8,040（11-13）、`investigation.md` 1,963（11-13）、`testing.md` 4,663（11-13）、`planning.md` 1,733（11-13）、`decide-page.md` 7,786（11-12）、`resources.md` 4,011（11-13）、`TEMPLATE.handoff.md` 4,179（11-14）、`TEMPLATE.workflow.md` 1,161（11-13）、`inbox.json` 4,825、`decisions.json` 1,783 |

對照：`W/common/` 223 檔 1,680,052（其中 `archive/` 209 檔 1,619,152）；`W/dispatch/` 491 檔 1,595,752（其中 `archive/` 463 檔 1,488,213）。整個 `W` 底下 archive 佔絕大多數位元組。

### 跨資料夾的一條（先列，後面各夾只點名）

**A1**｜過時｜下列各處還把「等使用者的事」只導到 `WAIT_USER`，全文沒提使用者專區：`W/feature-dev/README.md:14,27,57`、`W/testing.md:13,20,58`、`W/investigation.md:20`、`W/planning.md:19`、`W/dev-env.md:13`、`W/dev-env/01-跨機與外部工具.md:27`、`W/dev-env/02-模型端點.md:22`、`W/tidy/README.md:58`、`W/tidy/gotchas.md:15`、`W/resources.md:70`、`W/decide-page.md:66`、`W/TEMPLATE.workflow.md:30`、`wf/WORKFLOWS.md:66`、`wf/INDEX.md:29,53`、`wf/STRUCTURE.md:19`、`W/inbox.json`（`local.out_of_tree_reply` 第 4 條、`local.handoff` 第 2 條）｜證據 R-zone｜確定（字面衝突）。

### feature-dev

**A2**｜過時｜`W/feature-dev/README.md:13,23`｜Done when 與流程寫「跑過 `python3 wf/tools/index_gen.py --apply` → 補文檔 → commit」，是自己跑生成器、自己 commit 的寫法｜R-commit（07:30「不要再 git add，也不要自己跑 index_gen --apply」）｜確定（字面衝突；哪邊算數見開頭注意）。
**A3**｜過時｜`W/feature-dev/README.md:26`｜「自動驗證是你自己跑的把關（鐵律：改完跑驗證）」｜R-noctest：鐵律 1 已刪，現存鐵律 2、3、4、5、6 沒有「改完跑驗證」；同檔 `:12` 已寫成「build 得過」｜確定。
**A4**｜過時｜`W/feature-dev/README.md:18-24` 整段流程｜只寫「一個 agent 自己讀 code map→改→build→commit」；全檔 grep `agent-fsm`、`sol`、`commit-request`、`aos-user`、`專區` 都是 0｜現行實作隊形在 `W/dispatch/aos-teams/07-…:19-27`（opus 帶 sol、走 agent-fsm）｜確定（缺，不是寫錯）。
**A5**｜找不到｜`W/feature-dev/README.md:41,47-50`｜提到本工作流的 `session-log.md`、`landed/`、`gotchas.md`、`archive/`，四個都不存在（檔內自述「長出來才建」）；`find W -name session-log.md` 0 筆，`wf/SESSION-LOG.md:47-52`「各工作流 session-log」表是空的｜確定。

### refactor

**A6**｜過時｜`W/refactor/README.md:13,20`｜「code map 中受影響領域的列已更新」「更新 code map」是手改的寫法｜`wf/knowledge/code-map.json` 的 `_description`：「`wf/knowledge/code-map/` 底下是生成物，別手改」；`AGENTS.md:37`｜確定。
**A7**｜找不到｜`W/refactor/README.md:22-26`｜「內容」表只列 `moving-things.md`；同夾的 `reports/`（3 夾 80 檔 666 KB）與 `archive/` 沒列｜`find` 結果見 A0｜確定。
**A8**｜過時｜`W/refactor/moving-things.md:8,55-61,82`｜要求「CI 實測過」「CI 指令實跑一次」、grep `.github/`｜repo 沒有 `.github/`；`W/dev-env/01-…:5`「沒有 CI 差異，全部驗證都由 agent 跑」｜確定。
**A9**｜跟程式對不上｜`W/refactor/moving-things.md:80`；同類 `W/tidy/README.md:16,38,41,49`｜寫 `python3 tools/check_anchors.py`、`tools/tabledb.py`、`tools/find_big_lists.py`、`tools/fix_moved_links.py`；repo 根沒有 `tools/`，實際在 `wf/tools/`（只有站在 `wf/` 才跑得到）｜`find wf/tools`｜確定。
**A10**｜過時｜`W/refactor/moving-things.md:87-88`｜「所有分支都要改…用 worktree 在別的分支上做」｜R-main；`git branch -a` 只有 main、`git worktree list` 只有一棵｜確定。
**A11**｜過時｜`W/refactor/moving-things.md:4,50`、`W/tidy/gotchas.md:8,21,34`｜講「拆 repo」「母 repo／子 repo 各跑各的檢查」｜`W/dev-env.md:35`：aos 是獨立 clone，`simple_tools` 的 submodule 11-13 晚起不再是工作 repo｜確定（情境已不在）。
**A12**｜過時｜`W/refactor/moving-things.md:13-14`｜「驗證 → 最後才清掉舊的」，沒提刪除要授權｜`AGENTS.md:36`（刪除屬不可逆動作，要授權來源）；`W/TEMPLATE.handoff.md:22`「不要 rm」；commit `b8ff23ada`「依使用者不刪規則」｜猜（兩邊沒有直接互斥的句子）。
**A13**｜壞連結｜`W/refactor/reports/2026-11-07-sol審查/11-使用者裁定/01-落實結果.md:48` → `wf/tools/wf-lint.sh`（不存在；`70e6d4fd8` 刪）；同檔 `:47` 與 `W/refactor/reports/2026-11-07-arknights-kb/03-W1到W4施工結果.md:98` 提 `wf/tools/codemap_gen.py`（不存在，只剩 `wf/tools/__pycache__/codemap_gen.cpython-314.pyc`）｜確定（都是當時的報告）。
**A14**｜太長｜`W/refactor/reports/`：`2026-11-07-sol審查/` 64 檔 516,200（內含 `decide_20261107_sol.json` 82,559）、`2026-11-07-arknights-kb/` 6 檔 94,284（`01-盤點-語料.md` 39,990、`08-第二輪簡報.md` 21,288）、`2026-11-07-晚審/` 10 檔 55,411｜arknights 這份的對象是另一個專案，`W/common/user.md:19` 寫 arknights 凍結到至少 12-14｜大小確定；「該不該留在這」不判。

### tidy

**A15**｜過時｜`W/tidy/README.md:25,27`；`W/tidy/manager-brief.md:17`｜Done when 寫成硬條件：非 archive 的 md 超過 8192 bytes 要 0 個、子夾 README ≤ 300 行、入口 ≤ 100 行、`SESSION-LOG.md` ≤ 4096 bytes｜`wf/STRUCTURE.md:33`「門檻是觸發檢視的訊號、非硬性上限」；`W/common/user/02-交接與收工.md:11`「開發階段不設行數上限」；commit `9f60cb0d8`「8 KB 三處改成推薦語氣」；實況：`wf/SESSION-LOG.md` 17,260 bytes，非 archive 超過 8000 bytes 的 md／json 有 26 個（見 F）｜確定。
**A16**｜過時｜`W/tidy/README.md:45,46,48`；`W/tidy/gotchas.md:31`｜「一律 `git mv`／新檔 `git add`」「看 `git diff --cached`」「以明確路徑補 `git add`」｜R-commit（07:30「不要再 `git add`」）｜字面衝突確定；commit-request 吃不吃改名沒查，猜。
**A17**｜過時｜「kernel」一詞指 wf 這套骨架，跟 aos 的 kernel 撞名：`W/tidy/README.md:8`（骨架版本升級、照上游變動記錄）、`:45`（不碰 kernel 檔）、`wf/WORKFLOWS.md:41`（「kernel 內建」）、`wf/INDEX/01-repo-layout.md:14`（「kernel 工具」）、`W/planning.md:5`（「kernel 的 planning 管線」）、`W/team-model/plans.md:3`（「kernel 升級不覆蓋」）｜知識庫 `~/aos-home/knowledge/aos/_description.json` 八個詞之一 kernel＝「wherever you send a request」；repo 裡找不到任何「上游骨架」或升級記錄的檔｜撞名確定；上游骨架還在不在，猜。
**A18**｜過時｜`W/tidy/manager-brief.md:12`｜「預設實作工人＝便宜的實作 agent（例：codex CLI 的非互動模式）」｜R-gpt｜確定。
**A19**｜過時｜`W/tidy/content-trim.md:54`｜適用範圍列了「code-map」與 hackathon、workshop 的 `records/`｜code map 逐檔表現在是生成的 json（見 D1）；兩個 `records/` 11-03 都進了 archive（`W/hackathon/archive/README.md:9`、`W/workshop/archive/README.md:9`），而同檔 `:59` 寫 archive 凍結不改｜確定。
**A20**｜找不到｜`W/tidy/content-trim.md:58`｜「`dispatch/` 的 `reports/`、`done/`、`superseded/`」｜`W/dispatch/` 頂層只有 `aos-teams/ aos-teams.md archive/ CLAIMS.md driving-cli-agents.md kits/ lessons/ lessons.md README.md`｜確定。
**A21**｜太長｜`W/tidy/reports/2026-11-12-收尾.md` 27,064 bytes（單檔）；`W/tidy/reports/2026-11-03-收斂/05-…md` 8,117｜確定。
**A22**｜找不到｜`W/tidy/README.md:59`｜報告只連到最舊那份 `reports/2026-10-02-wf-tidy.md`；`reports/` 現有 6 輪（10-02、10-13、10-20、10-26、11-03、11-12），沒有索引檔｜確定。

### spec、ideas

**A23**｜（現況吻合）｜`W/spec/README.md:1-3`、`W/ideas/README.md:1-3`｜兩份都只剩轉址，連結目標都在；`W/_index.json`、`wf/WORKFLOWS.md:18-19`、`wf/STRUCTURE.md:59`（工作樹版）說法一致｜確定。跟 archive 規則的關係見 C9。
**A24**｜過時｜`W/workshop/README.md:18,87`、`W/hackathon/README.md:60`｜「談出方向後轉交 ideas／`docs/`」「我不自己改 `docs/`」｜ideas 已封存（`W/ideas/README.md:1`）；repo 根沒有 `docs/`（`ls` 報不存在；條文現在在 `proto8/docs/`）｜確定。

### hackathon

**A25**｜過時｜`W/hackathon/arena.md:17-22,27-29,38`、`W/hackathon/briefs.md:52-56,82`、`W/hackathon/gotchas.md:54,60`、`W/hackathon/staff/researcher.md:28`｜場地腳本寫 `SRC=/mnt/c/code/mine/simple_tools/aos`、複製 `build/bin/aos` 與 `build/lib/*.so`｜R-v1；`W/dev-env.md:47`「不要在 `/mnt/c` 底下跑」「`~/repo/aos` 11-13 起唯一一份」｜確定（照做會失敗：來源路徑與執行檔都不在）。
**A26**｜過時｜`W/hackathon/README.md:9-10`、`roles.md:11-14`、`rounds.md:23-26`、`arena.md:43-49`、`briefs.md:57,99`｜參賽者、評委、書記、祕書全是 `codex exec`，子 agent 指名 Terra／Luna；現役 13 檔裡 `codex` 出現 34 次｜R-gpt｜確定。
**A27**｜找不到｜`W/hackathon/README.md:56`、`W/hackathon/INDEX.md:29`；`wf/WORKFLOWS.md:22`「已辦場次見 INDEX」｜紀錄落點 `records/<題目>.md`，但 `W/hackathon/records/` 不存在（整夾在 `archive/records/`）；`INDEX.md` 裡也沒有任何場次清單｜`find`、`W/hackathon/archive/README.md:9`｜確定。
**A28**｜過時｜`W/hackathon/README.md:34-41` 對 `:43`｜上半段還寫「優先挑 workshop/BACKGROUND.md…background/ 那 17 檔…OPEN-QUESTIONS…roadmap」，下一段自己寫「上面這些來源都已封存」｜同檔｜確定。
**A29**｜過時｜`W/hackathon/briefs.md:24`｜資料包寫 `docs/aos-folder.md / docs/roadmap.md`｜repo 根沒有 `docs/`｜確定。
**A30**｜重複｜`W/hackathon/staff.md:7-13`、`W/hackathon/staff/README.md:18-23`、`W/hackathon/INDEX.md:21-27` 是同一張四列表寫三次；`W/hackathon/INDEX.md:9-17` 與 `W/hackathon/README.md:48-52` 重複三列｜確定。
**A31**｜過時｜`W/hackathon/briefs.md:6`｜「名單與挑人判準見 README 的〈角色〉」，README 已沒有這節（在 `roles.md`，`README.md:50`）｜確定。
**A32**｜跟程式對不上｜`W/hackathon/rounds.md:25`、`W/workshop/commands.md:34-35` 寫從 `--json` grep 第一筆 `session_id`；`W/workshop/SESSIONS.md:28` 寫「事件裡的欄位是 `thread_id`，不是 `session_id`」｜兩份互斥｜互斥確定；哪個對，猜（沒跑 codex）。
**A33**｜（看起來沒在用）｜hackathon、workshop 兩個工作流｜兩邊 `archive/README.md:9` 都寫紀錄是「proto5～7 年代」、11-03 整批封存；之後沒有新場次。11-14 的發想（`proto8/thinking/2026-11/14/aos-brainstorm/README.md`，`aos-teams/07` 稱「第一次照這樣跑」）全文 grep `workshop`、`hackathon` 0 筆｜猜（沒人用是從紀錄推的）。

### workshop

**A34**｜過時｜`W/workshop/README.md:5-6`；`wf/WORKFLOWS.md:21`｜「12 場紀錄、背景資料、問題清單、session id 看 INDEX.md」；`W/workshop/INDEX.md:10-16` 只列 5 個現役檔，紀錄、背景、問題清單都在 `archive/`（`W/workshop/archive/README.md:9-13`）｜確定。
**A35**｜找不到｜`W/workshop/README.md:80`、`W/workshop/staff.md:18,36`｜紀錄落點 `records/<主題>.md`、書記任務書寫 `wf/workflows/workshop/records/<檔名>.md`；`W/workshop/records/` 不存在｜確定。
**A36**｜過時｜`W/workshop/commands.md:11-20,24,31-32`、`W/workshop/README.md:10,29-31,34-35`｜家裡寫「WSL／Linux」、公司寫 Windows `codex.exe` 配 `-C 'C:\code\mine\simple_tools\aos'`；slug `gpt-5.6-sol/terra/luna`；全流程 `codex exec`（現役 6 檔 `codex` 39 次）｜R-gpt；`AGENTS.md:45`（家機 Manjaro、兩台 repo 都 `~/repo/aos`）；`W/dev-env/01-…:13`「codex 在 Windows 的登入已失效，固定走 WSL 那份」｜確定。
**A37**｜過時｜`W/workshop/SESSIONS.md` 全檔（3,984 bytes）｜2026-08-25 的 codex session id，檔內 `:21` 自述「全部在公司那台 Windows」｜`W/dev-env/01-…:13` 那台 Windows 的 codex 登入已失效｜猜（沒實測 resume；但前提已變）。

### experiments

**A38**｜找不到｜`W/experiments/README.md:8-10`｜實驗表只有 T5 一列；同夾 `claude-subscription/`（8 檔 34.6 KB，2026-09-13）沒列（`W/_index.json` 的 experiments 那句有提）｜確定。
**A39**｜過時｜`W/experiments/t5-agent-loop*`（9 檔）｜全是 08-25 那代：`aos deliver`、`aos recover`、`aos status --json`（`t5-agent-loop.md:9`）、`/mnt/c/code/mine/simple_tools/aos/build/bin/aos`（`record/02-…:57` 起 13 處）、ctest 基線（`record/02-…:32-36`）；`README.md:4` 講「規格、roadmap」｜R-v1；`wf/INDEX/01-repo-layout.md:21` 已有一句「讀舊紀錄注意」｜確定（它是紀錄，不是規則）。
**A40**｜過時｜`W/experiments/claude-subscription/codex-task.md:3`｜「你在 repo `~/repo/simple_tools/aos`」｜`W/dev-env.md:35`（那份不再是工作 repo）｜確定（紀錄）。

### digest

**A41**｜（沒找到過時的規則句）｜`W/digest/README.md`｜寫作規範 `:34` 已是「8 KB 推薦值」；兩批 08-26（7 篇）、10-25 至 11-01（8 篇），11-01 之後沒有新批｜內容是當時快照：`2026-08-26/` 講單一執行檔那代（例 `05-要不要把-aos-拆成很多小程式.md`），兩批各有一篇「等你決定的事」（`2026-08-26/06`、`2026-10-25至11-01/08`）是當時的待裁清單｜「規則沒過時」確定；「待裁清單現在已不準」猜（沒逐題對）。

### investigations（入口 `W/investigation.md`）

**A42**｜過時｜`W/investigations/` 全部 4 檔｜兩份報告都是 proto5（`proto5-host-root-second-wall.md`、`proto5-linux-wall-feasibility*`）｜proto5 在 `archive/`（`wf/INDEX/01-repo-layout.md:11`）；`W/investigation.md:12` 要求調查筆記落在 `investigations/<主題>.md`，但 proto8 年代這裡沒有新增任何一份｜確定（沒新檔）；proto8 的調查實際寫去哪（看起來在 `proto8/thinking/`），猜。

### dev-env（入口 `W/dev-env.md`）

**A43**｜過時｜`W/dev-env.md:33-41`；`W/resources.md:56`｜標題「worktree 隔離可以開」，寫 `git reset --hard main`、`git rebase main`、`git worktree remove`＋`git branch -d`；resources 寫「其他隊用 `git worktree`」｜R-main（11-03，比這條 09-30 的方向新）｜確定。
**A44**｜過時｜`W/dev-env.md:29`｜「commit 前必跑的只有生成器 `index_gen.py --apply`（鐵律 3）」｜R-commit｜確定（字面衝突）。
**A45**｜跟程式對不上（文件自相矛盾）｜`W/dev-env/01-跨機與外部工具.md:11` 對 `W/dev-env.md:47`｜01 寫「在 WSL 建置就用 `/mnt/c/code/mine/simple_tools/aos`」；入口寫「不要在 `/mnt/c` 底下跑」「WSL 裡的 clone 是 `~/repo/aos`（11-13 起唯一一份）」｜確定。
**A46**｜過時｜`W/dev-env/01-…:13,15`｜公司機 codex 寫法 `codex exec --approve-for-me -m <slug>`、`cd /mnt/c/code/mine/simple_tools/aos`、佇列腳本｜R-gpt；`W/dispatch/aos-teams.md`「權限邊界」條（codex 用 `-s workspace-write`）｜確定。
**A47**｜跟程式對不上（文件自相矛盾）｜`W/dev-env/02-模型端點.md:8,10` 對 `W/dev-env/01-…:17,26`｜02 寫「就是不能碰 LM Studio」「不准碰 LM Studio」；01 寫公司機 LM Studio「可以用」、表裡列為本機真模型｜兩句日期不同（09-25、11-06），02 沒寫只限哪台｜字面衝突確定。
**A48**｜過時｜`W/dev-env/02-模型端點.md:12,18`｜推薦模型名 `chatgpt-gpt-6-sol`、`chatgpt-gpt-6-astra`、`chatgpt-gpt-6-luna`｜`W/dispatch/aos-teams/07-…:56` 寫普通工作 `chatgpt-gpt-6.1-sol`；`:27` 只用 sol｜確定（名字不同）；LiteLLM 現在實際有哪些名字沒查（沒連）。
**A49**｜找不到｜`W/dev-env/02-模型端點.md:5`｜「（見上表）」，那張表拆檔後在另一份 `01-…:21-27`｜確定。
**A50**｜過時｜`W/testing.md:39`；`AGENTS.md:45`｜「公司 WSL 的 `~/aos-home` 有使用者在用的樹」只講公司機｜這台家機（Manjaro，hostname `nien`）也有 `~/aos-home`，本 session 的 shell 就帶著它的 `AOS_*`；commit `f14c851a9`「家機從零搭好 ~/aos-home」｜確定。

### team-model（入口 `W/team-model.md`）

**A51**｜過時｜`W/team-model.md:43,67`、`W/team-model/plans.md:5`、`W/team-model/grades.md:26`｜「一個 codex（`gpt-6.1-sol`）」「簡單 terra」「盡量派 codex」「工人層用 codex」｜R-gpt（11-14：不要 terra、不走 codex）｜確定。
**A52**｜過時｜`W/team-model.md:31`｜隊長「寫任務書、審 diff、跑 build、commit、push」｜R-commit；`AGENTS.md:36` push 要先確認｜確定。
**A53**｜過時｜`W/team-model.md:73-79`｜「本專案同機的隊用子 agent 通道，跨資料夾才走 inbox」、頂層只被 `NEEDS-USER` 等吵醒｜`AGENTS.md:53`（同一棵樹走 aos 信箱）；`W/dispatch/aos-teams/07-…:32-35`（所有 ok-* 回報先寄小廝 `xiaosi`，急的立刻轉、其餘 20 分鐘彙整）｜確定。
**A54**｜過時｜`W/team-model/grades.md:28`｜「現用版本：Fable 5.1、Opus 5.5、Sonnet 5.5」｜本 session 的模型是 Fable 5.2（模型 ID `claude-fable-5-2`）｜Fable 那格確定；另兩格沒查。
**A55**｜（事實）｜`W/team-model/grades.md:11-24`｜分級表列序不照級（`:20-21` 兩列 A 排在 `:19` E、F 之後），同時有 `gpt-5.6-*` 與 `gpt-6*` 兩代 slug，依據是 `probe-2026-10-09.json`（一題一次，`:28`）｜確定（描述）；哪些 slug 還在用，猜。
**A56**｜（事實）｜`W/team-model.md:5`｜「源頭是 `~/repo/moddings/skyrim/agentctl/docs/team-model.md`，兩邊要一起改」；那個檔在這台存在｜兩邊現在是否同步沒比｜猜。
**A57**｜太長｜`W/team-model.md` 8,040 bytes（離 8192 差 152）｜確定。

### 其他單檔工作流（順帶看到的）

**A58**｜過時｜`W/decide-page.md:8,13,58`｜「看板『待你裁』是唯一的收件匣」，1～2 題用 `progress_post.sh <線> ask`｜R-zone（`user.md:14`：問他的題目寄專區 `aos-user send --kind decide`，他現在大多看全景頁）；這台 `~/Desktop/aos-進度/` 最新檔是 11-08 23:29，`pgrep dash.py` 沒有看板行程｜規則衝突確定；看板已停用，猜。
**A59**｜過時｜`W/resources.md:56`｜「主工作樹的 commit 權」用 `.lock/worktree.lock`｜R-commit（排隊指令自己拿鎖，`wf/tools/commit_queue.py` 檔頭）；repo 根目前沒有 `.lock/`｜確定。
**A60**｜過時｜`W/TEMPLATE.handoff.md:21`｜「commit 到 `<repo>` 的 `<分支>`」｜R-main、R-commit｜確定。同檔 `:51`「本線團隊：`teams/<TEAM>`」｜`W/inbox.json` `_description`：teams 等五通道 11-13 退場｜確定。
**A61**｜（查過沒問題）｜`W/testing.md:5`｜連結文字「prefix-fixes 坑-55」指到 `proto8/thinking/2026-11/04/tests-trim.md`｜該檔 grep「坑-55」有 1 筆，目標對得上；只是連結字看起來像另一份檔｜確定（不是壞連結）。

---

## B. `wf/WORKFLOWS.md` 與 `wf/WORKFLOWS-parts/`

大小：`WORKFLOWS.md` 6,936；`WORKFLOWS-parts/01-multi-agent-flavor.md` 1,262、`02-統一形式.md` 294、`README.md` 136。連結檢查：這四檔 0 個壞連結，每一列指到的檔都在。

每個工作流資料夾有沒有出現：

| `W/` 底下 | 派發表哪裡 | 備註 |
|---|---|---|
| `feature-dev/` | `WORKFLOWS.md:17` | 有 |
| `ideas/` | `:18` | 列名有，入口欄指到 `proto8/docs/CONCEPTS.md`、`proto8/thinking/`，沒連 `W/ideas/README.md` |
| `spec/` | `:19` | 同上，指到 NORMS／CONVENTION |
| `workshop/` | `:21` | 有 |
| `hackathon/` | `:22` | 有 |
| `experiments/` | `:23` | 有 |
| `investigations/` | `:24`（經單檔 `investigation.md`） | 夾本身沒列，是報告落點 |
| `refactor/` | `:26-27` | 有 |
| `dev-env/` | `:28`（經 `dev-env.md`） | 夾是分檔 |
| `digest/` | `:30` | 有 |
| `common/` | `:13`（conventions）、`:45`（gotchas）、`:49`（user） | `common/data-files.md` 沒列 |
| `tidy/` | `:46` | 有 |
| `dispatch/` | `WORKFLOWS-parts/01:9` | 有 |
| `team-model/` | `WORKFLOWS-parts/01:10`（經 `team-model.md`） | 有 |
| 單檔 `testing`、`planning`、`decisions.json`、`decide-page`、`inbox.json`、`resources` | `:25`、`:47`、`:48`、`:50`、`parts/01:7-8`、`parts/01:11` | 有 |
| `TEMPLATE.workflow.md` | `:56` | 有 |
| `TEMPLATE.handoff.md` | — | 沒列（`W/_index.json` 有） |

**B1**｜（現況吻合）｜每個工作流資料夾都有對應的列，每列指到的東西都存在｜上表＋連結檢查｜確定。
**B2**｜找不到｜`wf/WORKFLOWS.md` 全檔｜沒有任何一列通往：`wf/public/`（公用知識庫，`recipes.md`、`patch-and-commit.md`、`sol-crew.md` 等 12 檔＋`tools/`）、`wf/advices/`（7 檔）、`W/dispatch/kits/`、commit 排隊（`commit-request`）、使用者專區｜grep `wf/public|wf/advices|public/README|advices/`：`AGENTS.md`、`wf/WORKFLOWS.md`、`wf/INDEX.md`、`wf/INDEX/`、`wf/STRUCTURE.md`、`W/common/README.md`、`W/dispatch/README.md`、`W/dispatch/aos-teams.md` 都是 0 筆；提到它們的只有 `wf/_index.json`、`W/TEMPLATE.handoff.md:12,33`、`W/dispatch/kits/card.md` 與它們自己｜確定。
**B3**｜過時｜`wf/WORKFLOWS.md:66`｜「等使用者做／驗證／決定 → WAIT_USER.md」｜R-zone（見 A1）｜確定。
**B4**｜重複｜`wf/WORKFLOWS-parts/02-統一形式.md:3-5` 與 `wf/WORKFLOWS.md:58-60`｜兩處都只是一句「出處在 STRUCTURE」的指標；`WORKFLOWS.md` 沒有任何連結指到 `02`（只有 `01:1` 的「下一份」連過去）｜確定。
**B5**｜（事實）｜`wf/WORKFLOWS.md:54`｜multi-agent 那張表（1,262 bytes）拆到 parts，而 `WORKFLOWS.md` 本身 6,936 bytes，合回去 8.2 KB 左右｜確定。
**B6**｜找不到｜`wf/WORKFLOWS.md:21,22`｜「已累積的紀錄與待決問題見 INDEX」「已辦場次見 INDEX」；兩份 INDEX 都沒有這些內容（A27、A34）｜確定。
**B7**｜（事實）｜`wf/WORKFLOWS.md:20`｜「roadmap」那列沒有對應的工作流檔，入口欄直接是 `SESSION-LOG.md`；`:41` 分組名「kernel 內建」撞名見 A17｜確定。
**B8**｜（現況吻合）｜`W/_index.json` 的鍵跟 `W/` 實際內容完全一致（多 0、少 0）；`wf/_index.json` 只少 `temp`（已 gitignore）；`wf/tools/_index.json`、`wf/tools/progress_board/_index.json` 也一致｜腳本比對｜確定。

## C. `wf/INDEX.md`、`wf/INDEX/`、`wf/STRUCTURE.md`

大小：`INDEX.md` 4,068；`INDEX/01-repo-layout.md` 3,930、`INDEX/README.md` 116；`STRUCTURE.md` 8,191。
**`STRUCTURE.md` 有別人還沒 commit 的改動（只有 `:59` 一行，補了「11-14 已整夾封存進 `workflows/common/archive/`（97cda3435）」）；以下講的都是工作樹版。**`wf/WAIT_USER.md` 也有別人未 commit 的改動（少 2 行）。

實際的 `wf/` 頂層：`advices/ HANDOFF.md inbox/ INDEX/ _index.json INDEX.md knowledge/ public/ salvage/ SESSION-LOG.md session_logs/ STRUCTURE.md temp/ tools/ wait-user/ WAIT_USER.md workflows/ WORKFLOWS.md WORKFLOWS-parts/`。
實際的 repo 根：`AGENTS.md archive/ .claude/ CLAUDE.md .git .gitattributes .gitignore impl_cpp/ proto8/ README.md .vscode/（未追蹤） wf/`。
實際的 `proto8/` 頂層：`archive cases cmd docs extras feedback impls install.sh kernel knowledge lib notes py README.md schema（未追蹤） templates thinking user-advice _index.json`。

**C1**｜找不到｜`wf/INDEX.md:21-31`「頂層文件（`wf/` 這一層）」表｜沒列 `public/`、`advices/`、`knowledge/`、`tools/`、`salvage/`、`temp/`、`INDEX/`、`WORKFLOWS-parts/`、`_index.json`（`inbox/` 在 `:54`、`knowledge/code-map.json` 在 `:13,38` 有提）｜上面的 ls｜確定。
**C2**｜過時｜`wf/INDEX/01-repo-layout.md:5`｜「在兩台機器上開發，checkout 路徑不同（家裡 Linux／WSL、公司 Windows）」｜`AGENTS.md:45`、`W/dev-env.md:35`：家機 Manjaro、公司 WSL，兩台 repo 都在 `~/repo/aos`｜確定。
**C3**｜找不到｜`wf/INDEX/01-repo-layout.md:7-17` 佈局表｜沒列 `wf/public/`、`wf/advices/`、`wf/knowledge/`、`wf/temp/`、`wf/session_logs/`、`wf/wait-user/`、`.gitattributes`；`proto8/` 那格（`:9`）沒點名 `knowledge/`（aos 知識庫的來源，活樹那份是複本，`aos-teams/06:10`）、`extras/`、`cases/`、`feedback/`、`notes/`、`archive/`（該格有寫「各夾一覽在 proto8/README」）｜ls｜確定。
**C4**｜過時｜`wf/INDEX/01-repo-layout.md:14`｜`wf/tools/` 寫成「kernel 工具：`tabledb.py`、`find_big_lists.py`、`fix_moved_links.py`、`check_anchors.py`…`compact_reload.sh`」｜實際頂層有 30 多個檔與 `progress_board/`、`decide_page/`、`tests/`，其中 `index_gen.py`（鐵律 3 的生成器）、`commit-request`／`commit_queue.py`、`index_check.py`、`json_text.py`、`quiet*.py` 都沒提｜見 E｜確定。
**C5**｜跟程式對不上｜`wf/INDEX/01-repo-layout.md:15`｜salvage「七篇」｜`wf/salvage/README.md:5`「六篇正文（01～06）」；`wf/salvage/archive/` 實際 01～06 共 6 篇＋README｜確定。
**C6**｜找不到｜`wf/INDEX.md:52`；`wf/STRUCTURE.md:69,78`｜「進度 hub → 各工作流 session-log」、資料夾型工作流可有 `session-log.md`｜整個 `W/` 沒有任何 `session-log.md`；`wf/SESSION-LOG.md:47-52` 那張表是空的｜確定。
**C7**｜跟程式對不上｜`wf/STRUCTURE.md:16`｜「下層檔不向上連 AGENTS.md」｜`W/` 非 archive 有 5 檔連回 `AGENTS.md`：`W/feature-dev/README.md:3,5`、`W/common/user.md:5`、`W/common/README.md`、`W/common/conventions.md`、`W/dispatch/aos-teams/05-…md`；另 `wf/HANDOFF.md:3`、`wf/salvage/README.md:1`｜grep｜確定。
**C8**｜跟程式對不上｜`wf/STRUCTURE.md:83`｜封存檔「檔頭第一行加 `> 封存 YYYY-MM-DD…`」｜`wf/` 各 `archive/` 底下非 README 的 md 共 520 份，第一行以 `> 封存` 開頭的 193 份｜腳本數的｜確定。
**C9**｜跟程式對不上｜`wf/STRUCTURE.md:84-85`（活文件不連進 archive，只有 `archive/README.md` 索引可以連過去）｜活文件連進 archive 的有：`W/ideas/README.md:3`→`common/archive/ideas/README.md`、`W/spec/README.md:3`→`common/archive/spec/README.md`、`W/hackathon/README.md:43`→`workshop/archive/README.md` 與 `common/archive/README.md`｜後兩個連的是 archive 的索引檔本身，算不算違規條文沒講清｜連結存在確定；算不算違規，猜。
**C10**｜過時｜`wf/STRUCTURE.md:29`｜「程式碼單檔 > 300 行」門檻｜`W/common/user/02-交接與收工.md:11`「開發階段不設行數上限（2026-10-09 定）」；`wf/tools/commit_queue.py` 812 行、`index_gen.py` 390 行｜兩句並存確定；哪句算數不判。
**C11**｜過時｜`wf/STRUCTURE.md:19`｜「等使用者的記 `WAIT_USER.md`」「兩者膨脹就分別拆 `session_logs/`／`wait-user/`」｜R-zone；`wf/SESSION-LOG.md` 現在 17,260 bytes 沒拆，而 `session_logs/` 實際是每日日誌（`wf/INDEX.md:28`）不是 SESSION-LOG 的分檔｜確定。
**C12**｜過時｜`wf/STRUCTURE.md:51,61`｜舉例「改不到的外部連結（例如 proto5/ 內）」「mktemp 世界、`.aos/` 動態狀態進了版控就 `rm --cached`」｜proto5 已在 `archive/`；`.aos/` 動態狀態是單一執行檔那代的版面（`wf/INDEX/01-repo-layout.md:21`）｜猜（例子過時，規則本身沒查）。
**C13**｜太長｜`wf/STRUCTURE.md` 8,191 bytes，離它自己 `:27` 的 8192 門檻差 1 byte；`W/dispatch/aos-teams.md` 8,187（差 5）｜`W/tidy/gotchas.md:22` 自己寫過「入口壓在 8192 邊緣時再改一個字就爆」｜確定。
**C14**｜（事實）｜`wf/STRUCTURE.md:20`「鐵律 3–5 條」｜`AGENTS.md:35-40` 現有 6 個編號、1 號已刪，有效 5 條｜吻合，確定。

## D. `wf/knowledge/code-map.json` 與 `code-map/`

**D1**｜（事實）｜是生成的嗎｜`wf/knowledge/code-map/proto8/*.json` 11 份是生成物：每份有 `generated_by: "wf/tools/index_gen.py"`，`wf/tools/index_gen.py:21` 寫「同一次也寫逐檔 code map」，範圍在 `wf/tools/index_gen.json` 的 `codemap` 段。`wf/knowledge/code-map.json`（7,949 bytes）是**手寫**的入口（它的 `_description`：「本檔手寫；`wf/knowledge/code-map/` 底下是生成物，別手改」）｜確定。
大小（讀的當下；`lib.json` 在我讀的幾分鐘內從 45,363 變 45,652，有人正在重生）：`impls.json` 29,468（217 葉）、`lib.json` 45,652（279）、`cmd.json` 21,078（132）、`knowledge.json` 11,357（147）、`templates.json` 9,168（70）、`extras.json` 3,879（22）、`py.json` 3,733（19）、`kernel.json` 2,230（20）、`cases.json` 1,216（11）、`feedback.json` 575（5）、`proto8.json` 514（1）；整個 `wf/knowledge/` 約 136.5 KB。
**D2**｜（事實）｜`proto8/` 哪些夾不在 code map｜刻意跳過的 5 個：`thinking`、`archive`、`notes`、`user-advice`、`docs`（`index_gen.json` `codemap.skip_top`；`code-map.json` 的 `not_code` 同說法）。其餘有追蹤檔的頂層夾 10 個（cases、cmd、extras、feedback、impls、kernel、knowledge、lib、py、templates）都有一份｜確定。
**D3**｜找不到｜`proto8/schema/`｜不在 code map、也不在 `code-map.json` 的 `domains`｜它整夾未追蹤（`git ls-files proto8/schema` 0 筆），生成器掃的是 `git ls-files`；同樣還沒進去的未追蹤夾：`proto8/cmd/aos-comm/`、`proto8/lib/aos/comm/`、`proto8/lib/agent/board_{clear,ls,read,set,wait}/`、`proto8/templates/kits/`、`proto8/lib/packs/comm.json`｜`git status`｜確定（是別人做到一半的東西）。
**D4**｜找不到｜`aos-user` 指令｜`AGENTS.md:36,52`、`W/common/user.md:14`、`wf/WAIT_USER.md:16` 都叫 agent 用 `aos-user send`／`verify`；但 repo 裡（archive 以外）`find -name 'aos-user*'` 只有 `proto8/user-advice/2026-09/aos-user.md`，`proto8/cmd/` 沒有 `aos-user`，code map 只有包裝它的 `proto8/lib/agent/user_send/`、`user_verify/`。實體在活樹工作區 `~/aos-home/ws/tools/aos-user/`（`WAIT_USER.md:16` 寫的路徑，存在）｜確定（repo 內找不到）；是不是故意不進 repo，猜。
**D5**｜（事實）｜code map 的範圍只有 `proto8/`｜`wf/tools/`（70 多檔，含 812 行的 `commit_queue.py`）、`wf/public/tools/`、`impl_cpp/` 都不在 code map；`wf/tools/` 另有自己的 `_index.json`｜`index_gen.json` `codemap.out`｜確定。
**D6**｜找不到｜`wf/tools/__pycache__/codemap_gen.cpython-314.pyc`、`quiet.cpython-314.pyc` 等｜`codemap_gen.py` 原始檔已不在（`b21bec87e` 說變薄殼，之後刪），只剩快取（`.gitignore:19` 忽略，不在版控）｜確定。

## E. `wf/tools/` 每支腳本

「文件有提」＝在 `AGENTS.md` 或 `wf/` 底下（不含 temp、session_logs、salvage、code-map、`wf/tools/` 自己）的 md／json 裡出現檔名；括號是最後 commit 日。`wf/tools/_index.json` 每一支都有一句。

| 腳本 | 是什麼 | 文件有提嗎 |
|---|---|---|
| `index_gen.py`（11-14，390 行）＋`index_gen.json`＋`index_gen_desc.json`（168,668 bytes，手寫的一句話表） | 從檔頭一句話生成各夾 `_index.json` 與逐檔 code map | 有：`AGENTS.md:37`、`user.md:12`、`dev-env.md:29`、`feature-dev/README.md:13` 等 9 處；`index_gen.json` 沒有文件提 |
| `codemap_lib.py`（11-13） | index_gen 用的「檔頭一句話」認法函式庫，沒有命令列 | 檔名沒人提（`wf/_index.json` 提到「codemap_lib」） |
| `index_check.py`（11-13） | 查 `_index.json` 跟樹對不對得上 | 有：`dev-env.md:29`、`user.md:12`、`SESSION-LOG.md` |
| `check_anchors.py`（11-13） | 查 md 連結的 `#錨點` | 有：`dev-env.md:28`、`user.md:12`、`refactor/moving-things.md:80` 等 7 處 |
| `commit-request`（190 bytes 薄殼）＋`commit_queue.py`（11-14，812 行） | commit 排隊：申請者拿鎖、在 repo 外組 commit、推進 main | 有：`aos-teams/06:24`、`07:30,38`、`dispatch/kits/card.md`、`wf/advices/指令與工具.md`、`wf/public/patch-and-commit.md` 等 8 處；入口鏈沒提（見開頭注意） |
| `compact_reload.sh`（10-20） | compact 後的 SessionStart hook：印 user.md＋分檔＋HANDOFF 第一條 | 有：`HANDOFF.md:5`、`user/02`、`INDEX/01:14,16`；`.claude/settings.json` 掛著 |
| `tabledb.py`（09-01）＋`tabledb_fmt.py`、`tabledb_fmt_vars.py`、`tabledb_links.py`、`fmt-vars.json` | `wf-table/1` 資料檔的讀寫與連結解析、`$fmt` 路徑代號 | `tabledb.py` 有（`AGENTS.md:40`、`STRUCTURE.md:89`、`common/data-files*.md` 等 9 處）；`tabledb_links.py`、`fmt-vars.json` 各 1 處；`tabledb_fmt.py`、`tabledb_fmt_vars.py` 沒人提（內部模組） |
| `find_big_lists.py`（11-13） | 找 md 裡超過門檻的表格／清單 | 有：`tidy/README.md:16,38,41`、`common/data-files*.md` 等 5 處 |
| `fix_moved_links.py`（09-01）＋`fix_moved_links_fmt.py` | 搬檔後照 `舊<TAB>新` 重寫相對連結 | 前者有（5 處）；後者沒人提（內部模組） |
| `json_text.py`＋`json_text_cli.py`（11-13） | 把 json 展開成逐行文字給 git diff 用 | 有：只在 `dev-env.md:20` |
| `metainfo_migrate.py`（11-07） | 一次性搬舊的 metainfo 欄位 | **沒有任何文件提** |
| `quiet.py`、`quiet_hook.py`、`quiet_tick.py`、`autoreply_tick.py`（11-14） | 清淨時段：擋下新信／kernel_hold 通知、到期合成一則、替來信自動回 | 只在 `wf/public/`：`public/tools/quiet/README.md`、`public/tools/README.md`、`public/recipes.md` |
| `quiet-README.md`（11-14，2,537 bytes） | 上面四支的英文說明 | **沒有任何文件提**；跟 `wf/public/tools/quiet/README.md`（2,710 bytes）幾乎同文 |
| `progress_post.sh`（11-07）、`progress_answers.sh`（11-07）、`forum_post.sh`、`forum_admin.sh`（11-08） | 寫一筆進度到桌面看板、讀看板回答、論壇貼文與管理 | 有：`aos-teams.md`、`aos-teams/04-進度回報.md`、`decide-page.md:8,15,58`、`user/01` |
| `progress_board/`（11-13；`dash.py`、`collect.py`、`forum.py`、`eli5.py`、`summarize.py`、`remote_sync.py` 等 18 支＋`designs.json` 151,626 bytes＋`README.md` 12,060） | 本機進度看板伺服器、彙整、論壇、白話解說、遠端同步 | 各支檔名沒人提，靠夾內 `README.md` 與 `_index.json` |
| `decide_page/`（11-13；`decide_page.py`、`model.py`、`render.py`、`reply.py`、`README.md`、`web/`） | 把一批待裁題做成離線互動頁、讀回答、落地 | `decide_page.py` 有（`decide-page.md:57-62`）；其餘內部模組沒人提 |
| `tests/`（9 支：`test_commit_queue.sh` 15,159、`test_index_tools.py`、`test_index_check_edges.py`、`test_codemap_json.py`、`test_json_text*.py`、`test_quiet.py`、`test_autoreply.py`、`test_metainfo_migrate.py`） | 上面各工具的測試 | 沒有文件提（`W/testing.md` 沒列 wf/tools 的測試） |

**E1**｜找不到｜`wf/tools/metainfo_migrate.py`＋`tests/test_metainfo_migrate.py`｜沒有任何文件提到；檔頭自述是「一次性」搬舊欄位｜`W/common/user.md:20`「proto8 不寫遷移、不做舊格式相容」（11-05，比這支 11-07 早）｜沒人提確定；是不是死的，猜。
**E2**｜重複｜`wf/tools/quiet-README.md` 與 `wf/public/tools/quiet/README.md`｜同一份說明兩處，public 那份多一段引言與一行檔案位置；程式本體只在 `wf/tools/`，`wf/public/tools/quiet/` 只有 README｜`diff`｜確定。
**E3**｜過時｜`wf/tools/progress_post.sh`、`progress_answers.sh`、`forum_*.sh`、`progress_board/`、`decide_page/`｜文件（`aos-teams/04`、`decide-page.md`）仍叫各線用看板回報與問題；`user.md:14`（11-14）說題目寄專區、他看全景頁；這台 `~/Desktop/aos-進度/` 最新檔 11-08 23:29、沒有 `dash.py` 行程；`progress_board/config.json:3,6` 還掛著 arknights 的站與 `~/code/playground-ak`（arknights 凍結，`user.md:19`）｜規則並存確定；看板已停用，猜。
**E4**｜找不到｜文件提到、但不存在的腳本：
  - `wf/tools/wf-lint.sh`：現役區 14 處（都在 `W/tidy/reports/` 的 10-02、10-13、10-20 報告與 `W/refactor/reports/…sol審查/11-使用者裁定/01-落實結果.md:48`），archive 5 處。11-13 刪（`70e6d4fd8`）。
  - `wf/tools/codemap_gen.py`：現役區 2 處（A13），archive 3 處。
  - `wf/tools/inbox_send.sh`（`inbox_*.sh`）：`wf/inbox/done/20261107T15*-aos-a0-*-REQUEST.md` 8 封的正文；`W/inbox.json` `_description` 自己寫 11-13 已刪。
  都是當時的紀錄或信，不是現行指示｜確定。
**E5**｜找不到｜`wf/public/發佈前檢查.md:23,48`、`wf/public/tools/doc-run/README.md:28`｜出處寫 `wf/temp/ok-release/bin/run-doc.py`、`wf/temp/ok-release/drafts/tools/check-cmds.py`、`scan.py`；這些檔在這台存在，但 `wf/temp/` 已 gitignore（`.gitignore:35`），別台或別的 clone 看不到｜確定。
**E6**｜（事實）｜`W/testing.md` 全檔沒提 `wf/tools/tests/`（9 支測試）怎麼跑｜grep｜確定。

## F. 超過 8000 bytes 的 `.md`／`.json`

範圍：`wf/` 底下，不含 `temp/`、`session_logs/`、`salvage/`、`knowledge/code-map/`。共 **92** 個，其中不在任何 `archive/` 的 **26** 個（下表全列）；在 `archive/` 的 66 個列在後面。

| bytes | 路徑（非 archive） |
|---|---|
| 168,668 | `wf/tools/index_gen_desc.json` |
| 151,626 | `wf/tools/progress_board/designs.json` |
| 82,559 | `W/refactor/reports/2026-11-07-sol審查/decide_20261107_sol.json` |
| 39,990 | `W/refactor/reports/2026-11-07-arknights-kb/01-盤點-語料.md` |
| 27,064 | `W/tidy/reports/2026-11-12-收尾.md` |
| 21,288 | `W/refactor/reports/2026-11-07-arknights-kb/08-第二輪簡報.md` |
| 17,260 | `wf/SESSION-LOG.md` |
| 14,174 | `W/refactor/reports/2026-11-07-sol審查/11-使用者裁定/01-落實結果.md` |
| 13,202 | `W/dispatch/aos-teams/07-預設流程與agent-fsm.md` |
| 12,817 | `W/refactor/reports/2026-11-07-sol審查/01-設定檔.md` |
| 12,319 | `W/refactor/reports/2026-11-07-arknights-kb/01-盤點-aos.md` |
| 12,060 | `wf/tools/progress_board/README.md` |
| 10,728 | `W/refactor/reports/2026-11-07-arknights-kb/03-W1到W4施工結果.md` |
| 9,311 | `wf/advices/fsm範本.md` |
| 9,064 | `W/refactor/reports/2026-11-07-arknights-kb/04-第一輪實跑.md` |
| 8,772 | `W/dispatch/aos-teams/03-使用者原話.md` |
| 8,560 | `W/dispatch/CLAIMS.md` |
| 8,216 | `wf/public/recipes.md` |
| 8,191 | `W/refactor/reports/2026-11-07-sol審查/03-條文-no-pid-tick-json-argv-special-cases/01-no-pid-P5b.md` |
| 8,191 | `wf/STRUCTURE.md` |
| 8,187 | `W/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md` |
| 8,187 | `W/dispatch/aos-teams.md` |
| 8,117 | `W/tidy/reports/2026-11-03-收斂/05-11-04晚-P2-P3-P4續.md` |
| 8,094 | `W/refactor/reports/2026-11-07-sol審查/05-代定盤點/01a-未裁逐條-1～6.md` |
| 8,040 | `W/team-model.md` |
| 8,032 | `wf/inbox/done/20261108T1310-arcagi-PROGRESS.md` |

**F1**｜太長｜非 archive 的現役規則檔裡超過 8192 的：`wf/SESSION-LOG.md` 17,260、`W/dispatch/aos-teams/07-…md` 13,202、`W/dispatch/aos-teams/03-使用者原話.md` 8,772、`W/dispatch/CLAIMS.md` 8,560、`wf/public/recipes.md` 8,216、`wf/advices/fsm範本.md` 9,311、`wf/tools/progress_board/README.md` 12,060｜`wf/STRUCTURE.md:27` 的門檻 8192｜確定。
**F2**｜太長｜兩份手維護的大 json：`wf/tools/index_gen_desc.json` 168,668（生成器的「取不到檔頭時的手寫一句話」表）、`wf/tools/progress_board/designs.json` 151,626｜確定。
**F3**｜太長｜貼著門檻的四份：`wf/STRUCTURE.md` 8,191、`W/dispatch/aos-teams.md` 8,187、`W/refactor/reports/…/11-使用者裁定.md` 8,187、`…/01-no-pid-P5b.md` 8,191｜確定。

在 `archive/` 的 66 個（bytes<TAB>路徑）：

```
198703	wf/workflows/common/archive/spec/archive/data/conformance.json
59114	wf/workflows/common/archive/spec/archive/notes/edge-cases.json
31254	wf/workflows/common/archive/ideas/archive/program-form.md
26541	wf/workflows/common/archive/ideas/archive/verdicts.md
24295	wf/workflows/common/archive/ideas/archive/cpu-to-os-gaps.json
20500	wf/workflows/common/archive/wait-user-2026-10-12/decided-2026-09-24.md
20386	wf/workflows/common/archive/ideas/archive/README-old.md
19474	wf/workflows/common/archive/ideas/archive/scheduling/README.md
17367	wf/workflows/common/archive/ideas/archive/ai-core-field/f1-origin.md
17341	wf/workflows/dispatch/archive/trial/archive/sandbox/solo/C/ws-lm/listen-cat-log-copy.md
16717	wf/workflows/common/archive/wait-user-2026-10-12/company-market.md
15317	wf/workflows/common/archive/ideas/archive/ai-core-field/f2-handy-unipath.md
15201	wf/workflows/common/archive/ideas/archive/os-metrics-and-resources.md
14769	wf/workflows/common/archive/wait-user-2026-10-12/digest-2026-10-05.md
14271	wf/workflows/common/archive/ideas/archive/ai-core-field/f3-llm-material.md
13777	wf/workflows/common/archive/spec/archive/plan-skeleton.md
13006	wf/workflows/common/archive/ideas/archive/turing-to-os.md
12503	wf/workflows/common/archive/ideas/archive/13-holes-and-play.md
12467	wf/workflows/common/archive/ideas/archive/05-write-compile-run.md
12466	wf/workflows/common/archive/spec/archive/07-call-and-delivery.md
12466	wf/workflows/common/archive/spec/archive/06-exec-and-run.md
12460	wf/workflows/common/archive/spec/archive/13-doorman-l1.md
12454	wf/workflows/common/archive/spec/archive/08b-daemon-reconcile.md
12444	wf/workflows/common/archive/spec/archive/05-series-format.md
12436	wf/workflows/common/archive/ideas/archive/11-tools-and-contacts.md
12431	wf/workflows/common/archive/spec/archive/08-daemon.md
12428	wf/workflows/common/archive/spec/archive/03-source-and-compile.md
12413	wf/workflows/common/archive/ideas/archive/09-call-and-failure.md
12381	wf/workflows/common/archive/spec/archive/12-cli.md
12356	wf/workflows/common/archive/ideas/archive/12-cli-and-layering.md
12342	wf/workflows/common/archive/ideas/archive/01-what-and-goals.md
12295	wf/workflows/common/archive/spec/archive/09-llm-world.md
12256	wf/workflows/common/archive/spec/archive/09b-llm-queue.md
12040	wf/workflows/common/archive/ideas/archive/core-layering.md
12036	wf/workflows/common/archive/ideas/archive/02-folders-as-lists.md
11941	wf/workflows/common/archive/ideas/archive/10-doorman.md
11904	wf/workflows/common/archive/ideas/archive/03-land-and-life.md
11408	wf/workflows/common/archive/spec/archive/04-inst-format.md
11354	wf/workflows/common/archive/ideas/archive/06-time-and-clocks.md
11284	wf/workflows/common/archive/spec/archive/notes/asset-inventory.json
11216	wf/workflows/common/archive/spec/archive/11-tools-and-contacts.md
11203	wf/workflows/common/archive/spec/archive/02-layout.md
11188	wf/workflows/dispatch/archive/trial/archive/sandbox/solo/tasks/D.full.md
11154	wf/workflows/common/archive/spec/archive/10-agent.md
11062	wf/workflows/common/archive/ideas/archive/07-daemon.md
10966	wf/workflows/common/archive/ideas/archive/04-inside-aos.md
10733	wf/workflows/common/archive/ideas/archive/08-agent.md
10176	wf/workflows/dispatch/archive/trial/archive/sandbox/solo/tasks/C.full.md
10150	wf/workflows/dispatch/archive/trial/archive/sandbox/team/opC/operator-C-report.md
9946	wf/workflows/common/archive/ideas/archive/llm-cpu.md
9860	wf/workflows/common/archive/spec/archive/notes/defaults-review.json
9339	wf/workflows/common/archive/ideas/archive/game-process-model.md
9331	wf/workflows/dispatch/archive/trial/archive/sandbox/solo/tasks/A.full.md
9090	wf/workflows/dispatch/archive/trial/archive/sandbox/solo/tasks/B.full.md
9086	wf/workflows/common/archive/ideas/archive/self-delivery-in-loop.md
8961	wf/workflows/common/archive/roadmap.md
8848	wf/workflows/common/archive/spec/archive/06b-run-rules.md
8514	wf/workflows/common/archive/spec/archive/01-terms.md
8427	wf/workflows/common/archive/ideas/archive/README.md
8397	wf/workflows/common/archive/ideas/archive/home-daemon-spec.md
8274	wf/workflows/common/archive/ideas/archive/tools/registry.md
8258	wf/workflows/common/archive/ideas/archive/top-down-cli.md
8211	wf/workflows/common/archive/ideas/archive/machine-shape/loop.md
8182	wf/workflows/common/archive/ideas/archive/top-to-bottom/03-inside-aos.md
8057	wf/workflows/dispatch/archive/proto/done/proto-D-heartbeat.md
8052	wf/workflows/workshop/archive/background/README.md
```
