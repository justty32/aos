← [工具大開發時代](README.md)｜[notes 索引](../README.md)

# 三波開發計畫

- **第一波**：workflows 團隊的最短路徑，而且**沒有牆也安全**——工具只寫固定位置（自己的 `outbox/`、團隊資料夾）或跟 base 一樣關在工作根目錄；跑任意程式的只給人用，或只准名冊白名單裡的指令。
- **第二波**：要牆（[agent-access](../2026-09-24-agent-access/README.md) 的 `access.json`＋bwrap，另一隊正在做）才安全的——跑任意程式、碰家外映射、唯讀看信任資料。
- **第三波**：錦上添花，而且大多是「讓模型做更多事」，照治理原則放最後。

工具代號見 [catalog.md](catalog.md)。

## 開隊前先定死的兩個格式（各隊共用，避免互等）

**`team.json`**（團隊資料夾的根；T-team 那隊擁有它的規範 `spec/team/`，其他隊照這份草稿寫、有要改的寄信給那隊）：

```json
{"_metainfo": {"_type": "aos_team", "_version": 1},
 "project": "../p",
 "members": {
   "lead":     {"template": "lead",     "model": "smart", "mail_to": ["worker-1", "reviewer", "human"]},
   "worker-1": {"template": "worker",   "model": "cheap", "mail_to": ["lead", "human"]},
   "reviewer": {"template": "reviewer", "model": "mid",   "mail_to": ["lead", "human"]}},
 "limits": {"stale_minutes": 10, "max_members": 6}}
```

成員的家在 `<團隊>/members/<名>/`；團隊共用的在 `<團隊>/team/`：`mail.log`、`tasks/`、`wait-user/`、`routes.json`、`routines.json`、`schedule.json`、`route.log`。人的名字固定是 `human`。

**信**（`<成員家>/outbox/<id>.json`，`id`＝`<epoch ns>-<pid>-<寄件者>`）：

```json
{"id": "…", "from": "worker-1", "to": "lead", "status": "DONE", "reply_to": "t-0001", "text": "…", "at": "2026-09-25T10:00:00+08:00"}
```

`status` 只准 REQUEST／DONE／BLOCKED／NEEDS-USER／FAILED／PROGRESS（workflows 原樣）。郵差投進收件人 `input/` 的是一則 user 訊息，第一行 `【來信 worker-1 → lead · DONE · t-0001】`。

---

## 第一波：workflows 團隊跑起來（建議 4 隊並行＋1 隊收尾）

| 隊 | 工具 | 模型（照調度慣例） | 領地（新檔為主） | 跟誰可能撞 |
|---|---|---|---|---|
| 1 骨架 | T-team、T-template、T-route、T-handoff（任務表）、T-ask 的人那半（`aos-team answer`） | Opus | 新 `cli/aos-team`、`lib/aos_team*.py`、`proto5/templates/`、新 `spec/team/`；`aos_agent_init.py`（加 `--template`） | 隊 2（team.json 讀法）→ 共用上面草稿 |
| 2 郵差 | T-say（工具包 `team`：`team_say`、`handoff`、`ask_human`）、T-post（郵差＋書記）、T-verify、T-beat | Opus | 新 `proto5/tools/team/`、`lib/aos_team_post.py`、`lib/aos_team_verify.py` | 隊 1（`aos-team` 的子命令分派：隊 1 留好 `mail`／`verify`／`routine` 三個入口，隊 2 只填實作） |
| 3 檔案＋workflows 包 | T-wf、T-md、T-json、T-directive | gpt-sol（量大、照規格） | 新 `proto5/tools/wf/`、`proto5/tools/files/`、`cli/aos-json`、`cli/aos-directives` | 幾乎不撞 |
| 4 記憶 | T-context（人用）、T-compact（機械版＋`compact_request`）、T-notes（放工作根目錄的版本） | Opus（碰 tick 鎖與記憶恢復規則，最難） | `lib/aos_agent_compact.py`、`lib/aos_agent_context.py`、`aos_agent_cli.py`（加兩個子命令）、`spec/agent/`（記憶一節）、`spec/aos-agent/` 新兩檔 | talk 那隊（`/context` 的算法——**先等 talk 合進 main**，或跟它拿那個函式搬進 `aos_agent_context.py`，talk 改叫它） |
| 5 收尾（前四隊合完才開） | T-score、三個模板的人格定稿、`routes.json`（IMPORT 用）、真跑驗收、試玩 | Opus；試玩派 gpt-sol 當新手 | `lib/aos_team_score.py`、`proto5/templates/*/prompts/`、`proto5/tutorials/07-team.md`、notes | 全部（最後一個合） |

合併順序：3 → 1 → 2 → 4 → 5（3 最獨立先合；1 定下 `aos-team` 骨架；2 填子命令；4 最可能跟 talk 撞，放後面）。每隊 ff-merge 前 `git reset` 到最新 main 重跑測試（照慣例在主 repo 做）。

### 任務書骨架（每隊一份，把 ⟨…⟩ 填掉就能開）

