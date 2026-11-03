← [2. repo 裡已經有答案的](../18-2-repo-裡已經有答案的.md)（分檔 1/3）｜[下一份](02-批次不短路-needs.md)

**孤兒 ＋ `.runi`**

- 矛盾的兩句：`docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉的不變式與「行程死掉 `.runi` 就會留著」；同檔〈十二、留給實作決定的〉〈已經被實作決定的〉的 `setpgid`。同節：`--loop` 用 `SA_RESETHAND`，第二次信號直接殺掉行程，`.runi` 會留著。
- `aggregate` 在 `claim` 之前：`wf/workflows/common/code-map.md` 的 `run_exec.cpp` 列；`core/inst/docs/handoff.md`〈取件與釋放〉（`claim_instruction()` 先拒絕既有 `.runi`；`release_instruction()` 在所有子行程含 parallel thread 結束後才呼叫）。
- 上一次的孤兒現場：`wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉，同節記了背景 job 忽略 SIGINT 的無效 harness。
- `.runi` 升級成租約的形狀限制：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 2 條（`.runi` 內容就是那批 JSON，不包 header；receipt 放旁邊 `inst.json.runi.receipt`，先寫 receipt 後 rename `.runi`）；第 5 條問 `.runi` 鎖的是那一批還是那個世界。
- 租約要原子建立：`docs/aos-folder.md`〈十二〉〈仍然開著的〉——`renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink`。
- `timeout_ms` 已有殺整個行程群組的機制：`core/inst/docs/exec.md`〈逾時與行程群組〉（SIGTERM 群組、2000 ms 後 SIGKILL）；缺的只是 parent 被外部信號砍掉那條路徑。
- 硬邊界：`wf/workflows/workshop/records/agent-loop-architecture.md`〈斷點續跑的硬邊界：本機可以原子，遠端付費不能假裝 exactly-once〉（可安全自動恢復的只有 provider 接受 idempotency key、或能按 request ID 查回）；同檔〈明顯的坑〉。

**不重複付錢的復原與 recover 的形狀**

- policy A／B／C 對照：`wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉（停／按 provider key 查回／盲目 retry，B 不重複）。`codex exec resume <thread_id>` 是 B 的真模型版。
- `aos recover [WORLD]` 介面：同檔〈痛在哪：可直接寫成子命令的需求〉——唯讀列出 `.runi`、每筆證據與可能仍活著的子行程；`--replay`／`--abandon`／`--adopt RECEIPT`；證據不足預設停住。同節還有 `aos deliver`／`aos status --json`／`aos agent step`（phase：`request-published → effect-started → result-temp → result-published → next-delivered`）／`aos agent emit-context`。
- `docs/roadmap.md`〈T5 — agent loop：不需要 `core/llms`〉的 ⚠ 區塊：驗收「Ctrl-C 後能從斷點繼續」與 D6 矛盾，拍板前不照這條驗收實作。

**停止條件與退出碼**

- `docs/aos-folder.md`〈十二〉〈已經被實作決定的〉：回合失敗時 `--loop` 不停，只有退出碼 3 會讓迴圈退出；`docs/roadmap.md`〈T4〉〈注意〉。
- 退出碼契約：`docs/aos-folder.md`〈八、退出碼〉、`docs/roadmap.md`〈D10〉、`wf/workflows/common/gotchas.md`〈使用 aos〉。
- 已成文提案：`exec-as-pure-cpu.md`〈轉交提案／一〉第 3 條（退出碼四類 ok／無事／busy／壞了，細節寫 receipt）、第 4 條（`--loop` 回合開頭自己 `stat` `.runi`）；同檔〈壞（六條）〉第 2 條。
- status 狀態名：`t5-agent-loop.md`〈`aos status --json [WORLD]`〉——`ready`／`running`／`blocked-runi`／`bad-delivery`／`no-work`／`unknown-effect`，不把 prompt 政策塞進 status。
