# `knowledge/wf/source/block-3.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/source/block-3.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

第 3 塊：kernel 的四條薄工作流、它們的記憶骨架、鐵律、派發通則、活清單寫法。來源是 workflows 模板 repo 的備料 `aos-prep/kernel/`（備料把模板的 md 原稿轉成 json 節點；每份備料自己記的模板原稿與 commit 留在 `template_files`、`prep_commit`）。搬遷紀錄與代定在 aos repo 的 `proto8/thinking/2026-11/13/workflows-into-aos.md`。

**`#/block`**：`3`

**`#/what`**：kernel 的四條薄工作流、它們的記憶骨架、鐵律、派發通則、活清單寫法

---

**`#/from`**（物件，5 個鍵：`repo`、`commit`、`note`、`date`、`paths`）

**`#/from/repo`**：workflows 模板 repo

**`#/from/commit`**：0d0091a2ec046e3d7bc734a70dfbd51fa80e961c

**`#/from/note`**：備料最終版 01959cecec110a8322544dc92196a12bd13c128b；它到 0d0091a 之間 aos-prep 只改了內文引用的 commit 編號

**`#/from/date`**：2026-11-13

---

**`#/from/paths`**（原文是字串陣列，11 行）

- aos-prep/kernel/decisions.json
- aos-prep/kernel/planning.json
- aos-prep/kernel/gotchas.json
- aos-prep/kernel/user.json
- aos-prep/kernel/memory-decisions.json
- aos-prep/kernel/memory-ideas.json
- aos-prep/kernel/memory-gotchas.json
- aos-prep/kernel/memory-user.json
- aos-prep/kernel/live-lists.json
- aos-prep/kernel/iron-rules.json
- aos-prep/kernel/dispatch.json

---

**`#/carried`**（陣列，11 項）

---

**`#/carried/0`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/0/here`**：wf/workflows/decisions.json

**`#/carried/0/from`**：aos-prep/kernel/decisions.json

---

**`#/carried/0/template_files`**（原文是字串陣列，2 行）

- template/workflows/decisions.md
- template/WORKFLOWS.md

**`#/carried/0/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/0/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；not_when 指到 knowledge 包 decide 工作流的那句改成「本庫沒有，需要就自建」

---

**`#/carried/1`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/1/here`**：wf/workflows/planning.json

**`#/carried/1/from`**：aos-prep/kernel/planning.json

---

**`#/carried/1/template_files`**（原文是字串陣列，3 行）

- template/workflows/planning.md
- template/WORKFLOWS.md
- flavors/dev/WORKFLOWS.dev.md

**`#/carried/1/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/1/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；指到 knowledge 包 plan-a-thing 的三處改成「本庫沒有對應的工作流，需要就自建」；拿掉「（dev 包）」

---

**`#/carried/2`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/2/here`**：wf/workflows/gotchas.json

**`#/carried/2/from`**：aos-prep/kernel/gotchas.json

---

**`#/carried/2/template_files`**（原文是字串陣列，2 行）

- template/workflows/common/gotchas.md
- template/WORKFLOWS.md

**`#/carried/2/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/2/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡

---

**`#/carried/3`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/3/here`**：wf/workflows/user.json

**`#/carried/3/from`**：aos-prep/kernel/user.json

---

**`#/carried/3/template_files`**（原文是字串陣列，3 行）

- template/workflows/common/user.md
- template/WORKFLOWS.md
- template/workflows/common/README.md

**`#/carried/3/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/3/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；「回覆風格：通用規則在 kernel/reply-style.json」那步改成只記這位使用者的回覆偏好（reply-style 沒落，W15＝B）

---

**`#/carried/4`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/4/here`**：wf/skeletons/decisions.json

**`#/carried/4/from`**：aos-prep/kernel/memory-decisions.json

**`#/carried/4/template_files`**（原文是字串陣列，1 行）：template/workflows/decisions.md

**`#/carried/4/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/4/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件；`records` 照備料是物件陣列（W18＝A）

---

**`#/carried/5`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/5/here`**：wf/skeletons/ideas.json

**`#/carried/5/from`**：aos-prep/kernel/memory-ideas.json

**`#/carried/5/template_files`**（原文是字串陣列，1 行）：template/workflows/planning.md

**`#/carried/5/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/5/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 的兩張表各從物件陣列改成以鍵名為鍵的物件

---

**`#/carried/6`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/6/here`**：wf/skeletons/gotchas.json

