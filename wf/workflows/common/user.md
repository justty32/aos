# user — 使用者偏好與確認邊界

← [common/README](README.md)

agent 不用重猜的事。always-on 鐵律在 [AGENTS.md](../../../AGENTS.md)，這裡是**這位使用者**的偏好——改了改這裡，不改鐵律。

| 項目 | 設定 |
|------|------|
| 語言 | 回覆與 `wf/`／`docs/` 一律繁體中文；程式碼沿用各檔既有語言 |
| 分支慣例 | 直接 commit `main`；push 先確認（鐵律 2）。分支只用於凍結或實驗 |
| 直接做、不用問 | 改 `wf/` 文件、加測試、跑唯讀指令、build／ctest、開子 agent 隊、做原型讓他試 |
| 一定先問 | push、刪檔、開新工作（鐵律 2）；**方向性裁決**（鐵律 5）——我擺選項與後果，他拍板 |
| 回覆風格 | 先結論、短；問「要不要」時附**可執行判準**（門檻數字）與後果。他說「不想看」時用實測取代拍板 |
| 時區 | Asia/Taipei（推的；不對就改這格）|
| 工作模式 | 我當調度者、不親做內容；隊形見 [dispatch/aos-teams](../dispatch/aos-teams.md) |

領域詞彙以 `docs/aos-folder.md` 的定義為準；常猜錯再開 `glossary.md`（見 [common/README](README.md)）。