```text
你是 aos proto5「工具大開發時代」第一波 ⟨隊名⟩ 隊。用繁體中文、白話。
你在 git worktree 裡；第一步 git reset --hard main。

## 目標
⟨一句話⟩。工具規格照 proto5/notes/2026-09-24-tool-era/catalog.md 的 ⟨T-xxx…⟩；
team.json 與信的格式照 plan.md〈開隊前先定死的兩個格式〉（要改先寫進報告，不要自己改格式）。

## 先讀
proto5/README.md、proto5/tools/README.md＋tools/base/（工具寫法）、spec/agent/info.md §3.3（工具檔）、
spec/aos-agent/cli-talk.md（say 投檔）、notes/2026-09-24-tool-era/{workflows-as-team,catalog,axes}.md、⟨本隊額外的⟩。
~/repo/workflows 唯讀，要用它的腳本就複製進工具包並記版本戳。

## 領地
可以新增／修改：⟨檔案清單⟩。不准碰：⟨其他隊的領地⟩、lib 其他檔（要改就寫進報告交調度者）。

## 規則（照 catalog〈共同規則〉）
規則放工具不放人格；不給模型「等」的工具；工具描述越短越好（報告附每個工具的描述字數）；
成功純文字退 0，失敗最後一行 JSON 退 1；寫檔一律暫存檔＋rename；崩在半路重跑同一行能收回。
不叫模型（除非 catalog 寫了）；不跑 LM Studio。真模型只用 LiteLLM localhost:4000 的 deepseek-chat。

## 交付
1. 程式＋單元測試（cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test 全綠，報新增幾條）。
2. 規範：⟨新檔或改哪一節⟩；lib/README、tools/README、proto5 README 指令表補行。
3. 報告 proto5/notes/2026-09-2x-tool-era-⟨隊名⟩.md：做了什麼、真跑輸出、每個工具六軸自評（axes.md §5 模板，量得到的附數字）、
   跟格式草稿不合的地方、要使用者拍的。notes/README.md 加一列。
4. astra 唯讀審查：寫 review-task.md，codex exec -m gpt-6-astra -C <worktree> -s read-only -o <報告夾>/review-astra.md - < 任務書；必修全修。

## 驗收（寫死 ⟨N⟩ 條）
⟨見下面各隊⟩

## 規則
不推、只在 worktree commit；commit 訊息繁中，結尾兩行照調度者給的。
最後一則訊息：worktree 路徑、分支、commit、測試數字、六軸一句話、要調度者合併時注意的檔。
```

### 各隊驗收（寫死）

- **隊 1 骨架**（6 條）：① `aos-team init --config` 照草稿生三個成員的家，`aos-agent check` 各自全過；② `start`／`stop`／`ls` 對三個成員都對，`ls` 一行一個；③ `ask` 命中 `routes.json` 的 `tool` 規則時不寫任何成員的 `input/`、直接印工具輸出；④ 命中 `handoff` 規則時 `team/tasks/t-0001.json` 生成、工人 `input/` 多一則開頭是【來信】的訊息；⑤ 沒命中時投給 lead；⑥ `answer q-…` 投回發問者、待辦少一條。
- **隊 2 郵差**（7 條）：① `team_say` 名冊外收件人、非白名單 STATUS 都回 `BadArguments`；② 郵差一次跑完：outbox 的信進收件人 `input/`、原檔進 `outbox/done/`、`mail.log` 多一行；③ 郵差在「投完、沒搬」之間被 KILL，重跑不會投兩次；④ DONE＋交接書 → 驗收員跑；有條不過 → 工人收到 FAILED＋輸出；⑤ 接了單、idle 超過 `stale_minutes`（測試調成秒）沒回終局 → lead 收到 BLOCKED；⑥ 心跳：到期寄 REQUEST、DONE 回來才改「上次執行」；⑦ `aos-kernel add` 反覆工作跑郵差，真 daemon＋kernel 整合測試一條。
- **隊 3 檔案＋workflows**（6 條）：① `wf_init`＋`wf_residue`＋`wf_lint` 在拋棄式資料夾把 heartbeat 包導入、數出殘留；② `json_edit` 五種 op 各一條、壞 pointer、改完非法 JSON 不寫；③ `json_edit` 對 `info.json`／工具檔拒絕（信任資料）；④ `md_section` 標題不唯一回 `NotUnique`、`append_item` 格式不對拒絕；⑤ `aos-directives resolve` 對 agent 的 `info.json` 印出與 `lib/aos_directives.py` 相同的結果；⑥ 每個工具描述字數列表，全包 < 3000 字元。
- **隊 4 記憶**（6 條）：① `aos-agent context` 的數字與 talk `/context` 一致（同一函式）；② `compact --dry-run` 不改檔；③ `compact` 後記憶照 §3.2 驗得過、`tool_calls` 與 `tool` 成對、舊的在 `prompts/archive/`；④ tick 正在跑（鎖被佔）時 `compact` 退 101 不動檔；`batch` 不是 null 時拒絕；⑤ 真模型（deepseek）壓縮後再問一句，回話正常（不 400）；⑥ `compact_request` 只寫旗標，下一次 idle 才做。
- **隊 5 收尾**（驗收＝整個第一波的驗收，見下）。

