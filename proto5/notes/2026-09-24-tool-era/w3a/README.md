← [工具大開發時代](../README.md)｜[notes 索引](../../README.md)｜計畫 [plan.md](../plan.md)｜目錄 [catalog.md](../catalog.md)｜評分 [axes.md](../axes.md)｜規範 [spawn.md](../../../spec/team/spawn.md)、[toolsmith.md](../../../spec/team/toolsmith.md)

# 第三波 W3-1 隊（模型生成員、模型造工具）報告（2026-09-25，提早收線版；**09-25 收尾＋39 翻案見 [§8](#8-09-25-追加收尾39-翻案)**）

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

## 8. 09-25 追加：收尾＋39 翻案

**一句話**：使用者翻案 WAIT_USER 39 做完了。生新成員現在**預設開、預設不用人批**，每個成員都能在名冊上各自設；牆照舊關牢。astra 審了，必修 6 條全修；T-toolsmith 真跑 2＋2 次補齊；教程 08 加了一節，索引也補了列。新手試玩沒做，留下一輪。
基底：main `0cfb325`（開工 `60e4b81`，中途 rebase 兩次，都沒有衝突）。全套 **96 檔 2665 條全綠**（約 4 分鐘）。

### 8.1 做了什麼

| 項 | 做了什麼 | 在哪 |
|---|---|---|
| 39 翻案 | 名冊 `spawn.templates` 沒寫＝內建模板都能生，要關就寫 `[]`；新鍵 `spawn.approve`（預設 `false`）；成員層 `members.<名>.spawn` 可寫 `true`／`false` 或 `{"allow","templates","approve"}`，會蓋過團隊層；模板 `may` 有沒有 `spawn` 只是出廠值。不用人批的申請，郵差檢查過就當場改名冊、`init`、`start`，回 DONE 給申請者，另寄一封給人知會；要人批的照舊開「[成員]」題 | [spawn.md](../../../spec/team/spawn.md)、[roster.md](../../../spec/team/roster.md)、`lib/aos_team_spawn.py`、`aos_team_format.py`（`spawn_policy`、`member_may`） |
| 牆 | 模板只收內建名、人數上限、`mail_to` 與 `may` 不超過申請者，這些都照舊。新增一條：**新成員生人的設定不比申請者寬**。申請者被設成要人批，或只能生某幾種，它生出來的成員會照抄這份設定 | `inherit_spawn` |
| 工具 | `init` 依成員開關決定裝不裝 `spawn_member`；工具回話會分「郵差會生」和「人決定」 | `aos_agent_init._spawn_tool`、`tools/task/spawn_member` |
| astra | 必修 6 條全修，見 §8.3 | [review-task.md](review-task.md)、[review-astra.md](review-astra.md) |
| 教程／索引 | 教程 08 加〈10. 讓領隊自己生工人、讓工人自己造工具〉；proto5 README 指令表、tools/task README、lib README 補列（code-map 早就有了） | [08-team.md](../../../tutorials/08-team.md) |
| 順手 | W3-2 留下的一行：`validate_routes` 把 OverflowError／RecursionError 轉成白話的 FormatInvalid，加 1 條測試 | `aos_team_format.py` |
| 測試 | `test_team_spawn` 24→43 條，涵蓋預設開、成員關、成員要批、團隊要批但成員不用、工人被開、不用批以後的 4 道牆、2 條繼承、郵差端到端、真崩、補做、rm 後讓出名額、同一輪看到新成員；`test_team_toolsmith` 26→27 條；`test_team_route` +1 條 | |

### 8.2 真跑（模型：DeepSeek 雲端 `deepseek-chat`）

**spawn 第 3 次（新流程：名冊不寫 `spawn`＝預設開、不用批）**，1 次，劇本同 §2：

| 次 | 結果 | 子專案 | 模型次數（領隊） | token | 秒 | 人做幾步 |
|---|---|---|---|---|---|---|
| auto r1 | done | 3/3 | 59（23） | 535k（領隊 169k，3 個工人各 113～137k） | **77** | **0** |

對照 §2：機械版 133～167 秒、17～20 萬 token、人寫名冊 1 次；舊的要批版 248～699 秒、人批 3 次。
- **時間與人手**：這次最快，人一步都不用做。
- **token**：這次最貴。領隊 23 次、每個工人 11～14 次，比昨天每個工人都多。只跑 1 次、又換了端點（見代裁 1），貴在哪還說不準，**留下一輪**再多跑幾次。
- **要注意**：領隊把三個成員取名 `importer-a／b／c`，**用的模板卻是 `worker`**。因為預設是「內建模板都能生」，它就挑了通用工人。這次照樣做完（工人也有 wf 工具），但名字和實際模板對不上。看 `aos-team spawn ls` 就知道實際用了哪個模板。

**T-toolsmith（§3 補齊）**，各 2 次：

| 次 | 結果 | words.txt | 模型次數 | token | 秒 | 人做幾步 | 草稿 |
|---|---|---|---|---|---|---|---|
| 機械 r1 | done | 33 ✓ | 4 | 21.6k | 17 | 4（寫 16 行 .py、wrap-py、test、add） | — |
| 機械 r2 | done | 33 ✓ | 5 | 27.2k | 23 | 4 | — |
| 模型 r1 | done | 33 ✓ | 8 | 49.2k | 34 | 1（approve） | 1 版就過（5/5） |
| 模型 r2 | done | 33 ✓ | 9 | 56.6k | 40 | 1 | 1 版就過（6/6） |

