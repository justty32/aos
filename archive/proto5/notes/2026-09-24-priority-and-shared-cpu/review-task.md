# 任務書：「agent 優先級與共用 cpu」提案唯讀審查（2026-09-24）

你是唯讀審查員（codex gpt-6-astra，`-s read-only`）。用繁體中文寫報告。**不要改任何檔**，只讀、只寫報告到 stdout。
不要跑 daemon、kernel、模型。

## 背景

使用者問了兩題：(1) 讓某個 agent 的 llm／tool 使用最優先；(2) 讓一些 agent 共用 cpu。調查隊長寫了一份**提案**（不改程式）：

- `proto5/notes/2026-09-24-priority-and-shared-cpu/README.md`（總結＋要使用者拍的）
- `proto5/notes/2026-09-24-priority-and-shared-cpu/priority.md`（題 1）
- `proto5/notes/2026-09-24-priority-and-shared-cpu/shared-cpu.md`（題 2）

依據：proto5 規範 `proto5/spec/kernel/`（尤其 tick.md 第 6～8 步、ledger.md、syscall.md、home.md §1.1、cli-ops.md）、`proto5/spec/cpu/methods.md`、
`proto5/spec/agent/info.md`、`proto5/spec/aos-agent/`（send.md、register.md、tick.md、collect.md）、`proto5/spec/aos-llm/`；
程式 `proto5/lib/aos_kernel_engine.py`（`dispatch`、`collect`）、`aos_kernel_ledger.py`（`_add`）、`aos_kernel_check.py`、`aos_agent_batch.py`、`aos_agent_home.py`、`aos_agent.py`（start）；
池式草稿 `proto5-2/README.md`、`proto5-2/spec/kernel-ledger.md`、`kernel-tick.md`、`kernel-pools.md`、`scale.md`；教程 `proto5/tutorials/05-many-agents.md`。

## 要審的（每條給：嚴重度〔必修／建議／可忽略〕、檔:行、現象、依據、建議改法）

1. **事實有沒有講錯**：逐條核對提案裡關於現況的斷言，例如——派工是先到先派、隊伍只有帳本一條、工作 cpu 的 `requests/` 最多一件 kernel 派的單、
   llm cpu 同步等模型、同格多張 syscall 照檔名排、反覆行程回 queue 尾所以輪流、改 `K/info.json` 加 cpu 不用重 boot、
   `tick.pool`／`interval_ms` 要 stop／start 才換而 `llm.pool`／`tool_pool` 下一批就生效、`aos-kernel check` 只認名叫 `llm` 的池、
   `llm.params` 原樣併進 HTTP body、工具只能在 agent 一級選池、`kind=aos` 的意思、路徑圖每一步對不對、行數估計離不離譜。
2. **漏掉的選項**：題 1 的 (a)(b')(c)(d) 與題 2 的 (i)～(v) 之外，有沒有更便宜或更合理的做法被漏掉？(b) 被判「不成立」的理由站不站得住？
3. **餓死與公平性**：(a) 的餓死分析（「一個 VIP 很難餓死別人」這個上限對嗎？一批工具的件數、tick 的 not_before、多個 VIP）；
   (c) 的硬切與 (d) 的借用——amy 的 cpu 借給別人時最壞要等多久；(c) 裡 amy 的 tick `interval_ms` 調小的副作用；
   工具加 `_pool` 之後，一顆 cpu 的共用池會不會讓某些 agent 永遠卡住（例如一個 agent 的一批裡有很多 call 都走同一顆）；優先權倒置還有哪些。
4. **(c) 的操作步驟與共用工具例子**：照規範真的走得通嗎？有沒有遺漏的步驟或會踩到的錯（pool 驗證、envs 只在建家時抄、check／probe、`aos-agent check` 的模型表、`AlreadyExists`）。
5. **proto5-2 那欄**：各選項在池式下的說法對不對（`ready`／`delayed`、`cpu add`）。
6. **上千個 agent 的瓶頸表**：有沒有講錯或漏掉的。

## 產出

報告開頭一段總結＋「必修 N 條、建議 M 條」，再逐條列。最後一段「我沒看的」。不要貼大段原始碼。
