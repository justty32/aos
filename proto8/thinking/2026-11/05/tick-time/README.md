# 2026-11-05 夜 時間回到 tick（tick-time，fable 規劃，未實作；11-06 使用者裁五題、Q1／Q2 改，新設計在 03）

← [2026-11-05](../README.md)｜源頭：[fs-image](../fs-image/README.md)（使用者原文在那）｜原則：[CONCEPTS 時空](../../../../docs/CONCEPTS/02-設計理念-時空.md)（C-05、C-16、C-37、C-44）、[NORMS 時空](../../../../docs/NORMS/02-設計理念-時空.md)（N-01～N-03）

**一句話**：aos 內部互相約時間（期限、租約、判卡住）一律用 tick 回合數，`AOS_TICK` 指時鐘檔；只有「人看、對外、對 Linux proc」三類留牆上時鐘。

> **11-06 使用者裁定**（逐字與新設計在 [03](03-11-06-裁定與新設計.md)）：Q3～Q5 照推薦；**Q1 改**——時鐘寫在 daemon 設定裡自帶（選填 key `tick`，可選、不強制、不耦合：daemon 只展開成一個普通 loop 型子項跑 aos-tick、把路徑用 `AOS_TICK` 傳下去）；**Q2 改**——沒 `AOS_TICK` 不是「時間不走」，退牆鐘（`ticks × AOS_TICK_INTERVAL`）當逃生口，記錄裡牆鐘欄一律寫、tick 欄有時鐘才寫。下面「方向題」段是 11-05 原列，留著對照；新題 N1（`_tick` 死了要不要重起）、N2（時鐘檔過舊要不要退牆鐘）在 03，使用者同日「那兩題都按照推薦」已裁。

## 已定（使用者 11-05 夜，照 fs-image）

- 時間就是 tick。推薦大家用 tick 回合數算時間。
- `AOS_TICK`＝要參照的那個時鐘（一個檔的路徑）。
- `AOS_TICK_INTERVAL`＝「一次 tick 大概多久」的默契；要實際時間就自己換算。
- 需要精確時間的才用牆上時鐘：①人類使用者體驗 ②跟外部交互 ③跟 Linux proc 交互（daemon）。
- aos-tick 跑在哪不重要。
- 「aos-tick 跑到一半被 sleep，重啟時怎麼界定時間」是邊緣，之後處理。

## 檔

- [01-盤點](01-盤點.md)：現行用秒的地方，逐處標「改 tick」或「留牆上時鐘」。
- [02-設計草稿](02-設計草稿.md)：時鐘檔格式、兩個環境變數沒設時怎麼辦、跟 no-pid 監管樹／state.json 的關係、sleep 邊緣清單、跟 C-44／N-01／N-03 的衝突（「沒 `AOS_TICK`＝時間不走」那列 11-06 被使用者推翻，以 03 為準）。
- [03-11-06-裁定與新設計](03-11-06-裁定與新設計.md)：使用者 11-06 逐字、`tick` key 自帶時鐘、兩鐘規則、混用的坑、新形狀的邊緣、新方向題 N1～N2、對 T 線估時的影響。

## 方向題（白話，推薦放第一）

> 11-05 原列；11-06 已裁（Q1／Q2 改），見 [03](03-11-06-裁定與新設計.md)。

1. **誰讓時鐘走？** 推薦：使用者自己起一台 `aos-loop` 跑 `aos-tick FILE`（跟其他 daemon 一樣是一個 proc，照 no-pid 監管樹掛在根 daemon 底下）；aos 不內建「自動有個時鐘」。替代：根 daemon 內建一條 tick 線——但這把時鐘綁死在 daemon 上，違背「aos-tick 跑在哪不重要」。
2. **`AOS_TICK` 沒設時，內部期限怎麼算？** 推薦：**沒時鐘＝時間不走**＝所有 tick 期限永不到（lock 租約不過期、kernel deadline 不過期、卡住不判），只印一次 warning。替代：退回牆上時鐘用 `AOS_TICK_INTERVAL` 反推——方便但偷偷把牆上時鐘混回來，凍住時又會全過期，正是今晚要解的病。
3. **`AOS_TICK_INTERVAL` 沒設時？** 推薦：預設 1000（毫秒，一 tick≈一秒），只給「要換算成人看得懂」的地方用；內部邏輯根本不該讀它。
4. **tick 數寫在哪些既有欄位？** 推薦：原本的秒／毫秒欄位改名帶 `_ticks`（`lease_ticks`、`deadline_tick`、`stuck_after_ticks`），不沿用舊名換語意，避免舊檔被誤讀。（**11-06 改讀**：使用者 11-06 選「照命名法 (Recommended)」——時間點照 C-54 R6 寫 `<事件>_at_ticks`：`deadline_tick`→`deadline_at_ticks`、`sent_tick`→`sent_at_ticks`、`acquired_tick`→`acquired_at_ticks`、`responded_tick`→`responded_at_ticks`；多久的 `lease_ticks`、`stuck_after_ticks` 不變，[lift-to-norms](../../06/lift-to-norms/README.md)。）
5. **daemon 的 3 秒／10 秒（REVIVE／GRACE）要不要動？** 推薦：不動，這兩個是跟 Linux proc 交互（SIGTERM→SIGKILL、fork 剛起就死），屬第③類。

## 明天接

- ~~使用者裁方向題 1～5~~ 11-06 已裁（03）；剩 N1、N2。
- 01 盤點只掃了 proto8/impls 與 bin 的 grep 結果；`lib/` 11-06 補掃在 [apply-ideas 01 § D](../../06/apply-ideas/01-逐項落點.md)。
- 02 的時鐘檔格式只定最小（一個整數），要不要帶 `interval_ms` 旁檔、`started_at` 給 sleep 邊緣用，列在 02 末，未定。
- 沒改程式、沒改 CONCEPTS／NORMS；衝突見 02 末段，要使用者點頭才改條文。