**結論**：模型造工具能用（兩次都一版就過），但如果人本來就知道要什麼工具，**機械版比較划算**：token 大約一半、時間大約快一倍。模型版省下人「寫 16 行」，可是人批之前還是得看草稿。r2 的草稿自己多加了一個 `write_to` 參數，可以把數字寫到任意路徑。牢擋得住，但這正是人審的時候要抓的東西，所以省下的工夫大半變成「審 20 幾行」。**建議照舊要人批**，只在「人不想寫」或「同一種事一直重複」時才用。
原始紀錄：`~/tmp/w3a-try/tool-{mech,model}-r{1,2}/`、`spawn-auto-r1/`（沒收進 repo）。

### 8.3 astra 必修（6 條全修）

| # | 問題 | 修法 |
|---|---|---|
| 1 | toolsmith 在郵差那邊探測過牢，`tools test` 裡第二次探測如果失敗，會退回在主機上直接跑 | 新環境變數 `AOS_TOOLS_REQUIRE_JAIL=1`：關不了牢就一支都不跑；toolsmith 一律帶上它 |
| 2 | 不用批的申請崩在一半，人剛好把申請者改成要批，重來時會直接生 | 補辦之前重看一次要不要人批；要批就改成開題 |
| 3 | 郵差自動生、人 `spawn approve`、`aos-team rm` 同時改 `team.json`，會互相蓋掉 | 三條路共用一把鎖 `team/.roster.lock`（讀、檢查、改、寫一口氣做完） |
| 4 | 郵差生失敗寄了 FAILED，人補做成功後沒人通知申請者 | `approve s-NNNN` 補做成功時，從 `team/post/outbox/` 補寄一封 DONE，只寄一次 |
| 5 | 用「名冊有沒有這個名字」推狀態：rm 掉的成員會再佔名額，init 失敗的會被當成已生 | 紀錄加 `status`（done／failed），已生看這格 |
| 6 | 郵差生完新成員，同一輪後面寄給它的信會被舊名冊退件 | 處理完 spawn 馬上重讀名冊（測試確認拿掉這個修正就會失敗） |

建議類採了一條：`templates: []` 的說法改成「沒在成員層另寫 `templates` 的都不准生」。另外兩條（崩潰測試再細、總逾時的子程序）列在下一輪。

### 8.4 代裁（附預設，翻案回這條）

1. **模型走 DeepSeek 雲端直連**：LiteLLM `localhost:4000` 今天沒開，照調度者指示改成 `https://api.deepseek.com/v1`。金鑰寫成 `"api_key": {"$env": "DEEPSEEK_API_KEY"}`，金鑰本身沒寫進任何檔。沒碰 LM Studio／ollama。昨天 §2 走 LiteLLM，數字不能完全直接比。
2. **「預設開」＝內建模板全部都能生**（`templates` 沒寫就是全部），不是只開 `importer`／`worker`。後果見 §8.2：領隊可能挑到不是你心裡想的模板。要窄就在名冊寫 `templates`。
3. **不用人批也寄一封知會給人**，說明誰生了誰、理由、怎麼收掉。人不用做任何事，但知道名冊變了。
4. **改名冊這件事，不用人批時由郵差做**：這推翻了昨天 §5 第 1 條「郵差不做有權限的事」。人批的那條路照舊走人的指令。
5. **開關分兩種生效方式**：「關掉」和「改成要批」存檔就生效，因為郵差每份申請都重驗。「打開」一個原本不能生的成員，要 `aos-team rm` 再 `init` 重生它的家，才會拿到 `spawn_member` 工具。
6. **造工具（`tool_draft`）這次沒做成「團隊層預設＋成員層覆蓋」的開關**，照舊一律要人批。使用者只講了生工人，而真跑也顯示人批時確實要看草稿。
7. **新成員照抄申請者的生人設定**，只在申請者的設定跟團隊層不一樣時才寫進名冊；一樣就不寫，跟著團隊層走。

### 8.5 留下一輪

- 新手試玩（Sonnet 只看教程 08，從開隊玩到生一個工人）：沒做，時間不夠。
- spawn 新流程再跑 1～2 次，確認 token 偏高是這次的偶然，還是「不用批」讓領隊生得太快、分工變碎。
- `tool_draft` 要不要也做成團隊層＋成員層的開關（見代裁 6）。
- astra 建議兩條：崩潰點再細（寫名冊後崩、init 失敗後崩），以及 toolsmith 總逾時時工具子程序有沒有收乾淨。
- `aos-team tool approve` 之後約 2 秒內，`tool ls` 還會顯示「等你批」（答案要等郵差下一輪才寫進去），人可能會再按一次。重按不會出事。

### 8.6 要使用者拍的（一題，可以不拍）

| # | 題目 | 預設 |
|---|---|---|
| 1 | 名冊沒寫 `spawn.templates` 時，「預設開」要開到多大？(a) 內建模板全部；(b) 只開 `worker`＋`importer` 這種做事的；(c) 維持 (a)，但在教程和範例名冊寫上 `templates` | **(a)**：照「預設開」字面做。真跑時領隊挑了 `worker` 當導入工人，事也做完了 |
