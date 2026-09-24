← [第二波 B 隊報告](README.md)｜[回報](review-astra.md)

# 審查任務書：第二波 B 隊（牆接線）（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／`lms`／localhost:1234／ollama。** 可以讀檔、跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_team_wall.py'`，另外 `test_team_escape.py`、`test_notes_recall_context.py`、`test_team_route.py`、`test_team_verify.py`；這台有 bwrap）。繁體中文、白話。

**只審這次的改動**：`git diff eacfcc2 HEAD -- proto5 wf/workflows/common/code-map.md`。第一波與 access-impl 的審查已修，不用重提。

## 背景

- 權限牆契約：`proto5/notes/2026-09-24-agent-access/contract.md`（有表就全關、可寫映射不能蓋到信任資料、唯讀可以重疊）；實作 `lib/aos_jail.py`、`lib/aos_agent_access.py`、`lib/aos_agent_batch.py`（`jail_argv`、`tool_inst`）。
- 團隊規範：`proto5/spec/team/`；這次新增 `spec/team/wall.md`（請以它為準對程式）。

## 這次做了什麼

1. **門房 `tool` 規則關牢**（`lib/aos_team_route.py` 的 `run_pack_tool`、`jail_argv`）：專案唯讀掛 `/work/ws`（規則寫 `"project": "rw"` 才可寫，`aos_team_format.validate_routes`）、`--net off`、清環境；沒 bwrap＝`NoBwrap`，不退回不關牢。
2. **驗收員**（`lib/aos_team_verify.py`）：`wf_lint_strict` 改成經 `aos-jail` 跑 `tools/wf/_jail_lint`（專案唯讀）；新條目 `cmd_ok`：`{"kind": "cmd_ok", "run": [...], "timeout_s"?}`，白名單在 `team.json` 頂層 `cmd_ok`（`aos_team_format._cmd_whitelist`、`cmd_allowed`、`validate_cmd`），牢裡跑、專案唯讀，退 0＝過、逾時＝不過、不在白名單／跑不起來／沒 bwrap＝檢查器壞。`file_exists`、`table_filled`、`contains`、`wf_residue` 仍在牢外（純讀）。
3. **郵差再驗**（`lib/aos_team_post.py` 的 `recheck`，在 `take()` 裡 `read_outbox_file` 之後）：`handoff` 的 `done_when` 路徑（相對專案、不含 `..`、不以 `/`／`~` 開頭）、`workflow`（不准 `..`、絕對只准 `/work/…`）、`cmd_ok` 對白名單、成員寫的信文與 handoff 的 goal／facts／workflow 不准有像信頭的行（`【來信`、`【人 →`）。
4. **記憶映射與兩支新工具**（`lib/aos_agent_init.py` 的 `_access`／補掛、`tools/notes/recall`、`tools/notes/context`、`tools/notes/_common.py` 的 `mem_dir`）：模板 `notes: true` 的成員多掛 `mem` → 自己家 `prompts/`（唯讀）；`mem` 加進保留名。
5. `tools/task/handoff`、`task.json` 收 `cmd_ok`；`aos_team_task.describe_item` 認 `cmd_ok`。
6. 逃逸測試 `lib/test/test_team_escape.py`：用 `aos-team init` 生真團隊，走 `tool_inst` 的真送件路徑進 bwrap。

## 請回答

1. **牢有沒有漏**：`aos-jail` 的呼叫（route、verify）參數有沒有能被注入的地方（`project` 路徑含 `=`、`,`、換行？`run` 的元素以 `-` 開頭會不會被 aos-jail／bwrap 吃成選項？`run[0]` 不含 `/` 的限制夠不夠）；`_jail_lint` 在牢裡從 `/opt/tool` 載 `_wf.py` 有沒有被專案影響的路徑（`sys.path`、cwd、環境變數）；wf-lint 跑 git 在唯讀專案裡會不會讀到專案的 `.git/config` 而執行東西（fsmonitor、hooks 之類；牢裡就算執行了，能碰到什麼？）。
2. **cmd_ok**：白名單比對（整串相等、timeout 不超過）有沒有繞法；開單時驗與驗收時再驗的兩處一致嗎；輸出截斷、編碼錯誤、`subprocess.TimeoutExpired` 後 bwrap 與孫行程會不會留下來（`--die-with-parent`）；「跑不起來」的判定（stderr 以 `bwrap: ` 開頭）會不會把專案指令自己的輸出誤判成檢查器壞。
3. **郵差 recheck**：擋得太多（正常的單子被退）或太少（例：`workflow` 用 `/work/../` 繞、Windows 分隔、Unicode 同形字、`done_when` 的 `check` 其他 args 裡的路徑）；假信頭的正規式；人（`human`）寄的為什麼不擋是否合理；recheck 丟的 `TeamError` 在 `take()` 裡會不會跟既有退件流程衝突（冪等、紀錄 id）。
4. **mem 掛點**：唯讀掛自己家的 `prompts/` 有沒有讓成員看到不該看的（別人的資料、access 設定）；`recall`／`context` 在記憶很大、archive 很多、壞檔、符號連結時的行為；補掛舊家會不會蓋掉人手改的掛載。
5. **逃逸測試**是否真的測到它宣稱的（例如 `test_03` 裡的 `rm` 在牢裡本來就找不到檔，算不算測到「寫不到 access.json」；`test_13` 絕對路徑的連結被 `json_files` 忽略、沒有退件，這樣夠不夠）；還缺哪一條 experiment.md 列的逃逸方式。
6. `spec/team/wall.md`〈保證外〉列得完整嗎；規範（wall、verify、route、roster、mail、post、layout、templates）與程式、教程 08 第 9 節對不對得上。

## 格式

**必修**（不改會做錯、可被濫用、或規範與程式不符的；每條：檔、函式、怎麼觸發、建議改法；M1、M2…）、**建議**（S1…）、**確認沒問題的**（簡短）。
