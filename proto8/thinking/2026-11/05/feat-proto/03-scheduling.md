← [入口](README.md)｜件 3：kernel 依信件附帶資訊排程｜上一份 [02-endpoint-packs](02-endpoint-packs.md)｜下一份 [04-spawn-agent](04-spawn-agent.md)

# 件 3：kernel 依信件附帶資訊排程（fable 照原則定，可翻案）

使用者原文（11-05 午，逐字）：「讓kernel能根據信件中額外附送的priority之類資訊做排程」。現況（[aos-llm-kernel docs/02](../../../../impls/aos-llm-kernel/docs/02-token-回報與額度.md)「一次」第 5 步）：信 body 的 `priority`＝`low`／`normal`／`high`、數字、或 `{"level", "deadline"}`；排隊＝**級數＋等了幾次÷10（aging）大的先 → deadline 近的先 → 等得久的先 → 先寄的先**；同時在飛不超過 kernel 的 `slots`；deadline 已過回 `DeadlineMissed`；額度到頂回 `BudgetMissing`（或 `spent: wait` 等下一窗）。11-05 早起 kernel 不自己跑、每封請 daemon 掛成 proc、一拍收成品再補位。

## 已定（照原則推得出）

- **信的 `priority` 形狀不變、不加新欄**：`level`、`deadline` 已經是「信件額外附送的資訊」，缺的不是欄位、是 kernel 排程時沒看包的屬性。C-11「排序＝決定哪個任務先給哪個資源」——資源現在多了一層：每個包是一種資源（C-09 有限就是資源、C-10 用格數表示 → 包的 `slots`）。
- **kernel 只排、不改信的內容**：代號是寄信的人選的，kernel 不替他換包（C-56 寫什麼就做什麼；見衝突）。
- **一拍的順序照舊**：收成品 → 收拾 → 擋壞信 → 排隊 → 補位到滿 → 寫 `queue.json`、退 0、不等。

## 代定（照推薦定，可翻案）

1. **排隊順序多一條**：級數（含 aging）→ deadline → **包的 `speed`（fast → normal → slow）** → 等得久 → 先寄。放在 deadline 之後：急的先、有時限的先，剩下同級的讓快的先走（快的早放格、整體吞吐高；慢的靠 aging 不會餓死）。
2. **包各自的 `slots`＝補位時跳過**：排好的順序一封封看，這封的包在飛數已達它的 `slots` ＝**跳過、看下一封**（不是停下）；kernel 總 `slots` 到了才停。效果：`stupid-fast`（本機一次只跑一封）滿了，後面寄給 `smart-high` 的照樣補位；今天的行為是「第一封塞住、整列等」。
3. **包的 `budget`**：到頂判法同 kernel 的（`counter_calls`＋在飛＋這次新掛 ≥ `max_calls`、或 `counter_tokens` ≥ `max_tokens`），到頂＝那封回 `BudgetMissing`，msg 寫 `endpoint smart-high: max_calls 200 reached in this day`（kernel 總額度照舊先判）。`spent: wait` 時只有「總額度到頂」才停整列；包到頂的那封留在 `new/` 等、別包照跑。
4. **在飛的包計數**：從 `cur/<信>/request.json` 的 `endpoint`… 不夠（request.json 存的是解好的那組、沒有代號）→ `proc.json` 多記 `"endpoint": 代號`。`used.json` 多 `packs`。
5. **不做的**：搶位（殺掉在飛的 low 讓 high 進——HTTP 一刀砍掉錢已經花了）、每個寄件人配額（10-15「濫用：先信任」）、信裡寫 `max_cost`／`max_wait_ms`（沒人要）。都列在這裡當以後的候選。
6. **文件**：`docs/02` 的「排隊」與「到頂怎麼判」各補一句；N-42 (1)「kernel 一次挑最該跑的（級數＋aging → 時限 → 等得久 → 先寄）」改成含 speed 與包 slots。

## 留給使用者的題（推薦放第一）

- **題 2：包的額度用完要不要自動降級**（`smart-high` 到頂 → 改用 `stupid-fast`）。(a) 推薦**不降級**：回 `BudgetMissing`，寄信的 agent 收到錯、自己決定（agent-fsm 現在是停下等人；要自動就在範本的 wait 加一條「`BudgetMissing` 就 `aos-agent llm set endpoint=stupid-fast` 再回 think」——那是 agent 範本的事、不是 kernel 的）。後果：多一趟來回，但誰用了什麼腦一清二楚。(b) 包寫 `"fallback": "stupid-fast"`，kernel 到頂時換包跑、回信的 `model` 說實話。後果：省一趟，但寄的人寫 A 拿到 B（違 C-56），帳也算在 B 上。
- **（順帶）aging 的 10 次一級要不要改成跟 `interval_ms` 無關的秒數**：現在 daemon 300 ms 一拍＝3 秒升一級、low 等 6 秒就超過 high；推薦先不動（有 deadline 可用），實測嫌快再改。

## 衝突

- **C-56 寫什麼就做什麼 vs 自動降級**：見題 2，推薦 (a)。
- **「先寄先跑」的直覺 vs speed 插隊**：同級時慢包的信會被後寄的快包信超過。這條今天就不保證（有 priority 就有超車），且只在同級、同 deadline 狀態下；aging 保底。不算新衝突，寫進 docs 一句。
