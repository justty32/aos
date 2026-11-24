# testing — 驗證（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)

改完怎麼確認沒壞。**沒有統一的自動測試**：使用者「感覺proto8/test已經成為我們的負擔了，能夠精簡嗎？我希望能大刪特刪」「激進版，不用說，甚至我希望整個刪掉也OK。」「ctest也可以刪掉吧」「這個鐵律刪掉，不用ctest」——不設 ctest、沒有整批的 `proto8/tests`（盤點：[thinking 11-04 tests-trim](../../proto8/thinking/2026-11/04/tests-trim.md)）。統一必跑的只有「**build 得過**」；各處有一些定向測試，改到哪就挑那處既有的定向測試跑（[prefix-fixes 坑-55](../../proto8/thinking/2026-11/04/tests-trim.md)）；其餘行為對不對靠手跑。

**何時用**：改完程式要確認沒壞、重構前要記基準。
**何時不用**：環境還沒裝好、不知道指令哪來 → [dev-env](dev-env.md)；build 紅了要查成因 → 只讀直接查、筆記寫進當天的 proto8/thinking（舊的 investigation 工作流 11-17 已封存）。

## Done when

- 下表標「改完必跑」的指令回傳 0。
- 「誰跑」是使用者的列，已各寄一封到使用者專區（`aos-user send`，見 [common/user.md](common/user.md)；進度記在 [progress.json](../progress.json)、標「等使用者」）（寫明跑什麼、什麼算過）。

## 驗證表

| 驗證 | 指令 | 誰跑 |
|------|------|------|
| **proto8 cpp（改完必跑）** | 見下面「proto8」 | agent |
| 要真模型、外部 CLI agent、跨機的 | 照該實驗檔的步驟 | 使用者 → 新題寄使用者專區（`aos-user send`），進度記在 [progress.json](../progress.json)、標「等使用者」；本機 LM Studio 跑得動的部分我自己跑 |

「誰跑」只有兩種值：**agent**（本機跑得動）、**使用者**（要實機、外部服務、帳號、付費、目視；新題寄使用者專區 `aos-user send`，進度記在 `wf/progress.json`、標「等使用者」）。判不準就當後者。

<a id="proto8"></a>
<a id="proto8不在-ctest-裡"></a>

## proto8

要建的只有 `proto8/cpp/`，11-17 起不用 CMake、vcpkg：在 proto8 跑 install.py，它先查相依、再用頂層 `cpp/Makefile` 編全家，清空再填 `proto8/bin/`（9 支執行檔）與 `proto8/include/`（`bin/`、`include/`、`cpp/build/` 不進 git；log 在 `cpp/build/build.log`；細節見 cpp/docs/04）：

```sh
(cd proto8 && python3 install.py)
```

開發時只重編一支：`make -C proto8/cpp -j8 BINDIR=$AOS_HOME/bin aos-exec`（或直接重跑 install.py，C++ 沒改時幾秒）。

