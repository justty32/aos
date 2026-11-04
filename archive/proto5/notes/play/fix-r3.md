# 試玩 r3 修正輪（fix-r3，2026-09-24）

← [play/](README.md)｜來源：[astra](2026-09-24-r3-astra.md)、[Opus](2026-09-24-r3-opus.md)；重點：`status`／`ls` 一眼看出正不正常

codex（gpt-6-astra）三條線依序跑；文件隊長改，標「（09-24 試玩 r3 補／改）」。
測試 1016 → 1055 條，連跑兩次綠；pgrep 空。README 照抄全跑（含「每天重開機」）：通，約 68 秒；模型用 LiteLLM `localhost:4000`／`deepseek-chat`（GPU 使用者在用）。

## 第 1 段：拆 `aos_kernel.py`

789 行拆成 info／ledger／engine／boot／cli 五支（≤ 224 行），`aos_kernel.py` 只留匯出層；48 段原文逐字一致，舊測試沒改。

## 第 2 段

| # | 狀態 | 做了什麼 |
|---|---|---|
| 1 | 已做 | `status` 的 `error` 改成這次原因：暫停中印根因＋「已連敗 3 次，等 continue」；救回後「（無）」＋舊錯標時間與「已恢復」；touch 只在 `-v`／`--json` |
| 2 | 已做 | `aos_kernel_health.py`：`ls` 第一行 `health`（ok 或哪裡壞＋該打的指令），取代尾巴 hint；`status` 第一行 agent 健康 |
| 3 | 已做 | 沒登記的 `say` 照投、stderr 警告；`--wait` 立刻退 101（含等到一半被 stop） |
| 4 | 已做 | `say -h` 兩例＋timeout 預設；README「每天重開機」、daemon 與終端、等待時間範圍、多則合成一輪 |
| 5 | 已做 | 六份規範標頭只留一句，沿革搬檔尾；aos-llm-call 的調度者裁決也搬檔尾 |

真機驗過：壞 port 時 `error` 直接是 Connection refused；搬走 `K/requests/` 時兩個第一行都喊缺目錄。

## 隊長裁決

1. **kernel 健康先後**：缺目錄 → 停機中 → daemon 沒活 → cpu missing → tick 停住（`state.json` 超過 max(10 秒, 10 格) 沒動）→ ok。缺目錄時帳本照樣每格更新，判不到停住，所以排最前。
2. **拿掉 `ls` 尾巴兩條 hint**，改由 health 講，不講兩次。
3. **agent 健康多兩種**：「kernel 判壞了」「設定讀不到」。
4. **舊 say --wait 測試改測「沒登記」**（假家本來沒登記）；成功／暫停／逾時／半寫檔在新檔以已登記的家重測。
5. **`--json` 的 `last_error` 保持＝最後一行**，新鍵 `current_error` 才是這次原因。
6. **模型例子改 LiteLLM／deepseek-chat**，寫明任何 OpenAI 相容端點都行（調度者中途指示）。

## 沒做

`say --wait` 進度訊息、`NotAnAgent` 提示、`start` 缺 `AOS_K` 的範例；行程 `bad` 時 `say --wait` 仍等到逾時；3.12 沒實跑。
