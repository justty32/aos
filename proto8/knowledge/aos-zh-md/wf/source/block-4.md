# `knowledge/wf/source/block-4.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/source/block-4.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

第 4 塊：dev（開發類）的八條工作流、它們的記憶骨架、通用規則。來源是 workflows 模板 repo 的備料 `aos-prep/dev/`（備料把模板的 md 原稿轉成 json 節點；每份備料自己記的模板原稿與 commit 留在 `template_files`、`prep_commit`）。搬遷紀錄與代定在 aos repo 的 `proto8/thinking/2026-11/13/workflows-into-aos.md`。

**`#/block`**：`4`

**`#/what`**：dev（開發類）的八條工作流、它們的記憶骨架、通用規則

---

**`#/from`**（物件，5 個鍵：`repo`、`commit`、`note`、`date`、`paths`）

**`#/from/repo`**：workflows 模板 repo

**`#/from/commit`**：0d0091a2ec046e3d7bc734a70dfbd51fa80e961c

**`#/from/note`**：備料最終版 01959cecec110a8322544dc92196a12bd13c128b；它到 0d0091a 之間 aos-prep 只改了內文引用的 commit 編號

**`#/from/date`**：2026-11-13

---

**`#/from/paths`**（原文是字串陣列，17 行）

- aos-prep/dev/feature-dev.json
- aos-prep/dev/testing.json
- aos-prep/dev/refactor.json
- aos-prep/dev/moving-things.json
- aos-prep/dev/analysis.json
- aos-prep/dev/investigation.json
- aos-prep/dev/dev-env.json
- aos-prep/dev/patch.json
- aos-prep/dev/memory-verification.json
- aos-prep/dev/memory-dev-env.json
- aos-prep/dev/memory-code-map.json
- aos-prep/dev/memory-conventions.json
- aos-prep/dev/memory-notes.json
- aos-prep/dev/memory-analysis.json
- aos-prep/dev/code-map-rules.json
- aos-prep/dev/green-is-not-checked.json
- aos-prep/dev/dispatch.json

---

**`#/carried`**（陣列，17 項）

---

**`#/carried/0`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/0/here`**：wf/workflows/feature-dev.json

**`#/carried/0/from`**：aos-prep/dev/feature-dev.json

---

**`#/carried/0/template_files`**（原文是字串陣列，3 行）

- flavors/dev/workflows/feature-dev/README.md
- flavors/dev/WORKFLOWS.dev.md
- template/WORKFLOWS.md

**`#/carried/0/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/0/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；尾端 commit 照備料，不加「被派出去的不 commit」（W12＝B）

---

**`#/carried/1`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/1/here`**：wf/workflows/testing.json

**`#/carried/1/from`**：aos-prep/dev/testing.json

---

**`#/carried/1/template_files`**（原文是字串陣列，2 行）

- flavors/dev/workflows/testing.md
- flavors/dev/WORKFLOWS.dev.md

**`#/carried/1/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/1/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/2`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/2/here`**：wf/workflows/refactor.json

**`#/carried/2/from`**：aos-prep/dev/refactor.json

---

**`#/carried/2/template_files`**（原文是字串陣列，3 行）

- flavors/dev/workflows/refactor/README.md
- flavors/dev/WORKFLOWS.dev.md
- template/WORKFLOWS.md

**`#/carried/2/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/2/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/3`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/3/here`**：wf/workflows/moving-things.json

**`#/carried/3/from`**：aos-prep/dev/moving-things.json

---

**`#/carried/3/template_files`**（原文是字串陣列，2 行）

- flavors/dev/workflows/refactor/moving-things.md
- flavors/dev/WORKFLOWS.dev.md

**`#/carried/3/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/3/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`tool_gap` 改寫成使用者已裁不帶 workflows 檢查工具、knowledge 沒有查連結的出廠工具（wf-lint 的路徑改成只寫檔名）

---

**`#/carried/4`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/4/here`**：wf/workflows/analysis.json

**`#/carried/4/from`**：aos-prep/dev/analysis.json

---

**`#/carried/4/template_files`**（原文是字串陣列，2 行）

- flavors/dev/workflows/analysis.md
- flavors/dev/WORKFLOWS.dev.md

**`#/carried/4/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/4/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；not_when 的「research 包（若有導入）」改成「本庫沒有，需要就自建」；產物照原文留 md（W13）

---

**`#/carried/5`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/5/here`**：wf/workflows/investigation.json

**`#/carried/5/from`**：aos-prep/dev/investigation.json

---

**`#/carried/5/template_files`**（原文是字串陣列，3 行）

- flavors/dev/workflows/investigation.md
- flavors/dev/WORKFLOWS.dev.md
- template/WORKFLOWS.md

**`#/carried/5/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/5/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/6`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/6/here`**：wf/workflows/dev-env.json

**`#/carried/6/from`**：aos-prep/dev/dev-env.json

---

**`#/carried/6/template_files`**（原文是字串陣列，3 行）

