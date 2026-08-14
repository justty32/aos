# testing — 跑測試（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

> 〔模板說明〕本檔是「單檔工作流」的範例：一個 `.md` 同時是入口與內容。膨脹了就照 [DEV-GUIDE](../DEV-GUIDE.md) 升級成資料夾型。

## 指令

- **快速驗證（Claude 自己跑、鐵律要求的那套）**：`{{指令，如 npm test / pytest / dotnet test --filter ...}}`
- **完整驗證**：`{{指令}}`

## 測試分類

> 〔模板說明〕若有「部分測試需要特殊環境」（本機資產、外部服務、實機），在這裡寫清楚分類方式與各環境能跑哪些——這是「離線機也能開發」的關鍵。例：以測試標籤區分 `RequiresXxx`，離線至少跑 `Category!=RequiresXxx`。跑不了的環境依賴驗證 → 記 [WAIT_USER](../WAIT_USER.md)。

- {{分類與說明}}
