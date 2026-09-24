← [工具大開發時代](README.md)

# 審查任務書：第一波第 4 隊「記憶與紀錄」（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要連 localhost 任何埠。** 可以讀檔、可以跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_agent_memory.py'`、`test_agent_notes.py`）。用繁體中文、白話回答。

## 要審的（這一隊做的）

程式：
- `proto5/lib/aos_agent_compact.py`（機械壓縮：`plan` 純函式、`apply` 寫 archive→記事件→換記憶、人用的 `compact`、tick 的 `auto`、申請 `on_request`、`history --archive`、`prune`）
- `proto5/lib/aos_agent_events.py`（`log/events.jsonl`、`usage.jsonl`、去重、`aos-agent events`）
- `proto5/lib/aos_agent_context.py`（`aos-agent context` 與 talk `/context` 同一個函式、token 粗估、輪的切法）
- `proto5/lib/aos_agent_notes.py`＋`proto5/tools/notes/`（`note` 工具與人看的 `notes ls/show`）
- 改動：`proto5/lib/aos_agent.py`（tick 的 idle 一步叫 `aos_agent_compact.auto`）、`aos_agent_batch.py`（`send`／`collect`／`settle` 記事件、think inst 多 `AOS_LLM_BATCH`、`calls[].ms/ok`）、`aos_agent_inputs.py`（intake 記事件）、`aos_llm_call.py`（寫 usage）、`aos_agent_talk.py`（`/context` 改叫共用函式）、`aos_agent_cli.py`（五個子命令＋`init --template`）、`aos_team_requests.py`（登記 `compact`）
- 測試：`proto5/lib/test/test_agent_memory.py`、`test_agent_notes.py`

規範（新檔）：`proto5/spec/agent/events.md`、`proto5/spec/agent/compact.md`、`proto5/spec/aos-agent/cli-memory.md`；既有檔只加了標「（09-24 第 4 隊補）」的句子。

## 對照來源

- 任務規格：`proto5/notes/2026-09-24-tool-era/catalog.md` 的 T-events、T-context、T-compact、T-notes 四段；`plan.md`〈各隊驗收〉隊 4 那 8 條、〈誰改共用的檔〉。
- 既有規則：`proto5/spec/agent/`（info.md §3.2 記憶驗證、state.md、layout.md）、`proto5/spec/aos-agent/`（tick.md §2／§2.1 tick 鎖、idle.md、send.md、collect.md、settle.md、cli-talk-repl.md 的 `/context`）、`proto5/spec/aos-llm/request.md`、`proto5/spec/team/`（mail.md〈申請〉、layout.md）。

## 請特別看

1. **鎖與恢復**：`compact` 只在持 `.tick.lock`、idle、`batch`／`intake` 為 null 時寫；tick 內的自動壓縮不重拿鎖（同行程再 flock 會被自己擋）——有沒有哪條路徑沒持鎖就寫記憶、或會死鎖。`apply` 的「archive → 事件 → rename 換記憶」在任何一步崩潰，重跑是否一定得到同一份結果、記憶檔是否永遠完整。`plan` 是不是真的決定性、是不是不動點（縮過再縮是空轉），特別是封存（seal）與「換掉的比說明行短就不換」這兩條。
2. **記憶正確性**：新記憶照 agent §3.2 驗得過嗎；`tool_calls` 與 `tool` 結果會不會被拆開（`check_pairs` 夠不夠）；輪的切法（連續的 user 開一輪）有沒有會切錯的情況（例如 user 夾在 tool 結果中間、記憶開頭是 tool）；說明行用 `user` 角色合不合理。
3. **沒做完的任務不縮**：`task_status` 找團隊資料夾與單號的方式、`TASK_RE`、「讀不到也算沒做完」會不會讓記憶永遠縮不下去。
4. **事件的「至少一次」**：`batch_start`／`batch_end`／`intake`／`compact` 的位置是否都在提交之前；有沒有會「做了沒記」的窗口；`batch_id` 對全部在本地結束的 act 批回 `None` 會不會出問題；寫事件失敗會不會讓 tick 失敗。
5. **usage**：`aos_llm_call.call` 的 `finally` 寫 usage 會不會在例外時漏記或誤記；`AOS_LLM_BATCH` 放進 think inst 的 `envs`（疊加、不 clear）會不會影響 llm cpu 原本的環境。
6. **自動壓縮的行為**：有輸入等著就不縮、`log/compact-skip` 的鍵（sha＋選項）、設定壞掉時的處理、申請檔先縮再搬——有沒有會每格空轉、或申請永遠搬不走的情況。
7. **`on_request`**：權限（只有 human 能替別人申請）、冪等（同 id 不重投、已處理過不重投）、欄位驗證，跟 spec/team/mail.md〈申請〉的約定合不合。
8. **`note` 工具**：flock 讀改寫、`wf-table/1` 格式、關牢時預設 `/work/notes/notes.json` 與人看的 `aos-agent notes` 找檔規則是否一致、描述字數。
9. **驗收 8 條**（plan.md 隊 4）逐條看測試是否真的證明了它（特別是 ⑥ KILL 窗口的測試是不是真的用 SIGKILL、在「寫 archive 後、換 history 前」）。

## 格式

分三段：**必修**（不改會做錯的：哪個檔哪一行附近、問題、建議改法）、**建議**、**確認沒問題的**（簡短）。必修按嚴重程度排，編號 M1、M2…；建議 S1、S2…。
