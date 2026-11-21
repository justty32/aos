# `knowledge/wf/workflows/user.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/workflows/user.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：記使用者偏好與確認邊界：agent 不用重猜的事。記的是這位使用者的偏好；always-on 鐵律在工作區的 `AGENTS.md`（條文見 `wf/knowledge/iron-rules.json#/rules`），偏好改了改偏好、不改鐵律。偏好表長什麼樣在 `wf/skeletons/user.json`。

---

**`#/when`**（原文是字串陣列，2 行）

- 使用者說「我的偏好是…」「以後直接做／先問」。
- 使用者說了偏好、講定了確認邊界（哪些事可以直接做、哪些一定先問），或講定分支慣例、時區、語言。

---

**`#/not_when`**（原文是字串陣列，3 行）

- 一次性的小事不記（例：「這次先不要跑測試」）——那是當下的指示，不是長期偏好。
- 要改的是任何時刻都適用的鐵律 → 那在工作區的 `AGENTS.md`（條文見 `wf/knowledge/iron-rules.json#/rules`，夠不夠格見 `wf/knowledge/iron-rules.json#/adopt`），不在這裡。
- 長期知識該歸哪一層 → `wf/layers.json#/layers`。

**`#/done_when`**（原文是字串陣列，1 行）：工作區的 `wf/knowledge/user.json` 的 `prefs` 裡對應那一項已改成新設定（或新增了一項），且檔內沒有留下與新偏好矛盾的舊值。

---

**`#/steps`**（原文是字串陣列，5 行）

- 讀工作區的 `wf/knowledge/user.json`；還沒有 → 照 `wf/skeletons/user.json#/skeleton` 建。
- 找到對應的項目（語言、分支慣例、直接做不用問、一定先問、回覆風格、時區）；沒有對應的就新增一項。
- 改那一項的 `setting`；同檔有跟新偏好矛盾的舊說法一併改掉。不動 `AGENTS.md` 的鐵律。
- 回覆風格：這位使用者對回覆的偏好記在 `prefs` 的回覆風格那項（本庫沒有出廠的通用回覆規則）。
- 領域詞彙常猜錯 → 照 `wf/skeletons/user.json#/glossary` 開詞彙表。

**`#/handoff`**：記完回到原本的工作。
