# tools/task：派工、看任務表、審查、問人、縮記憶、申請類

← [tools README](../README.md)｜格式：[spec/team/](../../spec/team/README.md)

給團隊成員（領隊、工人、審查）用的九支工具，**不叫模型、不直接改任務表／人格／access.json／routines.json**：寫的只有自己的 outbox（牢裡 `/work/outbox`），郵差再驗一次、開單、改狀態、或（申請類）包成一題問人。
`aos-team init` 照模板裝（`--only` 挑幾支）並寫好 `config.json`；不在團隊裡的 agent 用不了（`ConfigInvalid`）。

| 工具 | 誰有 | 做什麼 | 參數（* 必填） |
|---|---|---|---|
| `handoff` | 領隊 | 寫一份 `kind: handoff` 申請；郵差開 `t-NNNN` 並派給負責人。**改寫 workflows 文件類的單**（goal 提到 `.md` 又有「改寫／白話」等字眼）會機械補一條 `wf_lint_strict`（沒放才補），見下面〈G〉 | `assignee`*、`workflow`*（入口檔，沒有寫「無」）、`goal`*、`done_when`*、`facts`、`max_attempts`（1～10）、`deadline_minutes` |
| `board` | 全部 | 唯讀看 `/work/board`（＝`team/tasks/`）：`op: ls`（`all: true` 含結束的）、`op: show`。審查子單的條目編號跟父單一致（不是從 0 重編，見〈F〉） | `op`、`task`、`all` |
| `review_result` | 審查 | 逐條回一張審查子單（`t-0001.r1`），每條 `{i, pass, why}` 都要有；`i` 是**父單的原編號**，不是子單裡 0 起算的位置 | `task`*、`items`* |
| `ask_human` | 領隊、工人 | 寫一份 `kind: ask` 申請；答案之後是一封新信 | `question`*、`options`、`default`（要在 options 裡）、`reply_to` |
| `compact_me` | 領隊、工人 | 寫一份 `kind: compact` 申請縮**自己**的記憶（不收 `member`）；郵差投進自己家的 `compact-req/`，下一次閒著時縮（[compact-more.md §5](../../spec/agent/compact-more.md)） | `reason`（≤ 500 字）、`keep_rounds`（0～1000）、`max_tokens`（≥ 100） |
| `lock` | 工人 | 短期獨佔一個檔或資料夾的名字（[lock.md](../../spec/team/lock.md)）：`acquire` 拿不到會收到退信說誰拿著、`release` 放掉、`ls` 列全部；都是非同步，結果是下一輪的新信 | `op`*（`acquire`／`release`／`ls`）、`name`（acquire／release 要）、`why`、`ttl_seconds`（60～86400，預設 1800） |
| `access_request` | 工人 | 申請多掛一個資料夾／開網路；包成一題問人（[ask.md〈借用〉](../../spec/team/ask.md)），**自己改不到 `access.json`**，人同意後要自己跑 `aos-agent access set` | `name`*、`path_hint`*、`mode`*（`ro`／`rw`）、`why`* |
| `persona_propose` | 工人 | 提議改自己的人格；包成一題問人（同上），**自己改不到人格**，人同意後要自己跑 `aos-agent persona append`（[persona.md](../../spec/agent/persona.md)） | `text`*（≤ 2000 字）、`why` |
| `routine_propose` | 領隊 | 提議加（或拿掉）一條心跳例行；寄 `kind: routine` 申請，**開一題問人**，人 `answer` 批准心跳才會排進去（[beat.md](../../spec/team/beat.md)） | `name`*、`every`／`daily`／`once`（add 要恰好一個）、`to`、`goal`、`done_when`、`workflow`、`tz`、`timeout_minutes`、`retries`、`op`（`add`／`rm`，預設 `add`） |

- 寫完就回一句「queued … end this turn」：沒有「等回信」的工具，回信到了是新的一輪。`lock` 也一樣——catalog 草案設想的「acquire 立即回」在這套模型端沒有同步等待機制，所以照這裡的規矩走非同步。
- 擋手誤（名冊外的負責人、派給自己、`done_when` 種類不對、審查漏條）回 `BadArguments`；名冊的快照在 `config.json`，真正的把關在郵差。
- 錯誤格式跟 base 一樣：退 1、stdout 最後一行 `{"ok": false, "error": …, "message": …}`；另有 `ConfigInvalid`（沒團隊設定）、`NoOutbox`／`NoBoard`（沒掛進牢）、`WriteFailed`。
- 給模型看的描述（`function` 整段 JSON）九支合計約 5000 字元（約 1250 token）；每個成員只裝模板 `only` 列的幾支（lead：handoff／board／ask_human／compact_me／routine_propose；worker：board／ask_human／compact_me／lock／access_request／persona_propose）。
- 測試：[`lib/test/test_team_init.py`](../../lib/test/test_team_init.py)（`ToolUnitTests` 不關牢直接跑；`TeamIntegrationTests` 真 kernel＋bwrap）；`compact_me` 在 [`test_team_notes_compact.py`](../../lib/test/test_team_notes_compact.py)；`lock` 的郵差端在 [`test_team_lock.py`](../../lib/test/test_team_lock.py)；`persona` 人用那半在 [`test_agent_persona.py`](../../lib/test/test_agent_persona.py)。
- **G（自動補 `wf_lint_strict`）代裁**：選在 `handoff` 這一層機械補，不改門房規則——門房、`routes.json` 是 A 隊地盤（T-route），這裡改動範圍最小。**只涵蓋模型叫 `handoff` 這支工具開的單**（領隊自己開單會補到）；心跳照例行派工是 `aos_team_beat.py` 自己組 `handoff` 申請直接送出，不經過這支工具，不會補到（09-24 astra 審查 M6：原本註解宣稱「心跳照例行開單一樣有效」是錯的，已改成上面這句）。判法是 `goal`（只看這一欄，見 astra 審查 S1）的文字裡同時有 `.md` 與一個改寫用詞（白話、改寫、更好懂、更易讀、講白話），沒有否定詞（不要／別／不用／不准），且 `done_when` 還沒放就補一條。使用者要翻案（改成門房規則，或把邏輯也接進心跳）再議。
