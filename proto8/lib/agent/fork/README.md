# fork — 把當下的自己複製一份，給它一個 goal，只收回短結論（11-11）

← [lib](../../README.md)｜記錄：[thinking 11-11 fork-and-do-task/01-fork](../../../thinking/2026-11/11/fork-and-do-task/01-fork.md)

使用者 11-11：「一種是fork，也就是自身的各種東西複製一份，然後等他跑好後留下結論，這其實有點像subagent的變體。」裁「一律連對話複製」。開分身、等結論、抄帳、收掉這套照搬 do_task（原 thought）11-11 那版；「用別的定義」那條路（`from`、`AOS_DO_TASK_FROM`）拿掉。

- **抄什麼**（[`lib/agent/fork_copy.py`](../fork_copy.py)）：叫我的那隻（`aos-agent ctl who --json`）的定義照用；它 stack 裡定義 `interfaces.json` 的 `aos-agent` 宣告過的檔——`history`（必要，沒宣告＝`HistoryMissing`）、`tools`、`llm`、`hooks`、`system`（有那份才抄）——抄進 `<daemon>/procs/<分身名>/`，再 `ctl add --stack` 那份。登記檔裡相對路徑換算到新位置。history 尾巴那則 assistant 還沒回的工具呼叫補 tool 訊息：第一個（＝這次 fork）`[aos] fork: you are the copy made by this call; …`，其餘 `[aos] fork: not run in the copy …`。
- **不抄**：`goal.json`、工具小格（`tools/*`：todo、subagent 的帳、do_task／fork 的紀錄、claude／codex 工具的對話）、hook 狀態（`hooks/*`、`hook_tools_seen.json`）、queue、信箱、`think/`、`stage.txt`、observed、冷卻、`history_removed.jsonl`。
- **開場**：`say` 一則 `[aos] fork: you are a fork: …`（任務＝goal、只回結論、至多 max_chars 字、不能再 fork），`listen` 拿第一則回答。不寫分身的 `goal.json`。
- **只給 agent-fsm**（使用者「eca不給fork。」）：history 裡找不到叫到一半的 tool call（eca 的工具來回在 CLI 裡）＝`BodyUnsupported`，錯誤行叫它改用 `subagent`；判法同 do_task，什麼都不生。
- **深度**：`AOS_FORK_DEPTH`（`ctl add --envs` 帶），最多 1 層：分身再叫＝`DepthExceeded`。
- **收尾**：預設 `ctl rm --purge`；`keep: true`＝`ctl stop` 留著、結論後多一行 `details: <stack>/`。答不出＝停下、stack 一律留、錯誤行尾 `(details: …)`。不論哪種，先把分身公開宣告的帳抄到工具小格的 `observed/<分身名>/`（同 do_task）。
