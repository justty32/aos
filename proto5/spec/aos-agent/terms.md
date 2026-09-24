← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| 走一格 | 叫一次 `aos-agent tick`：最多做一件事（收輸入、送一批、收回一批並結清）就退出 |
| 門 | `state.json` 的 `waits`，外人的等待表（[agent.md §4.2](../agent/state.md)） |
| 當批 | `state.batch`：一次送出、一起收回的工作（[agent.md §4.3](../agent/state.md)） |
| 工作名 N | 一件工作的名字。**三種名字寫死**：kernel 行程名＝`N`；放進 `K/requests/` 的 request 檔名＝`N.json`（回音就出現在 `K/responses/N.json`）；ack 的 `params.name`＝`N.json`。`work/` 裡的檔是 `N.inst.json`、`N.in`、`N.out` |
| 批 id B | `aw-<agent 資料夾名>-<epoch ns>-<pid>`；第 i 個 call 的工作名是 `B-<i>` |
| 放單／回音／ack | 放單＝往 `K/requests/N.json` 放 `add`（tmp＋`link`，[cpu.md §3.1](../cpu/messages.md)）；回音＝`K/responses/N.json` 的執行狀態，答案在 `work/N.out`；ack＝結果寫進 `done` 後放的 notification（[cpu.md §3.3](../cpu/messages.md)） |
| K | kernel 家。只有 §5.1 建批那一刻讀 `AOS_KERNEL_HOME`（絕對路徑；09-24 fix-r4 由 `AOS_K` 改名）記進 `batch.kernel`；之後送件（含崩了重送）、收回、ack、清檔一律用 `batch.kernel` |
| tick 鎖 | （09-24 fix-r4 補）agent 家的 `.tick.lock`：`tick` 整格持著的獨占 flock，同一個家同時只有一個 tick 在做事（§2.1） |
| 手動暫停 | （09-24 fix-r4 補）agent 家有 `paused` 這個檔：`pause` 建、`continue` 刪；有它時 `tick` 什麼都不做就退 0（§1.6） |
