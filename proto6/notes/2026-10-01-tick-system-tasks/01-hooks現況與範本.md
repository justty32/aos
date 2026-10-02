← [2026-10-01：aos-tick 的系統級任務總整理（給 hooks 慢慢想用）](../2026-10-01-tick-system-tasks.md)（分檔 1/4）｜[下一份](02-git-mq-clean.md)

## 現在 hooks 能做什麼、限制在哪

正本：[B-635](../../spec/tick/hooks.md)。

**能做的：**

- 任務表頂層鍵 `hooks`，跟 `tasks` 同層，不是模組。
- 只開一個掛點 `after_all`：一串 inst，寫法比照 `tasks`（`id` 可省、吃頂層預設、同樣的 cwd 與環境變數）。
- 照表跑完之後跑，**被停格檔停下的那格也照跑**——這是它存在的理由。
- hook 看得到本格紀錄：~~這時紀錄已經收尾（`ended:true`）~~〔第十八批改：所有 hooks 跑完才收尾，hook 跑時還是 `ended:false`〕，有 `ran`、失敗清單 `tasks`、`stopped_after`，以及前面 hook 裡不是 0 的碼。

**限制：**

- **只有 `after_all`**。`before_all`、`before_task`、`after_task` 都沒開，寫了照收不理。所以「每格開頭」「每項前後」的事，現在只能當任務表上的一般項。
- **hook 不看停格檔**：hook 之間互不擋，hook 建停格檔也沒人理（下一格開頭刪掉）。所以 hook **擋不住任何東西**，也沒辦法「前一個 hook 失敗就不跑下一個」。
- **碼不影響 tick**：hook 回幾都只記進 `hooks.after_all`（0 不記），tick 照舊回 0。
- **擋板檔、拿不到鎖（busy）、表壞時一個都不跑**。
- ~~**紀錄在 hook 跑之前就寫成 `ended:true`**：hook 跑到一半 tick 被殺，下一格的 `last/` 看起來仍是「正常收尾」，看不出 hook 沒跑完；hooks 也不記 `ran`。~~ **已解決**（2026-10-01 第十八批：所有 hooks〔含 after_all〕跑完才寫 `ended:true`，跑 hook 時被殺，下一格的 `last/` 是 `ended:false`）。
- **hook 的 `AOS_TASK_INDEX` 從 0 數起，跟 `tasks` 的位置各算各的**：拿 index 當名字的東西（例如 `aos-git` 存檔點，plan 待問 2 的建議）會跟任務撞號。**已解決**（使用者 2026-10-01 第十批）：hook 改拿 `AOS_HOOK_POINT`／`AOS_HOOK_INDEX`／`AOS_HOOK_ID`，不再有 `AOS_TASK_INDEX`（[B-635](../../spec/tick/hooks.md)）；要用 index 當名字時，hook 跟任務的變數名本來就不同，自己加前綴（例如掛點名）即可。

## 怎麼讀每一項

每項固定五欄：**做什麼**／**原本的位置與機制**／**狀態與正本**／**現在已經不在的前提**／**放到 hooks 的想法（待使用者想）**。「範本位置」指 [B-629](../../spec/deferred/template.md) 的兩版範本。

## 一、標準任務表範本（B-629）

- **做什麼**：預設的一組系統級任務，夾著使用者任務。
- **原本的順序**：
  - 沒有 git：`mq-get` → 使用者任務 → `mq-post` → `clean`。
  - 有 git：`git-open` → `mq-get` → `mark-get` → 使用者任務 → `mark-user` → `clean` → `git-close` → `mq-post`。
  - 更早（第二十批原話）還有收件、投件、發摘要；發摘要 `summary` 10-01 拿掉。
- **機制**：全靠**陣列順序**給保證，例如「先提交再送」靠 `git-close` 排在 `mq-post` 前面，close 失敗建停格檔就擋住 `mq-post`。系統級任務標 `kind:"system"`，核心不看。
- **狀態**：待實作（[B-629](../../spec/deferred/template.md)）；plan 待問 11、12 還沒裁定，建議第二段版只剩 `git-open` → 使用者任務 → `mark-user` → `git-close`。
- **前提不在了**：`aos-mq` 要的通道在暫緩區；`clean` 沒東西可清；`kind` 沒人讀。
- **hooks 想法（待使用者想）**：範本可能拆成「`tasks` 放使用者任務＋必須被停格擋住的項」、「`hooks.after_all` 放停格後也要做的收尾」兩半。關鍵是每一項要不要被停格檔擋——**現在範本的保證大多靠「停格就不跑後面」，搬進 `after_all` 就失去這個擋法**，那一項得自己讀紀錄的 `stopped_after` 判斷。