**`#/carried/6/from`**：aos-prep/kernel/memory-gotchas.json

**`#/carried/6/template_files`**（原文是字串陣列，1 行）：template/workflows/common/gotchas.md

**`#/carried/6/prep_commit`**：9eb8f20a6b5e35e5d278f06d30e9f5e0dab892c2

**`#/carried/6/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件

---

**`#/carried/7`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/7/here`**：wf/skeletons/user.json

**`#/carried/7/from`**：aos-prep/kernel/memory-user.json

---

**`#/carried/7/template_files`**（原文是字串陣列，2 行）

- template/workflows/common/user.md
- template/workflows/common/README.md

**`#/carried/7/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/7/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`fields` 從物件陣列改成以鍵名為鍵的物件；W15＝B：`defaults` 整段、`rules` 講 defaults 那條、skeleton 回覆風格那格的出廠句與 skeleton `_description` 的出廠預設說明都拿掉；`holds` 的「通用回覆規則」拿掉

---

**`#/carried/8`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/8/here`**：wf/knowledge/live-lists.json

**`#/carried/8/from`**：aos-prep/kernel/live-lists.json

---

**`#/carried/8/template_files`**（原文是字串陣列，4 行）

- template/SESSION-LOG.md
- template/WAIT_USER.md
- template/WORKFLOWS.md
- template/AGENTS.md

**`#/carried/8/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/8/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；`which` 第三列的信件軸改成「同樹走 mailbox、樹外照工作區自己的做法」（multi-agent 包不併，W21）；`aos_note` 改寫成使用者 W11 的裁定（現在不改，照寫檔案）；`which` 照備料是物件陣列（W18＝A）；11-18 使用者選項框「跟著改 (Recommended)」：兩份清單併成一份 `wf/progress.json`（兩軸：信、進度），`session_log`、`wait_user` 併成 `progress`，加 `skeleton`，`session_start`、`which`、`aos_note` 跟著改

---

**`#/carried/9`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/9/here`**：wf/knowledge/iron-rules.json

**`#/carried/9/from`**：aos-prep/kernel/iron-rules.json

---

**`#/carried/9/template_files`**（原文是字串陣列，2 行）

- template/AGENTS.md
- flavors/dev/AGENTS.dev.md

**`#/carried/9/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

**`#/carried/9/changed`**：路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；「裝了開發包」兩處改成不提包

---

**`#/carried/10`**（物件，5 個鍵：`here`、`from`、`template_files`、`prep_commit`、`changed`）

**`#/carried/10/here`**：wf/workflows/_description.json＋wf/workflows/_index.json

**`#/carried/10/from`**：aos-prep/kernel/dispatch.json

---

**`#/carried/10/template_files`**（原文是字串陣列，2 行）

- template/WORKFLOWS.md
- flavors/dev/WORKFLOWS.dev.md

**`#/carried/10/prep_commit`**：ef0b1412a86d62804daab7fd53eb7a0650bbc80d

---

**`#/carried/10/changed`**

路徑改成本庫落點（`kernel/…`、`dev/…` → `wf/workflows/`、`wf/skeletons/`、`wf/knowledge/`；「aos 知識庫的」幾個字拿掉）；`source` 鍵拿掉、收進這裡；不單獨成檔：`route`、`skip`、`fallback`、`live_state` 寫進 `wf/workflows/_description.json` 的「派發」一節，`kernel_triggers` 變成 `wf/workflows/_index.json` 各格的 description；heartbeat／multi-agent 包那句改成「本庫沒有，需要就自建」

---

**`#/not_carried`**（陣列，3 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/not_carried/i`）

| i | `what` | `why` |
|---|---|---|
| 0 | aos-prep/kernel/reply-style.json（回覆風格九條） | 使用者 2026-11-13 收工待裁頁 W15＝B：算個人偏好，不當通用知識節點落檔，只留在各工作區自己的 user 偏好 |
| 1 | aos-prep/kernel/_description.json、_index.json、prep-report*.json（五份） | 備料的說明與報告，不是節點；報告裡跟落檔有關的取捨記在這裡與搬遷紀錄 |
| 2 | 備料報告 for_user 第 3 題「條列走資料檔、導航留 md」要不要另立一條鐵律 | 備料本身已拿掉這條；W22＝A（JSON 是推薦、md 照樣可以）之後沒有人要求另立，沒加 |
