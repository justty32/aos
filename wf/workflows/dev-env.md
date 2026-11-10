# dev-env — 開發環境、指令、外部工具

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

這台機器上要能開發需要什麼、怎麼裝、跑什麼指令；外部工具與 env var 也收在這裡。要建的只有 `proto8/impls/`（C／C++）；各專案的細節在 [proto8/impls/README](../../proto8/impls/README.md)，本檔是 agent 照著做的清單。

**何時用**：fresh clone、換機器、裝不起來、忘了指令、要加一個外部工具或環境變數。
**何時不用**：驗證／測試怎麼跑 → [testing](testing.md)；程式碼慣例 → [common/conventions](common/conventions.md)。

## Done when

- 照「流程」走完，[testing「proto8」](testing.md#proto8)的建置指令回傳 0，`proto8/impls/*/bin/` 底下有各專案的執行檔。
- 要使用者親自做的（帳號、授權、金鑰）在 [WAIT_USER](../WAIT_USER.md) 各佔一行。

## 流程（fresh clone 後）

1. **vcpkg**：本機裝在 `~/dev/vcpkg`，`proto8/impls/cmake/settings.cmake` 會自動找到，不用設 `VCPKG_ROOT`；要用別的路徑就設 `VCPKG_ROOT` 環境變數（或 configure 時給 `-DCMAKE_TOOLCHAIN_FILE`）。`git clone --depth 1` 的 vcpkg 會缺各專案 `vcpkg.json` 指定的 baseline commit，要 `git fetch --depth 1 origin <sha>` 補，不必 unshallow。
2. 照 [testing「proto8」](testing.md#proto8)把 `proto8/impls/` 建一次（repo 根沒有 CMake：08～09 月那一代 11-05 封存在 `archive/aos-v1/`）。
3. `proto8/install.sh` 把指令放進 PATH（見下表）。

## 指令表

| 做什麼 | 指令 | 備註 |
|--------|------|------|
| 建 proto8 的 C++ 實作 | 照 [testing「proto8」](testing.md#proto8)，在 `proto8/impls/` 建 | 10-23 起 proto8 的 aos-exec／loop／fsm／daemon 只有 C++ 版，手跑前要先建；各專案獨立 CMake、也能單獨 `cd <專案> && cmake -B build && cmake --build build`；重運算，派給隊員時 `nice -n 19`（見 [resources](resources.md)）|
| 把 proto8 的指令放進 PATH | `proto8/install.sh`（WSL clone 裡跑；預設 symlink 進 `~/.local/bin`，給參數換目的地、`--dry-run` 只印、`--uninstall` 拿掉）| 11-06 晚 K-5：也在 Python user site 寫 `aos-proto8.pth`，兩行為本 repo `proto8/py`／`proto8/lib` 絕對路徑；`--dry-run` 不寫、`--uninstall` 只刪內容完全相符的本 repo 那份；user site 不可用只 warning、其餘照裝，可改給 `PYTHONPATH`。impls 先建好；冪等、同名的別的東西不蓋；repo 換位置要重跑。11-10 起也連 `templates/copy-out`（開新 agent：`copy-out [範本] 目的資料夾`，把範本抄出 repo、指回 proto8 的路徑照 `--proto8 env|relative|absolute` 改寫（預設 env＝每台設一次 `AOS_HOME`），[templates/docs/02](../../proto8/templates/docs/02-agent-fsm.md)）。之後不用每殼 source env.sh 設 PATH |
| 文檔檢查 | `bash wf/tools/wf-lint.sh --strict wf .claude/commands` | 可選，預設不跑；或 `/wf-lint`；從 repo 根跑 `.` 會被 `.claude/worktrees/` 的副本淹掉 |

驗證與測試指令不列這裡——連同「誰跑」一起在 [testing](testing.md)。

## git 佈局：aos 是 submodule；worktree 隔離可以開

aos 是 `simple_tools` 的 submodule：`aos/.git` 是指標檔，真正的 gitdir 在 `../.git/modules/aos`。

**背景**：2026-09-02 一個 worktree session 收尾清理時把那個 gitdir 清空，四個未 push 的 commit 物件遺失，
只能從 GitHub 重 clone、拿工作樹重建（重建後是 `af49170`、`b19f1d8`）。之後一度禁止在本 repo 開 worktree 隔離。

**現在的規則**〔使用者方向 2026-09-30 晚〕：派出去的隊**可以**開 worktree 隔離（`isolation: worktree`／EnterWorktree），但要照下面三條防範：

- **開工**：worktree 起點可能很舊，第一步 `git reset --hard main`（見 [dispatch lessons](dispatch/lessons.md) 第 6 節）。
- **收尾**：隊員 `git rebase main`，確保能 fast-forward；**不准自己刪 worktree 或分支**。
- **清理**：由頂層在主 repo ff-merge 成功後才清：`git worktree remove <路徑>`＋`git branch -d <分支>`。

做完的 commit 仍盡早 push，本機 gitdir 不算可靠。

## 跨機、外部工具、模型端點

**10-28 起換到 Windows 機**：使用者在 Windows 機（`C:\code\mine\simple_toolsos`）工作，這台有 WSL Ubuntu，之後實跑（build、proto8 的程式與試驗場）都在 WSL 那邊做（使用者 10-28：「這台有wsl ubuntu，可能之後都要在那邊做處理」）。WSL 裡的 clone：hub 隊在 `~/repo/simple_tools/aos`，aos-tools 隊另開 `~/repo/aos-tools`（同一個 GitHub repo，避免兩隊在同一份工作樹打架；各自建 impls）。**不要在 `/mnt/c` 底下跑**：那裡每個檔都帶 `+x`，aos-exec 會把 JSON 當可執行檔（N-61）。從 Windows 端經 `\\wsl.localhost\Ubuntu\…` 改檔會把 `+x` 弄掉，改完要在 WSL `chmod +x`。

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-跨機與外部工具](dev-env/01-跨機與外部工具.md) | 跨機 / 離線差異；外部工具與 env var |
| [02-模型端點](dev-env/02-模型端點.md) | 模型端點（2026-09-25 定，10-10 核對） |

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
