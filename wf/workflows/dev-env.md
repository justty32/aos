# dev-env — 開發環境、指令、外部工具

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

這台機器上要能開發需要什麼、怎麼裝、跑什麼指令；外部工具與 env var 也收在這裡。要建的只有 `proto8/impls/`（C／C++）；各專案的細節在 [proto8/impls/README](../../proto8/impls/README.md)，本檔是 agent 照著做的清單。

**何時用**：fresh clone、換機器、裝不起來、忘了指令、要加一個外部工具或環境變數。
**何時不用**：驗證／測試怎麼跑 → [testing](testing.md)；程式碼慣例 → [common/conventions](common/conventions.md)。

## Done when

- 照「流程」走完，[testing「proto8」](testing.md#proto8)的建置指令回傳 0，`proto8/impls/*/bin/` 底下有各專案的執行檔。
- 要使用者親自做的（帳號、授權、金鑰）各寄一封到使用者專區（`aos-user send`，見 [common/user.md](common/user.md)；舊條目在 [WAIT_USER](../WAIT_USER.md)）。

## 流程（fresh clone 後）

1. **vcpkg**：本機裝在 `~/dev/vcpkg`，`proto8/impls/cmake/settings.cmake` 會自動找到，不用設 `VCPKG_ROOT`；要用別的路徑就設 `VCPKG_ROOT` 環境變數（或 configure 時給 `-DCMAKE_TOOLCHAIN_FILE`）。`git clone --depth 1` 的 vcpkg 會缺各專案 `vcpkg.json` 指定的 baseline commit，要 `git fetch --depth 1 origin <sha>` 補，不必 unshallow。
2. 照 [testing「proto8」](testing.md#proto8)把 `proto8/impls/` 建一次（repo 根沒有 CMake）。
3. 每個視窗先 `source proto8/env.sh` 把指令放進 PATH（見下表；想連進 `~/.local/bin` 才跑選配的 `proto8/cmd/install.sh`）。
4. 內容 json 的 diff：跑一次 `python3 wf/tools/json_text.py --setup`（Windows 可能叫 `python`；重跑無妨，`--setup --check` 只看；`--help`／`--setup` 由同夾的 `json_text_cli.py` 做，抄到別的 repo 要兩支一起抄）——在這個 clone 的 `.git/config` 設 `diff.json_text.textconv`，`git diff`／`show`／`log -p` 碰到 `.gitattributes` 點名的知識庫與 `_index.json`／`_description.json` 就展開成逐行文字再比；沒設照原檔比。`--stat`／`--numstat`／`--shortstat` 不吃這個設定，數的是原檔的行（要看展開後改了幾行就數 `git diff` 本身的 +／- 行）。`git blame` 預設也吃這個設定（要原檔行號加 `--no-textconv`）；要做成 patch 給 `git apply` 用時加 `--no-textconv` 或用 `format-patch`。

## 指令表

| 做什麼 | 指令 | 備註 |
|--------|------|------|
| 建 proto8 的 C++ 實作 | 照 [testing「proto8」](testing.md#proto8)，在 `proto8/impls/` 建 | proto8 的 aos-exec／loop／fsm／daemon 只有 C++ 版，手跑前要先建；各專案獨立 CMake、也能單獨 `cd <專案> && cmake -B build && cmake --build build`；重運算，派給隊員時 `nice -n 19`（見 [resources](resources.md)）|
| 把 proto8 的指令放進 PATH | `source proto8/env.sh`（11-17 新：每個視窗先 source；清掉 `AOS_*`、設 `AOS_HOME`＝那個 proto8、把它的 `cmd/*/bin`、`impls/*/bin` 放到 PATH 最前，不往 `~/.local/bin` 放東西）。選配：`proto8/cmd/install.sh`（WSL clone 裡跑；預設 symlink 進 `~/.local/bin`，給參數換目的地、`--dry-run` 只印、`--uninstall` 拿掉）| 不再寫 Python user site 的 `aos-proto8.pth`（使用者 11-15 對自編規則盤點的裁定「6.拿掉。」；家機那份已搬到 `~/.aos/saves/pth-removed-1115/`）；抄出 repo 的程式要 import 共用模組就設 `AOS_HOME`（共用模組只經 `$AOS_HOME/lib` 找，沒設報 `HomeMissing`）；還有舊的 `.pth` 時印 warning，舊的要自己移走，`--uninstall` 只拿掉連結、不碰它。impls 先建好；冪等、同名的別的東西不蓋；repo 換位置要重跑（指選配的 install.sh）。開新 agent 不用指令：`cp -r $AOS_HOME/templates/名 目的資料夾`（範本都寫 `{"$env": "AOS_HOME", …}`，每台設一次 `AOS_HOME`；[templates/docs/02](../../proto8/templates/docs/02-agent-fsm.md)）。用 `source proto8/env.sh` 就不用 install.sh |
| 查 md 連結／錨點 | `python3 wf/tools/check_anchors.py` | 想查才跑（大量搬檔後）；不是 commit 前必跑（使用者 11-13 晚，見 [user](common/user.md)）|
| 查 `_index.json` 跟樹對不對得上 | `python3 wf/tools/index_check.py` | 同上，想查才跑；生成器 `index_gen.py --apply` 由 `commit-request` 排隊跑，自己不用跑（鐵律 3，11-14 改）|

驗證與測試指令不列這裡——連同「誰跑」一起在 [testing](testing.md)。

## git 佈局：aos 是獨立 repo；只有一個 `main`、不開 worktree 分支

兩台的工作 repo 都是獨立 clone 的 `~/repo/aos`（自己的 `.git` 資料夾，origin `github.com:justty32/aos`）。家機以前用的 `~/repo/simple_tools/aos`（`simple_tools` 的 submodule，`.git` 是指標檔）11-13 晚起不再是工作 repo，還留在磁碟上（使用者「不用刪」），別在那裡改。

**規則**（使用者 2026-11-03 晚，原話在 [common/user.md](common/user.md)「分支慣例」那格）：**本地與遠端都只有一個 `main`**。所有線直接在 `~/repo/aos` 這一棵工作樹的 `main` 上做，不開分支、不開 worktree 分支（派子 agent 時不用 `isolation: worktree`／EnterWorktree），不 push 別的分支。

- **多條線同時改同一棵工作樹**：靠 `commit-request claim` 先宣告自己在改哪些檔，不靠 worktree 隔開；交件也走 `wf/tools/commit-request`（鐵律 3，用法見 [dispatch/aos-teams](dispatch/aos-teams.md)「1. commit」）。
- **不准自己刪 worktree 或分支**：真的看到有殘留的，回報、不自己清（worktree 收尾清理清空過當時 submodule 的 gitdir、丟掉未 push 的 commit）。
- **push 由頂層在使用者點頭後做**（鐵律 2；授權怎麼問見 [user/01「push 授權」](common/user/01-說話授權與記憶.md)），各線不 push。還沒 push 的 commit 只存在本機，本機 gitdir 不算可靠。

## 跨機、外部工具、模型端點

**Windows 機**：使用者在 Windows 機（`C:\code\mine\simple_tools\aos`）工作時，這台有 WSL Ubuntu，實跑（build、proto8 的程式與試驗場）都在 WSL 那邊做（使用者 10-28：「這台有wsl ubuntu，可能之後都要在那邊做處理」）。WSL 裡的 clone 是 `~/repo/aos`（11-13 起唯一一份；選配的 `proto8/cmd/install.sh` 的連結指它，樹住 `~/aos-home`）。**不要在 `/mnt/c` 底下跑**：那裡每個檔都帶 `+x`，aos-exec 會把 JSON 當可執行檔（N-61）。從 Windows 端經 `\\wsl.localhost\Ubuntu\…` 改檔會把 `+x` 弄掉，改完要在 WSL `chmod +x`。

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-跨機與外部工具](dev-env/01-跨機與外部工具.md) | 跨機 / 離線差異；外部工具與 env var |
| [02-模型端點](dev-env/02-模型端點.md) | 模型端點（2026-09-25 定，10-10 核對） |

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
