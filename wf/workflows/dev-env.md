# dev-env — 開發環境、指令、外部工具

← [WORKFLOWS](../WORKFLOWS.md)

這台機器上要能開發需要什麼、怎麼裝、跑什麼指令；外部工具與 env var 也收在這裡。要建的只有 `proto8/cpp/`（C／C++，在 proto8 跑 `python3 install.py`）；各專案的細節在 [proto8/cpp/README](../../proto8/cpp/README.md)，本檔是 agent 照著做的清單。

**何時用**：fresh clone、換機器、裝不起來、忘了指令、要加一個外部工具或環境變數。
**何時不用**：驗證／測試怎麼跑 → [testing](testing.md)；程式碼慣例 → [common/conventions](common/conventions.md)。

## Done when

- 照「流程」走完，[testing「proto8」](testing.md#proto8)的建置指令（`python3 install.py`）回傳 0，`proto8/bin/` 底下有 9 支 C++ 執行檔。
- 要使用者親自做的（帳號、授權、金鑰）各寄一封到使用者專區（`aos-user send`，見 [common/user.md](common/user.md)；進度記在 [progress.json](../progress.json)、標「等使用者」）。

## 流程（fresh clone 後）

1. **相依**：在 proto8 跑 `python3 install.py --check`（Python ≥ 3.11、只用標準庫）：必需 g++ ≥ 10、gcc、make、ar，缺了退 1；選配工具（git、tmux、bwrap、s6…）只列表、不擋。11-17 起不用 CMake、vcpkg（nlohmann json 是收進 repo 的單檔 `proto8/cpp/third_party/nlohmann/json.hpp`）。Python 選用模組清單在 `proto8/py/requirements-optional.txt`（現在只有 jsonschema；install.py 只檢查、不 pip）。
2. 在 proto8 跑 `python3 install.py` 建一次（見 [testing「proto8」](testing.md#proto8)）：填 `proto8/bin/`（9 支 C++ 執行檔＋19 支 Python 指令入口）、`proto8/lib/`（`py/` 的抄本＋C++ 函式庫）與 `proto8/include/`，都不進 git。**執行期只認這三夾**：改了 `py/` 或 `cpp/` 要重跑 `install.py` 才生效（11-18 S3 起；不再「存檔即生效」）。
3. 一台設一次 `export AOS_HOME=<這份 proto8 的絕對路徑>`（寫進 `~/.bashrc`；`install.py` 最後一行會印），之後每個視窗先 `source $AOS_HOME/env.sh`（或在樹裡 `source env.sh`，那份轉去家裡這份）把指令放進 PATH（見下表）。殼設定檔的完整寫法（`AOS_DAEMON`、`AOS_LLM_KERNEL` 要寫在 `source env.sh` 後面）、起 llm kernel 與 `.stack` 的根，照[每台設定說明書](dev-env/03-換機.md)，這裡不重寫。
4. 內容 json 的 diff：跑一次 `python3 wf/tools/json_text.py --setup`（Windows 可能叫 `python`；重跑無妨，`--setup --check` 只看；`--help`／`--setup` 由同夾的 `json_text_cli.py` 做，抄到別的 repo 要兩支一起抄）——在這個 clone 的 `.git/config` 設 `diff.json_text.textconv`，`git diff`／`show`／`log -p` 碰到 `.gitattributes` 點名的知識庫與 `_index.json`／`_description.json` 就展開成逐行文字再比；沒設照原檔比。`--stat`／`--numstat`／`--shortstat` 不吃這個設定，數的是原檔的行（要看展開後改了幾行就數 `git diff` 本身的 +／- 行）。`git blame` 預設也吃這個設定（要原檔行號加 `--no-textconv`）；要做成 patch 給 `git apply` 用時加 `--no-textconv` 或用 `format-patch`。

## 指令表

| 做什麼 | 指令 | 備註 |
|--------|------|------|
| 建 proto8 的 C++ 實作 | 在 proto8 跑 `python3 install.py`（`--check` 只查相依；見 [testing「proto8」](testing.md#proto8)） | proto8 的 aos-exec／loop／fsm／daemon 只有 C++ 版，手跑前要先建；重跑＝全新安裝，C++ 沒改時幾秒；log 在 `proto8/cpp/build/build.log`；開發時只重編一支：`make -C proto8/cpp -j8 BINDIR=$AOS_HOME/bin aos-exec`；重運算，派給隊員時 `nice -n 19`（見 [resources](resources.md)）|
| 把 proto8 的指令放進 PATH | 一台設一次 `export AOS_HOME=…`，每個視窗 `source $AOS_HOME/env.sh`（11-18 S6 分工：`AOS_HOME` 是人設的，`env.sh` 不設它、沒設就一行 `EnvBad` 什麼都不改；清掉 `AOS_HOME` 以外的 `AOS_*`、把 `$AOS_HOME/bin` 放 PATH 第一、`frontend/bin`（選配的網頁外掛，夾在才放）第二，不往 `~/.local/bin` 放東西；`aos-exec` 不在時提示 `python3 $AOS_HOME/install.py`）。樹裡的 `env.sh`（起手範本 `templates/starts/start-api`、`start-eca` 帶的薄的那份）只是轉去這份 | 不再寫 Python user site 的 `aos-proto8.pth`（使用者 11-15 對自編規則盤點的裁定「6.拿掉。」；家機那份已搬到 `~/.aos/saves/pth-removed-1115/`）；Python 指令的入口自己把 `lib/` 放上路徑，抄出 repo 的程式要 import 共用模組就設 `AOS_HOME`（共用模組只經 `$AOS_HOME/lib` 找，沒設報 `HomeMissing`）。舊的 `cmd/install.sh`（連進 `~/.local/bin`）11-18 S5 收掉（題 X-4 A），`~/.local/bin` 裡以前連的 `aos-*` 要自己拿掉。開一棵新樹：`cp -r $AOS_HOME/templates/starts/start-api 目的資料夾`（或 `start-eca`）；開新 agent：`cp -r $AOS_HOME/templates/名 目的資料夾`（範本都寫 `{"$env": "AOS_HOME", …}`，每台設一次 `AOS_HOME`；[templates/docs/02](../../proto8/templates/docs/02-agent-fsm.md)） |
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

**Windows 機**：使用者在 Windows 機（`C:\code\mine\simple_tools\aos`）工作時，這台有 WSL Ubuntu，實跑（build、proto8 的程式與試驗場）都在 WSL 那邊做（使用者 10-28：「這台有wsl ubuntu，可能之後都要在那邊做處理」）。WSL 裡的 clone 是 `~/repo/aos`（11-13 起唯一一份；`AOS_HOME` 指它的 `proto8`；樹 11-23 起住 `~/repo/aos/.stack`，被 git 忽略、每台各有各的，見[每台設定說明書](dev-env/03-換機.md)）。**不要在 `/mnt/c` 底下跑**：那裡每個檔都帶 `+x`，aos-exec 會把 JSON 當可執行檔（N-61）。從 Windows 端經 `\\wsl.localhost\Ubuntu\…` 改檔會把 `+x` 弄掉，改完要在 WSL `chmod +x`。

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-跨機與外部工具](dev-env/01-跨機與外部工具.md) | 跨機 / 離線差異；外部工具與 env var |
| [02-模型端點](dev-env/02-模型端點.md) | 模型端點（2026-09-25 定，10-10 核對） |
| [03-換機](dev-env/03-換機.md) | 每台怎麼設、怎麼起樹（11-22，11-23 改成 stack 不跟著機器搬）：每台要有什麼、`.zshrc`／`.bashrc` 怎麼寫、起 llm kernel 與 `.stack` 的根、核對、常見錯誤 |

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [wf/public 坑的主題表](../public/README.md#主題)。
