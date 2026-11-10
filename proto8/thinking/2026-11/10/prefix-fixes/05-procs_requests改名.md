# prefix-fixes 05：線 6——`procs_ctl_mailbox` 改名 `procs_requests`

← [prefix-fixes](README.md)｜使用者原話在 README「使用者裁定」段

## 結論

- daemon 的名單信箱三個身分一起改名：stack 裡資料夾的預設名、`daemon.json` 的 key、`procs_state.json` 的欄位；回信箱跟著是 `procs_requests/reply/`。照 11-06 [mailbox-naming 05](../../06/mailbox-naming/README.md) 的做法：不認舊名、不寫遷移、不留舊名提示。
- 原則（使用者）：箱子照**承載的機制**取名，不拿底層的 mailbox 取名；收進 C-54 R14 的 11-10 註。其他帶 mailbox 的機制名（`mailbox_warning`、`MailboxMissing`／`MailboxBad`、`--mailbox`、`daemon_reply/`、程式內部識別字）使用者裁「不用」改；agent 的 `queue/` 不動。
- `cmd/aos-agent/stack.gitignore` 那行順手改成 `**/procs_requests/reply/`（原本根錨定，巢狀 daemon 的沒擋到）。
- 條文：C-54 R14 補 11-10 註、R7 例與 `NORMS/命名.md` 改名加註、N-10／N-13／N-28 加「11-10 改名」、附錄 3 舊名對照加一列、附錄 4 持久檔三列。
- 驗：全家重建過；`impls/aos-daemon/tests` 67、`impls/aos-llm-kernel/tests` 21（兩個 live 沒跑）、`lib/aos/judge/tests` 6 都 OK；/tmp 假腦三層（根 → 總機＋領班 → agent）`add／rm／stop／start／ping` 都過，三台 stack 只有 `procs_requests/`、`procs_state.json` 欄名是新的。舊名 grep 只剩 thinking、archive、舊名對照、R14 引的原話、wf 歷史日誌。

## 要重建什麼

所有在跑的 daemon（含總機、領班這種巢狀 daemon）換新 binary 重起。舊 stack 的 `procs_ctl_mailbox/` 沒人讀，裡面沒處理的信不會套用，要清就手刪。`daemon.json` 明寫 `"procs_ctl_mailbox": …` 的 key 要改成 `procs_requests`——舊 key 當沒看到，信箱照樣開在預設 `procs_requests/`（原本寫 `null` 想關信箱的會變成開著）。試驗場 `~/code/playground` 照 main 重刷（含試驗場的 `lib/` 複本）。

## 沒改、留給使用者看

- 「ctl 信箱」「ctl mailbox」這個說法（全 proto8 約 70 處，含錯誤訊息 `the daemon has no ctl mailbox (procs_requests … is null)`）沒改：任務範圍只講箱名的三個身分。照同一條原則它也是「拿機制取名」，要不要統一成「requests 信箱」等使用者定。
