# 2026-10-15 通用 kernel：判官是一個 agent，閘門照舊

← [討論紀錄](README.md)｜前情：[kernel 截流](2026-10-15-kernel-intercept.md)、[LLM kernel](2026-10-15-llm-kernel.md)｜規範：[N-42](../NORMS/09-kernel.md)、[N-16 信箱](../NORMS/05-基礎設施-窗.md)、[N-28](../NORMS/04-基礎設施-loop與daemon.md)、[N-20](../NORMS/07-基礎設施-組合子.md)｜概念：[C-47、C-11、C-15、C-29](../CONCEPTS/04-kernel.md)、[C-46](../CONCEPTS/05-agent.md)｜程式：[lib kernel.md](../lib/kernel_llm.md)、[lib agent.md](../lib/agent.md)

## 原文（10-15，照記）

「規範這塊，我們就先做兩種kernel，一個用於管理LLM呼叫，一個則是通用的管理(以agent作為判斷)，然後都基於daemon。具體機制再來規劃。」（N-42）

「kernel就是以inst/loop/daemon為基礎，能夠管理某一inst是否被執行的，一個正在執行，或是被執行的inst。」（C-47）

「都隨意」（10-15，答六個未決）

「管LLM那塊，這塊很多時候都是確定性的……這個沒啥可說的。」

## 決定（使用者 10-15 定）

- 第二種 kernel＝通用管理，**判斷交給 agent**；基於 daemon。
- 排程看呼叫樹的特性，由子葉彙總，寫在 `_metainfo`；巢狀卡死不防護（N-20 精神）。

- 六個原未決（10-15 使用者答「都隨意」，照建議）：
  1. 判官不看信的 stdin 摘要；要就作者寫進 `_metainfo.summary` 一句。（10-15 使用者『隨意』，照建議）
  2. 判官腦先不挑：LM Studio 小模型＋嚴格 schema；判不好就退回規則。（10-15 使用者『隨意』，照建議）
  3. `human` 格：人正在回信就算佔格；回信落檔即釋放，`timeout_ms` 到也釋放。（10-15 使用者『隨意』，照建議）
  4. 拍距 `interval_ms` 2000；信少就走省判官那條。（10-15 使用者『隨意』，照建議）
  5. 判官不能「換隊」；只回三種話，級數仍由閘門填。（10-15 使用者『隨意』，照建議）
  6. 第一種先不併進第二種，兩支各自跑；跑順再併。（10-15 使用者『隨意』，照建議）

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

## 最輕原型

- `aos_kernel.py`：抄 `aos_gate_kernel.py`，排序那步換成「跑判官格、讀答案」，其餘不動；設定多 `judge`（TARGET）、`slots: {"llm": 1, "cpu": 2}`。
- 判官一：`judge_rules.py`，同一介面、純規則（先來後到＋同資源不超格）——先用它把形狀、後援、省判官跑通。
- 判官二：`judge/agent.json`（bob 式），system.md 寫「只回 run／defer／reject」，腦走 LM Studio；錯就退回規則。
- demo：三個閘門（假腦 sleep、假 cpu 活、假人回信）同時丟信，看 kernel log 的順序與 `judge_fails`。

## 動工自定點

10-15 做了基礎實作（[lib kernel2.md](../lib/kernel_general.md)、demo `run.py kernel2`），自己定的、等使用者看：

- **一拍＝一段忙碌期**：一拍裡一封一條執行緒、各自一支子程式，誰跑完就放格、馬上再決定；沒有在跑的才結束這拍。這樣 human 格等人時，llm／cpu 照樣排得動；子程式都在 loop 起的那個行程群組裡，收工整群收、不漏。代價：一拍可能很長，`waited_runs` 在一拍裡不長（另給 `waited_ms`）。
- **判官的輸入輸出**（使用者 10-15 拍板）：stdin＝kernel 的 state 窗整份（loop 骨架的 `state`／`pid`／`runs`／`last_error`／`beat`＋`queue`、`running`、`slots`、`budget`、`served`、`seen`、`judge_fails`、`judge_error`、`last_sig`）；stdout 保留 `run`／`defer`／`reject`，reject 每項 `{"id", "error": {code, msg}}`。同一個 id 出現兩次＝形狀不對。**10-15 再改（使用者「剩下都隨意」）**：stdin 瘦成 state 窗的子集 `queue`／`running`／`slots`／`budget`（同一份物件、不是新格式，C-48），兩種判官都這樣；整份太大，小模型判官慢（[實跑](2026-10-15-judge-live.md)）。
- **省判官的「局面」**＝排隊名單＋在跑名單＋各資源空格；記在 state 窗 `last_sig`，跨拍也沿用（判官全 defer、局面沒變＝不再問；有空格則由補位跑，見 kernel2.md）。
- **`judge_fails`＝連錯次數**（每次問都算，不是每拍）；判官對一次歸零；到 `max_fails` 停問，人把它改回 0 才再問。
- **資源**：`_metainfo.resource` 沒寫或 `"none"`＝便宜的，不佔格、不問判官；寫了 `slots` 沒有的＝`ResourceUnknown`。`slots` 純值 n＝`{"llm": n}`。`budget` 只管 `llm` 的信。
- **判官環境**：一律拿掉繼承的 `AOS_KERNEL`；判官 inst 自己 `envs` 指回本信箱也拿掉，指別的照給。判官沒寫 `timeout_ms`＝30 秒。
- **agent 判官**：`judge/ask_judge.py` 包 `aos_agent_call`，取最後一句裡第一個 `{` 到最後一個 `}`；沒用 `_tool` schema 硬約束（小模型錯就退回規則）。
- **新增的 key**：kernel 設定 `slots`（物件）、`judge`、`max_fails`、`poll_ms`；state 窗見上；信不加 key。抄自第一種的幾支小函數（讀信、回信、認領、跑一封）在 `aos_kernel.py` 另一份，日後併。
