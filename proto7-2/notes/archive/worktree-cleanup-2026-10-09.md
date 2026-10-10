> 封存 2026-10-10：10-09 r4 的一次性 worktree 清單，頂層已照清單刪掉已合進 main 的 51 個（見 decisions-2026-10-09 r4 段）；清單內容已過時。

# worktree 清單（2026-10-09 r4 波 0，I5）

← [r4 計畫](plan-2026-10-09-r4.md) §1 第 5 條、§5「worktree」｜[代定清單](decisions-2026-10-09.md)

目的：`../aos-wt/` 底下 58 個 worktree（加主 checkout 共 59）與 64 條本機分支逐列判「已在 main 嗎」，給頂層照刪。I5 **只列不刪**；刪 worktree／分支由頂層做，`apprentice/*` 與 `_check_main` 等使用者。

已抽到 [worktree-cleanup-2026-10-09.json](worktree-cleanup-2026-10-09.json)（64 列，一列一條分支）。

## 欄位

- `worktree`：相對 `simple_tools/` 的位置；空＝這條分支沒有 worktree。
- `branch`：分支名。
- `in_main`：`git merge-base --is-ancestor <分支> main` 的結果（yes／no），在 main `fd4d1e34`（MC 已 ff 進 main）上判。
- `ahead_of_main`：`git rev-list --count main..<分支>`，main 沒有的 commit 數。
- `untracked`：worktree 裡未追蹤的東西（都是隊伍當時的任務書／報告暫存夾）；有的話 `cmd` 帶 `--force`。
- `action`：建議動作。
- `cmd`：在 repo 根（`simple_tools/aos`，HEAD＝main）照跑的指令；空＝不動。

## 統計

| 建議 | 件數 | 是哪些 |
|---|---|---|
| 刪（已在 main，ahead 0） | 57 | loop7 全 22、loop8 全 12、loop9 全 10、loop10 全 13（mc 已 ff 進 main） |
| 留 | 1 | `loop11/FL`（本輪 FL 隊現役，目前 ahead 0，交件後再刪） |
| 等使用者 | 6 | `apprentice/*` 五條（各 ahead 1、未在 main，無 worktree；刪要 `-D`，不可逆）、`_check_main`（已在 main，無 worktree） |
| 不在本輪範圍、不動 | 2 | `roadmap-run`（ahead 46、未在 main、已凍結）、`main-ref`（已在 main，舊參照） |

- 57 條裡 6 個 worktree 有未追蹤暫存夾（B `.loop7/`、K1 `.k1/`、K4 `.k4/`、M `.mteam/`、S `.codex-S/`、A4 `.a4/`），沒有 `--force` 會被 git 拒；刪前要留哪份報告先搬出來。
- `git branch -d` 只刪已合進 HEAD 的分支，所以要在 HEAD＝main 的主 checkout 跑；跑完補 `git worktree prune`。
- `aos-wt/M/.mteam` 目前還有一個早先 session 留下的閒置 shell 停在裡面（`ps` 可見），刪 M 不影響它，但該 shell 之後會在不存在的目錄裡。
- 照跑的方式：逐列取 `cmd` 非空且 `action` 是「刪」的那 57 列；查法見工作流的資料檔說明。
