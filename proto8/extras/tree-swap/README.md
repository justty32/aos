# tree-swap：停樹後把一棵樹的程式複本與 C++ 執行檔換成某個 commit 的版本

← [extras](../README.md)｜規格：[aos-teams/06「停樹換檔的做法」](../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)｜11-13 晚預演與給使用者的單子：[tree-swap-1113](../../thinking/2026-11/13/tree-swap-1113.md)

三支 bash，**都不含 kill／shutdown**；停樹、起樹由使用者自己下。每段動手前先確認這棵樹沒有任何行程活著，有就印出那些行程、`RED:` 退 3、什麼都不改。

| 檔 | 做什麼 |
|---|---|
| [build.sh](build.sh) | `--ref <commit>`：`git archive` 該 commit 到 repo 外（預設 `~/code/swap-1113/src`），編十支 C++，寫 `BUILD_REF` |
| [swap.sh](swap.sh) | `--ref <commit> all`＝六段：`check`（樹停了？build 的 impls 跟 ref 同？樹裡有沒有「只在樹裡有」的檔會被丟掉？）→`backup`→`copy`（解到旁邊、兩次改名換上）→`stamp`（用該 commit 的 [copy_tree.py](../aos-home/copy_tree.py) `--stamp-only` 寫每夾的 `.aos-source.json`）→`bin`（十支各自 `cp` 到旁邊再 `mv`）→`verify` |
| [rollback.sh](rollback.sh) | 還原最近一次（或 `--backup <夾>`）的備份，`all`／`tree`／`bin`；還原後逐檔比對 |
| [common.sh](common.sh) | 預設路徑、「樹在跑」偵測、計時 |

- **換什麼**：樹裡已經有的 `lib templates knowledge py kernel`（沒有的夾不建），與 `$TS_BIN_ROOT/<p>/bin/<p>` 十支（`aos-daemon directive exec fsm json llm llm-kernel lock loop post`；`~/.local/bin/aos-*` 指的就是 repo 的 `proto8/impls/<p>/bin/<p>`，gitignore 著）。
- **不碰**：`agents defs teams kernels ws root daemon .stack env.sh`、`~/.aos`。
- **「樹在跑」怎麼算**：自己的行程裡，環境的 `AOS_STACK`／`AOS_DAEMON` 落在樹底下，或 cwd 在樹底下且是 aos／claude／python／node。不看 `AOS_HOME`（`.zshrc` 每個殼都設）。從某隻 agent 的殼裡下（殼裡有 `AOS_STACK` 等）直接拒絕。
- **路徑**用環境變數改：`TS_TREE`（預設 `~/aos-home`）、`TS_REPO`、`TS_BUILD`、`TS_BIN_ROOT`、`TS_BACKUP_ROOT`（預設 `~/aos-saves/tree-swap`，`LAST` 記最近一份）。
- 換完之後 repo 的 `impls/*/build` 比執行檔舊；之後在 repo 重 build 會從已 commit 的原始碼編出等價的檔。
