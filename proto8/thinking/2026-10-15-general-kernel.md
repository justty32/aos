# 2026-10-15 通用 kernel：判官是一個 agent，閘門照舊

← [討論紀錄](README.md)｜前情：[kernel 截流](2026-10-15-kernel-intercept.md)、[LLM kernel](2026-10-15-llm-kernel.md)｜規範：[N-42](../NORMS/09-kernel.md)、[N-16 信箱](../NORMS/05-基礎設施-窗.md)、[N-28](../NORMS/04-基礎設施-loop與daemon.md)、[N-20](../NORMS/07-基礎設施-組合子.md)｜概念：[C-47、C-11、C-15、C-29](../CONCEPTS/04-kernel.md)、[C-46](../CONCEPTS/05-agent.md)｜程式：[lib kernel.md](../lib/kernel.md)、[lib agent.md](../lib/agent.md)

## 原文（10-15，照記）

「規範這塊，我們就先做兩種kernel，一個用於管理LLM呼叫，一個則是通用的管理(以agent作為判斷)，然後都基於daemon。具體機制再來規劃。」（N-42）

「kernel就是以inst/loop/daemon為基礎，能夠管理某一inst是否被執行的，一個正在執行，或是被執行的inst。」（C-47）

「管LLM那塊，這塊很多時候都是確定性的……這個沒啥可說的。」

## 決定（使用者 10-15 定）

- 第二種 kernel＝通用管理，**判斷交給 agent**；基於 daemon。
- 排程看呼叫樹的特性，由子葉彙總，寫在 `_metainfo`；巢狀卡死不防護（N-20 精神）。

## 結論（AI 整理，待使用者確認）

**管什麼**：任何被閘門包住的 inst（不限腦）。每封信只回三種話：**現在跑**、**再等**、**不跑**（附代號與白話，N-29）。資源種類＝`_metainfo.resource` 一個字（`llm`／`gpu`／`cpu`／`disk`／`net`／`human`），kernel 設定裡每種有幾格（C-10）；`human`＝人的注意力也是外部 PU（C-28、C-29），格數 1。

**請求怎麼到**：**閘門不改**。`aos_gate.py` 的 `kernel` 指到通用 kernel 的信箱就行，信的形狀同第一種（inst、stdin、priority、`_metainfo`、reply）。第一種是第二種的特例：判官換成規則腳本。

**身體一拍**（daemon 底下一個 loop，照 `aos_gate_kernel.py` 的骨架）：收殘信→過期／額度照舊→**問判官**→照答案認領、真跑、回信。判官＝表上一格 aos-inst TARGET（C-15：排序程式人寫或叫模型寫），預設是 `bob/` 式 agent 走 `aos_agent_lib.py ask`。

- **給判官看的 stdin**：`{tick, queue: [{id, priority, _metainfo, waited_ticks}], running: [{id, resource, since}], slots: {llm: {total, used}, …}, budget}`。不給 stdin 內容（省注意力，也不洩漏）。
- **判官回的 stdout**（約束形狀，走 `_tool` 的 schema）：`{"run": [id…], "defer": [id…], "reject": [{"id", "code", "msg"}]}`。沒點名的＝defer；`run` 超過空格的截掉；不認得的 id 忽略。
- **後援**：判官結束碼非 0、超過它的 `timeout_ms`、回的不是這個形狀、或 fsm `halted`＝這拍改用第一種的確定規則（級數＋aging＋先來後到），state 窗記 `judge_fails`；連錯 `max_fails` 拍就一直用規則、等人。
- **判官自己的腦不走自己**：它的 `brain` 直接指 LLM kernel 的閘門或直接叫，不指通用 kernel 的信箱（否則判官排隊等判官＝自己卡自己）。環境變數 `AOS_KERNEL` 在判官的格裡清掉。
- **省判官**：`new/` 的信名集合、`running`、格數跟上一拍一樣＝不問、沿用上拍答案；只有 0 或 1 封且有空格＝不問、直接跑。判官跑的時間算在這拍裡；信還在 `new/`，照樣算進它的 `wait_ms`。
- **跟 N-20**：判官的答案不保證可重現；kernel 重起 `cur/` 殘信照第一種回 `KernelRestarted`。
- **kernel 公告**：判官 reject／defer 的理由將來貼公告欄；公告欄在哪、格式，使用者說晚點再說，這裡只標記。

## 未決（括號＝建議預設）

1. 判官要不要看信的 stdin 摘要？（不看；要就作者寫進 `_metainfo.summary` 一句）
2. 判官腦用哪顆？（LM Studio 小模型＋嚴格 schema；判不好就退回規則，所以先不挑）
3. `human` 格怎麼算用掉：人正在回信就算佔格？（是；回信落檔即釋放，`timeout_ms` 到也釋放）
4. 一拍問一次判官太貴時的拍距？（`interval_ms` 2000；信少就走省判官那條）
5. 判官可以「換隊」嗎（把 low 升成 high）？（不行；只回三種話，級數仍由閘門填）
6. 第一種要不要併進第二種（判官＝規則腳本）？（先不併，兩支各自跑；跑順再併）

## 最輕原型

- `aos_kernel.py`：抄 `aos_gate_kernel.py`，排序那步換成「跑判官格、讀答案」，其餘不動；設定多 `judge`（TARGET）、`slots: {"llm": 1, "cpu": 2}`。
- 判官一：`judge_rules.py`，同一介面、純規則（先來後到＋同資源不超格）——先用它把形狀、後援、省判官跑通。
- 判官二：`judge/agent.json`（bob 式），system.md 寫「只回 run／defer／reject」，腦走 LM Studio；錯就退回規則。
- demo：三個閘門（假腦 sleep、假 cpu 活、假人回信）同時丟信，看 kernel log 的順序與 `judge_fails`。