### 第一波的驗收：真跑一個 workflows 小例子＋六軸打分

**例子**：「把 workflows 的 heartbeat 包導入空專案 `~/tmp/wf-try/p`」（[workflows-as-team §2.4](workflows-as-team.md#24-走一遍驗收例子把-workflows-的-heartbeat-包導入一個空專案)）。Done when 照 workflows 的 `IMPORT.md`：`{{` 0、〔模板說明〕0、〔導入判斷〕0、`wf-lint.sh --strict` 退 0。

1. `aos-team init` 三成員（lead＝聰明、worker＝便宜、reviewer），模型全走 LiteLLM `deepseek-chat`（使用者打遊戲時也能跑）；工人的 base `--root` 指 `~/tmp/wf-try/p`（拋棄式，沒牆也不怕）。
2. `aos-team ask "把 workflows 導入 ~/tmp/wf-try/p，flavor heartbeat，時區 Asia/Taipei，專案一句話：試跑"`。
3. **跑 3 次**（每次刪掉重建 p），記：過幾次、每次的 `aos-team score`。
4. 另加一個「落穿」的例子：`aos-team ask "p 裡的 routines 加一條每天 9 點看信箱"`——門房沒規則，要經過 lead → handoff → worker，看 lead 那一段花多少。
5. 派一位新手（gpt-sol，只拿 README＋教程 07）照做一遍，照 play/ 五條標準打分，報告放 `notes/play/`。

**過關線**（使用者可改）：3 次至少 2 次 Done when 全過；每次模型呼叫 ≤ 25（worker 填字為主），lead 在例子 1 被叫 0 次；`mail.log` 人能一行一行看懂每步誰做；六軸沒有一軸 ≤ 2（B 軸例外：一波沒牆，工人的 bash 本來就是 B1，要在報告寫明）。

---

## 第二波：接上牆（牆那隊合進 main 之後開；建議 3 隊並行）

| 隊 | 工具 | 模型 | 內容 |
|---|---|---|---|
| A 造工具 | T-toolnew、T-tooltest、T-wrap-py | gpt-sol | `aos-agent tools new／test／wrap-py`（放新檔 `aos_agent_tools_dev.py`，跟牆那隊的 `tools ls/add/rm/alias` 分開）；wrap-py 產的工具包預設帶「進牢」設定 |
| B 牆接線 | 把第一波的 T-say、T-verify（`cmd_ok` 開放任意指令）、T-wf、T-notes（改映射 `notes`）、T-context 模型版、T-recall 放進牢 | Opus | 主要改工具檔的 `_meta` 與 `access.json` 模板；團隊模板預設工人只映射專案、outbox、notes |
| C 申請類 | T-access-req、T-persona、T-lock、T-pool | Sonnet（規格清楚、量小） | 都走 T-ask 的待辦；`_pool` 照 priority 提案 |

**驗收**：① 第一波的例子在「工人關牢」下再跑 3 次，結果不變、B 軸從 1 升到 ≥ 4；② 新例子：`tools wrap-py` 包一個小 Python 檔（例如 workflows 的 `find_big_lists.py` 裡的函式），裝給工人，交接書要它用這支工具找出超過 1 KB 的條列——模型沒寫任何 bash 就完成；③ 工人試著 `cat` 別的成員的家、寫 `access.json`，都被擋（逃逸測試照 agent-access 的 experiment.md）；④ 六軸重打一次，跟第一波比。

## 第三波：錦上添花（建議 2～3 隊，挑著開）

| 工具 | 為什麼放最後 |
|---|---|
| T-spawn | 模型生成員＝常駐成本（每個一份反覆工作）＋邊界擴大的風險；先看團隊固定編制夠不夠 |
| T-toolsmith | 模型寫程式給自己用，一定要牆＋人批；第二波的 wrap-py 先證明「人給檔、機械包」夠不夠 |
| T-wrap-cli | 要解析 help 文字，可能要模型 |
| T-compact `--summarize`、T-wrap-py `--describe-with-llm` | 都是「加一次模型」的選項，照治理原則要先證明機械版不夠 |
| T-crystal | 要第一、二波累積的 `route.log` 才有東西可統計 |

**驗收**：每個工具附「機械版 vs 加模型版」的六軸對照；加模型的那個要證明 L 軸的損失換到了什麼（例如門房命中率從 x% 升到 y%）。

## 並行與人力總表

| 波 | 並行隊數 | 前提 | 粗估 |
|---|---|---|---|
| 一 | 4 ＋ 收尾 1 | talk 合進 main（隊 4 要用它的 `/context`） | 各隊 1～2 天；收尾 1 天 |
| 二 | 3 | 牆那隊（`access.json`、bwrap、`tools ls/add/rm/alias`、`access set/rm`）合進 main | 各隊 1～2 天 |
| 三 | 2～3 | 第一、二波的紀錄 | 看挑幾個 |
