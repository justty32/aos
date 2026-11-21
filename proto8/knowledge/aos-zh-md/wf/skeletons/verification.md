# `knowledge/wf/skeletons/verification.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/verification.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：驗證表的記憶骨架：專案有哪些驗證、各自的指令、誰跑、測試怎麼分類、離線能跑哪一部分。落在工作區的 `wf/knowledge/verification.json`；流程在 `wf/workflows/testing.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：這個專案的驗證指令（測試、build、lint／型別、要實機或外部服務的那類）與「誰跑」；測試分類各對到哪些指令；要特殊環境時離線能跑的子集。
- 不放：怎麼挑、怎麼跑的流程（在 `wf/workflows/testing.json`）；環境安裝與一般指令（在工作區的 `wf/knowledge/dev-env.json`）；「新檢查要證明能變紅」這種每個專案都一樣的規則（在 `wf/knowledge/green-is-not-checked.json`）。

---

**`#/fields`**（物件，4 個鍵：`checks`、`checks[].who`、`categories`、`offline_subset`）

**`#/fields/checks`**：驗證表，物件陣列，一列一道驗證：`check`（驗證名稱，含何時跑，例「快速驗證（改完必跑）」「完整驗證（commit 前）」「lint／型別」）、`command`（指令或步驟）、`who`（誰跑）。`done_when` 是靠 `check` 名稱裡的「改完必跑」四個字找到那一列，這幾個字不要省。

**`#/fields/checks[].who`**：只有兩種值：`agent`（本機跑得動）、`使用者`（要實機、外部服務、帳號、付費、目視；記到工作區的 `wf/progress.json` 一條、status 寫「等使用者」）。判不準就當後者。

---

**`#/fields/categories`**

測試分類，物件，四個鍵各寫這個專案對到的指令或範圍：`fast`＝本專案自己的 unit／source gate，每次小改都跑；`contract`＝跨元件的真實 CLI／process 邊界，改 producer、consumer 或協定時跑；`full`＝README 指定的完整離線 suite，commit 前或大改後跑；`external`＝需要實機、外部服務、素材、帳號或人工感官驗收，agent 代跑不了的記到工作區的 `wf/progress.json`（status 寫「等使用者」）。沒有的寫「無」。

**`#/fields/offline_subset`**：部分測試需要特殊環境（本機資產、外部服務、實機）時，離線可跑的子集怎麼選（例：以標籤 `RequiresXxx` 區分，離線跑 `Category!=RequiresXxx`）。沒有這種測試就留空字串。

**`#/suggested_checks`**（原文是字串陣列，1 行）：建議起手的四列（指令換成專案的）：快速驗證（改完必跑，例 `npm test`）、完整驗證（commit 前，例 `npm run test:all`）、lint／型別（例 `npm run lint`）、要實機／外部服務的那類（`who` 是使用者）。

---

**`#/rules`**（原文是字串陣列，4 行）

- 一列一道驗證；指令寫得出來才列，「目視」這類寫成步驟、`who` 填使用者。
- 至少一列標「改完必跑」——`wf/workflows/feature-dev.json`、`wf/workflows/testing.json` 的 done_when 看的就是它。
- 部分測試需要特殊環境時：在 `checks` 補列、寫 `offline_subset`，並同時在工作區 `wf/knowledge/dev-env.json#/machines` 記哪台機器跑不了。
- 記錄是物件陣列，用 json 工具讀寫（`aos/packs.json#/json`）。

---

**`#/skeleton`**（物件，3 個鍵：`checks`、`categories`、`offline_subset`）

**`#/skeleton/checks`**：`[]`（空陣列）

---

**`#/skeleton/categories`**（物件，4 個鍵：`fast`、`contract`、`full`、`external`）

**`#/skeleton/categories/fast`**：（空字串）

**`#/skeleton/categories/contract`**：（空字串）

**`#/skeleton/categories/full`**：（空字串）

**`#/skeleton/categories/external`**：（空字串）

**`#/skeleton/offline_subset`**：（空字串）
