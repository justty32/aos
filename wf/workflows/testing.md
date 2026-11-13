# testing — 驗證（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

改完怎麼確認沒壞。**沒有統一的自動測試**：使用者「感覺proto8/test已經成為我們的負擔了，能夠精簡嗎？我希望能大刪特刪」「激進版，不用說，甚至我希望整個刪掉也OK。」「ctest也可以刪掉吧」「這個鐵律刪掉，不用ctest」——不設 ctest、沒有整批的 `proto8/tests`（盤點：[thinking 11-04 tests-trim](../../proto8/thinking/2026-11/04/tests-trim.md)）。統一必跑的只有「**build 得過**」；各處有一些定向測試，改到哪就挑那處既有的定向測試跑（[prefix-fixes 坑-55](../../proto8/thinking/2026-11/04/tests-trim.md)）；其餘行為對不對靠手跑。

**何時用**：改完程式要確認沒壞、重構前要記基準。
**何時不用**：環境還沒裝好、不知道指令哪來 → [dev-env](dev-env.md)；build 紅了要查成因 → [investigation](investigation.md)。

## Done when

- 下表標「改完必跑」的指令回傳 0。
- 「誰跑」是使用者的列，已在 [WAIT_USER](../WAIT_USER.md) 各留一行（寫明跑什麼、什麼算過）。

## 驗證表

| 驗證 | 指令 | 誰跑 |
|------|------|------|
| **proto8 impls（改完必跑）** | 見下面「proto8」 | agent |
| 要真模型、外部 CLI agent、跨機的 | 照該實驗檔的步驟 | 使用者 → [WAIT_USER](../WAIT_USER.md)；本機 LM Studio 跑得動的部分我自己跑 |

「誰跑」只有兩種值：**agent**（本機跑得動）、**使用者 → WAIT_USER**（要實機、外部服務、帳號、付費、目視）。判不準就當後者。

<a id="proto8"></a>
<a id="proto8不在-ctest-裡"></a>

## proto8

repo 根沒有 CMake，要建的只有 `proto8/impls/`：頂層 `impls/CMakeLists.txt` 一次建全部（各專案也可單獨 `cmake -B build`，兩種擇一、不要同時跑，見 impls/docs/04；`bin/`、`build/` 不進 git）：

```sh
(cd proto8/impls && cmake -B build && cmake --build build)
```

`proto8/cmd/`（指令）、`proto8/py/`（共用模組）、`proto8/lib/`、`proto8/kernel/`、`proto8/templates/` 是 Python／sh，沒有建置步驟；要確認就手跑（用法在各自的 README）。aos 的程式都不動 PATH，手跑時把 `proto8/impls/<名>/bin/`、`proto8/cmd/<名>/bin/` 放進 PATH（`proto8/install.sh` 一次放進 `~/.local/bin`）。

## 不碰跑著的樹

公司 WSL 的 `~/aos-home` 有使用者在用的樹，agent 的 Bash 帶著它的 `AOS_*`（[gotchas/05](common/gotchas/05-在跑著的樹旁邊做事.md)）；在這台跑任何測試、手跑任何 aos 指令：

- **先清環境，用 bash 腳本、不在 zsh 裡清**：把下面存成暫存夾裡的 `clean-env.sh`，一律 `bash clean-env.sh <指令…>` 跑（不 `source`）。zsh 的 `env -u $VARS`、在 zsh `source` bash 寫法的環境檔都等於沒清（11-13 線寅、線申各中一次，檔寫進活樹頂層那格 stack）。

  ```bash
  #!/bin/bash
  [ -n "$BASH_VERSION" ] || { echo "not bash, refuse" >&2; exit 2; }
  for v in $(compgen -e | grep '^AOS_'); do unset "$v"; done
  if env | grep -q '^AOS_'; then echo "AOS_* still set, refuse" >&2; exit 2; fi
  exec "$@"
  ```

- **全套測試、要當基準的那次，在乾淨複本上跑**：`git archive <commit> | tar -x -C <repo 外的暫存夾>`，不在共用的工作樹上跑——別線改到一半的檔會讓結果只反映當下的工作樹，測試寫錯環境時也不會碰到 repo 與活樹。
- **要起樹就起在 repo 外獨一無二的暫存夾**，tmux 用 `-S <暫存夾內 socket>`；收行程只收自己記下的（寫法在 [aos-teams/06](dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#任務書必貼的硬規則) 第 4 條）。
- **跑完核對**：`pgrep -u "$USER" -af aos-daemon` 跟開工前一樣、活樹裡頂層那格 stack 的 `ls` 跟開工前一樣；指令與輸出貼進回報。
- **測試程式自己也不寫 `pkill -f`**：收自己記下的 pid。

## 綠燈不等於有檢查

**一道檢查通過，可能是因為它根本沒在檢查。** 新增或修改一道檢查（例如 `wf/tools/wf-lint.sh` 的一條）時，要證明它能變紅：先餵一個**應該被擋**的輸入，確認 exit ≠ 0；再餵正確的輸入，確認 exit = 0。**build 得過不等於跑起來是對的**；真模型、外部 CLI 的行為只有實跑看得出，這類記到 [WAIT_USER](../WAIT_USER.md)，不要自己宣稱通過。

## 交接

- build 過了回 [feature-dev](feature-dev/README.md) 接完剩下的步驟（code map → 文檔 → commit）。
- 同一個紅燈第二次撞到 → [common/gotchas](common/gotchas.md)。
