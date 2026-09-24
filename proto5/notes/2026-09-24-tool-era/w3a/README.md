← [工具大開發時代](../README.md)｜[notes 索引](../../README.md)｜計畫 [plan.md](../plan.md)｜目錄 [catalog.md](../catalog.md)｜評分 [axes.md](../axes.md)｜規範 [spawn.md](../../../spec/team/spawn.md)、[toolsmith.md](../../../spec/team/toolsmith.md)

# 第三波 W3-1 隊（模型生成員、模型造工具）報告（2026-09-25，**提早收線版**）

**一句話**：兩個申請都做完、有測試、合得進 main；T-spawn 真跑了 2＋2 次，**加模型版比機械版貴、慢、還多卡一次人**，目前換不到東西——**建議只留機械版（人寫名冊），spawn 預設關著**。T-toolsmith 真跑沒來得及做（使用者要關機，提早收線），對照表那半空著。
基底：main `162cc59`（開工 `5984233`，中途 rebase 過 `d6603b9`、`162cc59`）。相關測試檔全綠（見 §6）；**astra 沒審**。

## 1. 做了什麼

| 項 | 做了什麼 | 在哪 |
|---|---|---|
| A T-spawn | 領隊 `spawn_member {"template","name","reason","mail_to"?}` → 郵差 `on_spawn` 照名冊檢查（模板在 `spawn.templates` 白名單、人數含等人批的不超過 `max_members`、新成員 `mail_to` 只能是申請者或它 `mail_to` 裡的、新成員模板的 `may` 不超過申請者）→ 記 `team/spawns/s-NNNN.json`、開一題 `[成員]`（tag `member`）→ 人 `aos-team spawn approve q-…`：再驗、改名冊（新成員一列＋申請者 mail_to 多一個名字）、`aos-team init`（生家＋更新大家工具的名冊快照）、`aos-agent start`、回覆申請者。一律平的；收掉走既有 `aos-agent stop`＋`aos-team rm` | `lib/aos_team_spawn.py`、`tools/task/spawn_member`、[spawn.md](../../../spec/team/spawn.md) |
| B T-toolsmith | 工人 `tool_draft {"name","description","parameters","code","cases",…}` → 寫 `outbox/tools-staging/<名>/` 給自己看＋寄申請 → 郵差 `on_tool_draft` **用申請內容**生包到 `team/tool-drafts/d-NNNN/`（記 sha256）→ 牢裡 `aos-agent tools test --json`（每次執行 5 秒逾時、整個 90 秒）→ 沒過退 FAILED 附沒過的幾條；過了開一題 `[工具]`（tag `tool`）、同名舊題收掉 → 人 `aos-team tool approve q-…`：只裝最新一版、核 sha256、`tools add` 到寫的人的家、回覆。外殼固定（驗參數、叫 `main(args, root)`、例外一律 `PythonError`） | `lib/aos_team_toolsmith.py`、`tools/task/tool_draft`、[toolsmith.md](../../../spec/team/toolsmith.md) |
| 登記 | `aos_team_requests.KINDS` 加 `spawn`、`tool_draft`；`aos-team` 分派表加 `spawn`、`tool`；**郵差主流程沒改** | |
| 名冊 | 新鍵 `spawn: {"templates": [...]}`，沒寫＝不准生；白名單抄進成員 task 包 `config.json` 的 `spawn_templates`（`spawn_member` 先擋手誤） | `aos_team_format.py`、`aos_team.member_context`、`aos_agent_init.team_config`（各一兩行） |
| 模板 | lead：`may` 加 `spawn`、工具加 `spawn_member`、人格一句；worker：`may` 加 `tool_draft`、工具加 `tool_draft`、人格一句 | `templates/lead`、`templates/worker` |
| 前綴 | 照 main 的 tag 慣例：`TAG_LABEL` 加 `member`→`[成員]`、`tool`→`[工具]`；題目是郵差自己開的（帶 tag），不經 `ask` 申請，`ASK_TAGS` 沒動（模型的 `ask_human` 冒充不了這兩種前綴） | `aos_team_ask.py` |

## 2. 對照：T-spawn（「導入三個子專案」）

情境：`p/` 裡 `a`、`b`、`c` 三個子專案各有 `facts.json`；人丟同一句話給領隊（開三張單、同時派給三個導入工人）。
機械版＝人先在名冊寫死 `importer-1..3`；加模型版＝名冊只有 lead、`spawn.templates=[importer]`，領隊自己申請，腳本當人立刻 `approve`。
LiteLLM `deepseek-chat`，kernel default 4 顆、llm 3 顆；每次全部重建。腳本在 `~/tmp/w3a-try/exp_spawn.py`（沒收進 repo）。

