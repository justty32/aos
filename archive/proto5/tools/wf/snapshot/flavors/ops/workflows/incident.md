# incident — 異常深查（壞了 / 紅字）

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

從異常現象查到原因、修掉、留下坑。

**何時用**：紅字、報錯、服務掛了、盤點對不上、使用者說「壞了」。
**何時不用**：只是想知道現在的狀態、沒有異常 → [inventory](inventory.md)；要改功能 / 加需求 → 開發類工作流。

## Done when

- 現象消失：`{{驗證指令，如 curl -fsS localhost:8080/healthz}}` 回傳預期值。
- 若適用：[common/gotchas](common/gotchas.md) 或 [decisions](decisions.md) 新增一列。

## 流程

1. **現象原文照貼**：錯誤訊息、log 片段、指令輸出**逐字貼**——不轉述、不摘要、不改寫成人話。一併記時間、主機 / 環境、版本。
2. **定位**：照下表由近到遠看，每看一處記「看到什麼」。
3. **修**：先說「要做什麼、影響什麼」再動手。重啟、刪資料、改線上設定、回滾這類不可逆或對外動作守**鐵律 2（授權來源）**——沒有授權來源就先問。
4. **驗證**：跑 Done when 的指令，把輸出原文貼回。
5. **記坑**：第二次撞到、或使用者說「上次也是這樣」→ [common/gotchas](common/gotchas.md) 一列（門檻見 [STRUCTURE](../STRUCTURE.md)）。

## 定位表（第 2 步）

| 看哪裡 | 指令 |
|--------|------|
| 服務 log | `{{指令，如 docker logs --tail 200 <服務>}}` |
| 系統 log | `{{指令，如 journalctl -u <服務> -n 200}}` |
| 資源 | `{{指令，如 df -h; free -m}}` |
| 最近改動 | `{{指令，如 git log --oneline -10}}` |

> 〔模板說明〕由近到遠排：先看出事的那個服務，再往系統、資源、最近改動擴；填成這個專案真的跑得動的指令。

## 交接

- 要使用者親自處理（重開機、找廠商、給憑證）→ [WAIT_USER](../WAIT_USER.md) 一行。
- 修法有兩個以上選項且選了一個 → [decisions](decisions.md) 一列。
- 確認整體回穩 → [inventory](inventory.md)。