- **跑測試前**：測試跑的是安裝產物（`bin/`、`lib/`），先在要測的那份 proto8 跑過 `python3 install.py`（改了 `py/` 或 `cpp/` 都要重跑才生效；11-18 S3 起沒有「存檔即生效」）；很多 Python 測試靠 PATH 上有指令，先 `export AOS_HOME=<那份 proto8> && source $AOS_HOME/env.sh`（在 bash 裡；11-18 S6 起 `env.sh` 不替你設 `AOS_HOME`，沒設報 `EnvBad`）。乾淨複本（`git archive`）不帶 `bin/ lib/ include/`，要在複本的 proto8 自己跑一次 install.py。
- **每個要跑測試的殼，先 `source "$AOS_HOME/env.sh"`**：下面每條指令都假設已經做過；沒做會冒一堆 `No such file or directory: 'aos-exec'`，看起來像程式壞了、其實是 PATH 上沒有 `bin/`（[重建步驟單「要知道的」](../../proto8/thinking/2026-11/17/重建步驟單.md#要知道的)）。
- **測試夾在哪、怎麼跑**：共用模組與 install 的測試在 `proto8/py/tests/`（`python3 -m unittest discover -s proto8/py/tests`）；指令的測試在 `proto8/py/tests/apps/<名>/`，**不是套件、要逐夾跑**（`for d in proto8/py/tests/apps/*/; do python3 -m unittest discover -s "$d" -t "$d"; done`）；工具的測試在各工具夾的 `tests/`（`proto8/py/tools/…/<工具>/tests`）；C++ 的在 `proto8/cpp/<專案>/tests`；範本的在 `proto8/templates/tests/`（子夾名有 `-`，逐夾跑）。
- **frontend 測試**：走 `proto8/frontend/tests/run.sh`（它要求環境沒有 `AOS_*`）。`test_slash` 把暫存夾寫死成 `~/.aos/scratch/ok-pano-b`，夾不在會有 28 個 FileNotFoundError；先設 `VIEW_TEST_TMP=<自己的暫存夾>` 再跑就全綠（50 支、跳過 7 支）。
- **`wf/tools/tests`**：`python3 -m unittest` 跑 53 支。`test_commit_queue.sh` 不在 unittest 裡，另外跑：`bash wf/tools/tests/test_commit_queue.sh <來源 repo> <暫存夾>`；要有當天的 `proto8/thinking/<年-月>/<日>/README.md`（沒有就 SKIP、退 1），git 身分要寫在 `.gitconfig`（它不吃 `GIT_AUTHOR_*` 環境變數）。
- **`check.py` 腳本**：`templates/tests/image-move-check`、`templates/kernels/tests/kernel-chain-check` 不是 unittest，discover 會顯示 0 支；直接跑 `python3 proto8/templates/tests/image-move-check/check.py`、`python3 proto8/templates/kernels/tests/kernel-chain-check/check.py`（成功退 0；用已裝的 aos 指令，不 build、不安裝）。

Python 的原始碼在 `proto8/py/`（套件 `py/aos/`、指令本體 `py/aos/apps/<名>/`、工具 `py/tools/{base,aos,agent}/`；11-18 S3～S5 從 `lib/`、`cmd/` 搬來），`install.py` 把它抄成 `proto8/lib/`、照 `py/entries.json` 在 `proto8/bin/` 生指令入口；`proto8/templates/`（含 kernel 範本 `templates/kernels/`）不用裝、原地就是成品；agent-fsm 的格 11-24 起不在範本裡，在 `py/aos/apps/agent_fsm/`，跟其他 Python 一樣要 `install.py` 裝進 `lib/` 才生效。要確認就手跑（用法在各自的 README）。aos 的程式都不動 PATH，手跑時把 `proto8/bin/` 放進 PATH（`source $AOS_HOME/env.sh` 一次放好；舊的 `cmd/install.sh` 11-18 S5 收掉了）。

## 不碰跑著的樹

家機與公司 WSL 兩台的 `~/aos-home` 都有使用者在用的樹，agent 的 Bash 帶著它的 `AOS_*`（[行程與環境](../public/行程與環境.md#agent-的-bash-帶著活樹的-aos_跑測試或-aos-指令前先清清的寫法在-zsh-裡會靜靜失效)）；在這台跑任何測試、手跑任何 aos 指令：

- **先清環境，用 bash 腳本、不在 zsh 裡清**：把下面存成暫存夾裡的 `clean-env.sh`，一律 `bash clean-env.sh <指令…>` 跑（不 `source`）。zsh 的 `env -u $VARS`、在 zsh `source` bash 寫法的環境檔都等於沒清（11-13 線寅、線申各中一次，檔寫進活樹頂層那格 stack）。

  ```bash
  #!/bin/bash
  [ -n "$BASH_VERSION" ] || { echo "not bash, refuse" >&2; exit 2; }
  for v in $(compgen -e | grep '^AOS_'); do unset "$v"; done
  if env | grep -q '^AOS_'; then echo "AOS_* still set, refuse" >&2; exit 2; fi
  exec "$@"
  ```

- **全套測試、要當基準的那次，在乾淨複本上跑**：`git archive <commit> | tar -x -C ~/.aos/scratch/<線名-日期>/<子夾>`，不在共用的工作樹上跑——別線改到一半的檔會讓結果只反映當下的工作樹，測試寫錯環境時也不會碰到 repo 與活樹。
- **要起樹就起在 `~/.aos/scratch/<線名-日期>/` 這個獨一無二的暫存夾**（使用者 11-15 裁「4.a」；不放 `~/code`，那是使用者自己的空間），tmux 用 `-S <暫存夾內 socket>`；收行程只收自己記下的（寫法在 [aos-teams/06](dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#任務書必貼的硬規則) 第 4 條）。
- **跑完核對**：`pgrep -u "$USER" -af aos-daemon` 跟開工前一樣、活樹裡頂層那格 stack 的 `ls` 跟開工前一樣；指令與輸出貼進回報。
- **測試程式自己也不寫 `pkill -f`**：收自己記下的 pid。

## 綠燈不等於有檢查

**一道檢查通過，可能是因為它根本沒在檢查。** 新增或修改一道檢查時，要證明它能變紅：先餵一個**應該被擋**的輸入，確認 exit ≠ 0；再餵正確的輸入，確認 exit = 0。**build 得過不等於跑起來是對的**；真模型、外部 CLI 的行為只有實跑看得出，這類寄使用者專區（`aos-user send`；進度記在 [progress.json](../progress.json)、標「等使用者」），不要自己宣稱通過。

## 交接

- build 過了回 [feature-dev](feature-dev/README.md) 接完剩下的步驟（code map → 文檔 → commit）。
- 同一個紅燈第二次撞到 → 記進 [wf/public](../public/README.md#主題)。