| 次 | 結果 | 子專案 residue＋lint | 模型次數（領隊） | token | 秒 | 人做幾步 |
|---|---|---|---|---|---|---|
| 機械 r1 | done | 3/3 | 33（14） | 169k | 133 | 名冊寫 3 列（開工前一次） |
| 機械 r2 | done | 3/3 | 36（18） | 196k | 167 | 同上 |
| 模型 r1 | done | 3/3 | 49（30） | 341k | 248 | 批 3 次 |
| 模型 r2 | done | 3/3 | 35（17） | 190k | 699 | **答 1 題＋批 3 次**：領隊沒申請，先 `ask_human` 問「IMPORT.md 在哪、名冊有誰」，卡到人回答（等人約 10 分鐘，算進秒數） |
| 機械 r3、模型 r3 | 沒跑 | | | | | 提早收線 |

**六軸對照**（團隊，照 axes.md §4；S 跑不到 10 次不給分）：

| 軸 | 機械版 | 加模型版 | 差在哪 |
|---|---|---|---|
| L | 2（33～36 次） | 2（35～49 次） | 領隊多 3 次申請、多收 3 封批准信；還會迷路（r1 領隊 30 次，翻遍 `/work` 找名冊與 IMPORT.md） |
| S | —（2/2） | —（2/2，但 1 次要人插手） | 領隊不確定「有沒有工人」時會問人而不是申請 |
| R | 2（17～20 萬） | 2（19～34 萬） | 最多多一倍 token；閒著時多生的成員各多一份反覆工作（跟機械版寫死的一樣多） |
| F | 4（2～3 分） | 3～2（4～12 分） | 多一輪「申請→人批→回信」；人不在就停 |
| H | 4 | 4 | 名冊、`spawn ls`、`[成員]` 題都看得懂；但名冊是「跑到一半被改的」，事後要看 `team/spawns/` 才知道誰生的 |
| B | 4 | 4 | 生出來的權限只來自人寫的白名單模板；郵差與 `approve` 各驗一次；逃逸測試全擋（§4） |

**結論（值不值得）**：**不值得當預設**。L 軸的損失換到的只有「人不用事先想好要幾個工人」，但人還是要批每一個（步數沒少，只是從開工前挪到跑到一半、而且要人在場），token 最多多一倍、時間多 1.5～5 倍。**建議：只做機械版**（人寫名冊，教程照舊）；spawn 程式留著、`spawn.templates` 預設空＝關著，真的遇到「工人數要跟工作量變」的情境再開。

## 3. 對照：T-toolsmith（「數 md 檔字數的工具」）——**沒做，留下一輪**

腳本寫好了（`~/tmp/w3a-try/exp_tool.py`：機械版＝人寫 17 行 `.py` → `tools wrap-py` → `tools test` → `tools add`，4 步；加模型版＝工人自己 `tool_draft` 到測過、人批 1 步；兩版都用門房規則開單「用 count_md_words 數字數寫進 words.txt」，驗收查數字 33），**一次都沒跑**。
下一輪從這裡接：`bash ~/tmp/w3a-try/aos/boot.sh` 開機 → `python3 ~/tmp/w3a-try/exp_tool.py mech 1`／`model 1` 各 2～3 次 → 填下表。注意同一個 kernel 上一次只能跑一支團隊（成員同名）。
腳本裡判斷題目還是看 `question.startswith('[工具]')`，rebase 後要改看 `q['tag'] == 'tool'`（`exp_spawn.py` 同樣要改）。

| 軸 | 機械版（wrap-py） | 加模型版（tool_draft） |
|---|---|---|
| 全部 | 沒量 | 沒量；要量「幾版才過測」「token」「人幾步」 |

設計上已知的：工具描述 `tool_draft` 863 字元（約 216 token），每個工人每次呼叫都送；`spawn_member` 574 字元只送給領隊。

## 4. 逃逸測試（每條一個測試，全擋）

