# dev-env — 開發環境、指令、外部工具

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

這台機器上要能開發需要什麼、怎麼裝、跑什麼指令；外部工具與 env var 也收在這裡。給人讀的完整版在 [`docs/build.md`](../../docs/build.md)，本檔是 agent 照著做的清單。

**何時用**：fresh clone、換機器、裝不起來、忘了指令、要加一個外部工具或環境變數。
**何時不用**：驗證／測試怎麼跑 → [testing](testing.md)；程式碼慣例 → [common/conventions](common/conventions.md)。

## Done when

- 照「流程」走完，`cmake --build --preset default` 回傳 0，`build/bin/aos` 存在。
- 要使用者親自做的（帳號、授權、金鑰）在 [WAIT_USER](../WAIT_USER.md) 各佔一行。

## 流程（fresh clone 後）

1. **vcpkg**：本機裝在 `~/dev/vcpkg`，根 `CMakeLists.txt` 會自動找到，不用設 `VCPKG_ROOT`。要用別的路徑就設 `VCPKG_ROOT` 環境變數，或把個人 preset 放 `CMakeUserPresets.json`（已 `.gitignore`）。`git clone --depth 1` 的 vcpkg 會缺 `vcpkg.json` 指定的 baseline commit，要 `git fetch --depth 1 origin <sha>` 補，不必 unshallow。
2. `cmake --preset default`（第一次、或 `CMakeLists.txt`／`vcpkg.json` 變動後重跑）。**只能從 repo 根目錄**，子專案不可單獨 configure。
3. `cmake --build --preset default`，接著照 [testing](testing.md) 跑 ctest 確認全綠。

## 指令表

| 做什麼 | 指令 | 備註 |
|--------|------|------|
| configure | `cmake --preset default` | preset：`default`（`build/`）、`release`（`build/release/`）、`merged`（`build/merged/`，多產一顆合併的 `libaos.so`）|
| build | `cmake --build --preset default` | 重運算，派給隊員時 `nice -n 19`（見 [resources](resources.md)）|
| 跑起來 | `build/bin/aos <子命令>` | 執行檔與各測試都在 `build/bin/` |
| 關掉擴充建一次 | `cmake -S . -B /tmp/aos-nomod -DAOS_BUILD_MODULES=OFF && cmake --build /tmp/aos-nomod` | 動過 `modules/` 之後 |
| 文檔檢查 | `bash wf/tools/wf-lint.sh --strict wf .claude/commands` | 或 `/wf-lint`；從 repo 根跑 `.` 會被 `.claude/worktrees/` 的副本淹掉 |

驗證與測試指令不列這裡——連同「誰跑」一起在 [testing](testing.md)。

## git 佈局：aos 是 submodule；worktree 隔離可以開

aos 是 `simple_tools` 的 submodule：`aos/.git` 是指標檔，真正的 gitdir 在 `../.git/modules/aos`。

**背景**：2026-09-02 一個 worktree session 收尾清理時把那個 gitdir 清空，四個未 push 的 commit 物件遺失，
只能從 GitHub 重 clone、拿工作樹重建（重建後是 `9bd31c0`、`e292b83`）。之後一度禁止在本 repo 開 worktree 隔離。

**現在的規則**〔使用者方向 2026-09-30 晚〕：派出去的隊**可以**開 worktree 隔離（`isolation: worktree`／EnterWorktree），但要照下面三條防範：

- **開工**：worktree 起點可能很舊，第一步 `git reset --hard main`（見 [dispatch lessons](dispatch/lessons.md) 第 6 節）。
- **收尾**：隊員 `git rebase main`，確保能 fast-forward；**不准自己刪 worktree 或分支**。
- **清理**：由頂層在主 repo ff-merge 成功後才清：`git worktree remove <路徑>`＋`git branch -d <分支>`。

做完的 commit 仍盡早 push，本機 gitdir 不算可靠。

## 跨機、外部工具、模型端點

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-跨機與外部工具](dev-env/01-跨機與外部工具.md) | 跨機 / 離線差異；外部工具與 env var |
| [02-模型端點](dev-env/02-模型端點.md) | 模型端點（2026-09-25 定，10-10 核對） |

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
