# kernel 意圖卡（第一版，r6）

← [intents](README.md)｜藍圖 [blueprint-kernel1](../blueprint-kernel1.md)｜依據 [kernel-pack §10](../reviews/2026-10-05/kernel-pack.md)（全照預設）

**①解決什麼**：「替任務做決策的任務」——一個普通 keep 任務，每個自己的 tock 讀指定來源的公開事實（帶身分、版本、來源鐘、讀取狀態的快照）→ 純函式規則 → 驗證決定 → **先存意圖再送控制** → 核對回條 → 被殺接續。第一版只做觀測與「綁 run 的 kill」。第一條實用規則＝**監督 brain**：一封信連續 N 回合沒進展就先寄信給人，再超過 M 回合才 kill 那個 run（keep 會重起、brain 從 task.json 接續，不重問）。

**②必要的副作用**：寫自己槽內 `state.json`（意圖、tock 水位、規則狀態，一次 rename）與 `decisions.json`（只留上一次，人看）；寫目標槽 `ctl.json`（`{"op":"kill","run","id","by","why"}`，核心既有協定）；有設 mail 才寄 NEEDS-USER 給 `you`；events 可選。只讀 brain/task.json、birth／exit／last-round／tock.json。不花錢、不連網、不改核心、不改任何包。

**③不做**：restart／reload、改 tasks.json、daemon pause／resume、動態 mounts、多控制者、外部程式或 LLM 規則、aos7-pack、接管 step／budget／adapt、判「健康」或業務完成、累積歷史、跨 node／刪槽後的接續、撤回已送出的 kill。

**人類面**：新手零新概念。`aos7-up` 預設不裝；裝法只在 ADVANCED（`aos7-ctl add` 一行）；`aos7-kernel status <node>` 一行白話（「監督 2 件：都在動／第 7 回合起沒進展，已寄信」）；旁觀者從信箱就看得出監督者寄了信。

**④對照現狀多出來的**：先通知後 kill 兩段 → **保留**（kill 不可逆）；mail 依賴 → **改成可選**（沒 mail 只寫 decisions.json）；events 發布 → **可選、預設關**。