- flavors/dev/workflows/dev-env.md
- flavors/dev/WORKFLOWS.dev.md
- flavors/dev/README.md

**`#/carried/6/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/6/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/7`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/7/here`**：wf/workflows/patch.json

**`#/carried/7/from`**：aos-prep/dev/patch.json

---

**`#/carried/7/template_files`**（原文是字串陣列，2 行）

- flavors/dev/workflows/patch.md
- flavors/dev/WORKFLOWS.dev.md

**`#/carried/7/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/7/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；產物落點照備料寫工作區的 `wf/patches/<patch>/`（W14＝A）；PATCH.md、APPLY.md 留 md（W13）

---

**`#/carried/8`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/8/here`**：wf/skeletons/verification.json

**`#/carried/8/from`**：aos-prep/dev/memory-verification.json

**`#/carried/8/template_files`**（原文是字串陣列，1 行）：flavors/dev/workflows/testing.md

**`#/carried/8/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/8/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件

---

**`#/carried/9`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/9/here`**：wf/skeletons/dev-env.json

**`#/carried/9/from`**：aos-prep/dev/memory-dev-env.json

**`#/carried/9/template_files`**（原文是字串陣列，1 行）：flavors/dev/workflows/dev-env.md

**`#/carried/9/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/9/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件

---

**`#/carried/10`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/10/here`**：wf/skeletons/code-map.json

**`#/carried/10/from`**：aos-prep/dev/memory-code-map.json

---

**`#/carried/10/template_files`**（原文是字串陣列，2 行）

- flavors/dev/workflows/common/code-map.md
- flavors/dev/COMMON.dev.md

**`#/carried/10/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/10/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件

---

**`#/carried/11`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/11/here`**：wf/skeletons/conventions.json

**`#/carried/11/from`**：aos-prep/dev/memory-conventions.json

---

**`#/carried/11/template_files`**（原文是字串陣列，3 行）

- flavors/dev/workflows/common/conventions.md
- flavors/dev/COMMON.dev.md
- flavors/dev/AGENTS.dev.md

**`#/carried/11/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

---

**`#/carried/11/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件；`suggested_items` 檔案拆分那條的「單檔超過 300 行」拿掉，改成「檔太大照 `wf/tidying.json#/split` 檢視」（第 1 塊牴觸第 3 條）

---

**`#/carried/12`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/12/here`**：wf/skeletons/notes.json

**`#/carried/12/from`**：aos-prep/dev/memory-notes.json

**`#/carried/12/template_files`**（原文是字串陣列，1 行）：flavors/dev/workflows/investigation.md

**`#/carried/12/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/12/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件

---

**`#/carried/13`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/13/here`**：wf/skeletons/analysis.json

**`#/carried/13/from`**：aos-prep/dev/memory-analysis.json

**`#/carried/13/template_files`**（原文是字串陣列，1 行）：flavors/dev/workflows/analysis.md

**`#/carried/13/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

---

**`#/carried/13/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件；`skeleton` 照備料是檔名清單（`["session_log.md"]`），沒改名

---

**`#/carried/14`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/14/here`**：wf/knowledge/code-map-rules.json

**`#/carried/14/from`**：aos-prep/dev/code-map-rules.json

**`#/carried/14/template_files`**（原文是字串陣列，1 行）：flavors/dev/workflows/common/code-map.md

**`#/carried/14/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/14/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/15`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/15/here`**：wf/knowledge/green-is-not-checked.json

**`#/carried/15/from`**：aos-prep/dev/green-is-not-checked.json

**`#/carried/15/template_files`**（原文是字串陣列，1 行）：flavors/dev/workflows/testing.md

**`#/carried/15/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/15/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/16`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/16/here`**：wf/knowledge/dev-dispatch.json

**`#/carried/16/from`**：aos-prep/dev/dispatch.json

---

**`#/carried/16/template_files`**（原文是字串陣列，3 行）

- flavors/dev/AGENTS.dev.md
- flavors/dev/WORKFLOWS.dev.md
- flavors/dev/README.md

**`#/carried/16/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/16/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`_description` 改寫（派發通則改指 `wf/workflows/_description.json`、觸發說法改指 `wf/workflows/_index.json`）；`disambiguation` 的「混合型專案（同時用了 knowledge 包）」一條拿掉（knowledge 包不併，W21）；`menu` 的「本包」改「本庫」

---

**`#/not_carried`**（陣列，2 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/not_carried/i`）

| i | `what` | `why` |
|---|---|---|
| 0 | aos-prep/dev/_description.json、_index.json、prep-report*.json（六份） | 備料的說明與報告，不是節點；`_index.json` 的 description 拿來寫 `wf/workflows/_index.json` |
| 1 | 「被派出去的不 commit、由主線驗收後 commit；push 一律先問」 | 使用者 2026-11-13 W12＝B：不寫進通用版，留給各工作區自己的偏好與鐵律 |