| # | 試什麼 | 結果 | 測試 |
|---|---|---|---|
| S1 | spawn 的 `mail_to` 比自己大 | `MailToExceeds`，沒開題 | `test_escape_mail_to_bigger_than_requester` |
| S2 | `mail_to` 寫自己寄不到的現有成員 | `MailToExceeds` | `test_escape_mail_to_someone_requester_cannot_reach` |
| S3 | 權限比自己大（小模板申請生 lead） | `MayExceeds` | `test_escape_template_with_more_may` |
| S4 | 模板名亂寫（`../../etc`、絕對路徑、不存在、空） | `BadTemplate` | `test_escape_template_garbage_names`、`…_not_allowed`、`…_missing_on_disk` |
| S5 | 超過 `max_members`（等人批的也算） | `TooMany` | `test_escape_over_max_members_counts_pending` |
| S6 | 申請夾帶 `mounts`／`tools`／`model` | `BadArguments` | `test_escape_extra_fields_rejected` |
| S7 | 名字撞人、保留名、`../lead` | `NameTaken`／`FormatInvalid` | `test_escape_name_taken_reserved_or_bad` |
| S8 | 工人自己在 outbox 寫 spawn 申請 | 郵差照 `may` 退件 | `test_forged_request_from_worker_rejected_by_post` |
| T1 | 草稿讀別人的家（絕對路徑、`../../team/members/…`、`/work/../`） | 牢裡讀不到、例子沒過、退信不帶內容 | `test_escape_read_other_home` |
| T2 | 草稿寫 `access.json`（主機路徑、`/work/../`） | 檔一個位元組沒變 | `test_escape_write_access_json` |
| T3 | 無窮迴圈 | 逾時被砍，< 30 秒回，退信寫「逾時」 | `test_escape_infinite_loop_times_out` |
| T4 | 測過之後改 staging 想換程式 | 裝的是郵差的快照 | `test_escape_staging_swap_after_test` |
| T5 | 改郵差快照 | `Tampered`，不裝 | `test_escape_snapshot_tampered` |
| T6 | 工具名撞 `read`、包名撞 `task` | `tools add` 拒絕，原檔不動 | `test_escape_name_clashes_with_existing_tool`、`…_package_name_of_builtin_pack` |
| T7 | 裝好的工具在成員牢裡讀領隊的家 | `blocked` | `test_installed_tool_still_jailed` |
| T8 | 沒有 bwrap | `NoJail`，不在主機上跑 | `test_no_jail_no_run` |

## 5. 代裁（附預設，翻案回這條）

1. **批准走人的指令 `spawn approve`／`tool approve`，不是 `answer 批准` 自動生效**：生家、改名冊、裝工具都是人的指令做，郵差不做有權限的事；人先 `answer 批准` 也行，再跑 `approve` 會補做。
2. **「權限」比 `may` 與 `mail_to`，不比專案讀寫**：內建領隊專案唯讀，照字面連工人都生不出；能不能寫專案由人寫的白名單決定。`ask`、`compact`、`lock`、`review_result`、`tool_draft` 算安全，新成員可以有。
3. **白名單只收內建模板名**；沒寫＝不准生（預設關）。
4. **草稿一定要附至少一條 `expect: "ok"` 的例子**：`tools test` 自動的正例把「每次都丟例外」也算過。
5. **郵差同步測**（最久約 90 秒，那段時間別的信晚一輪），不另開 kernel 工作——不改郵差主流程。
6. **過了不寫信給工人**（省一輪模型），批准時才回信；沒過才退信。
7. **只裝給寫的人自己**；同名重裝只限上次也是 `tool_draft` 裝的。
8. **申請者的 `mail_to` 自動多新成員的名字**（不然它派不了工）。

## 6. 要使用者拍的（一題）

| # | 題目 | 預設 |
|---|---|---|
| 1 | T-spawn 要不要留？對照（2＋2 次）：加模型版 token 最多多一倍、時間 1.5～5 倍、人還是要批每一個、有一次領隊改去問人 | **只用機械版**：程式留著，`spawn.templates` 預設空＝關；教程只寫怎麼開、不當預設流程 |

## 7. 數字與收尾狀態

- 測試：`test_team_*.py` 相關檔 461 條全綠（rebase 到 `162cc59` 後）；新增 `test_team_spawn.py` 24 條、`test_team_toolsmith.py` 26 條，改 `test_team_format.py`、`test_team_init.py`、`test_team_notes_compact.py`（新工具、新 may）。**全套沒跑**（收線）。
- 工具描述：`spawn_member` 574 字元、`tool_draft` 863 字元；task 包 11 支合計約 6500 字元（測試上限從 5500 放到 7000）。
- **沒做、留下一輪**：T-toolsmith 真跑與對照（§3）；T-spawn 各第 3 次；astra 唯讀審查（**沒審**）；教程 08 的一小節（沒加）；README 指令表、tools/task README、code-map 的列（下面列給收尾隊）；新手試玩。
- 給收尾隊要加的列：proto5 README 指令表 `aos-team spawn`、`aos-team tool`；tools/task/README 兩支工具；lib README 兩個模組、兩個測試檔；code-map `aos_team_spawn`、`aos_team_toolsmith`。
- 真跑場地 `~/tmp/w3a-try/`（daemon 已 `aos down`）。
