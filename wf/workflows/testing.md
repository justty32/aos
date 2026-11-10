# testing — 驗證（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

改完怎麼確認沒壞。**11-04 起沒有自動測試**：使用者「感覺proto8/test已經成為我們的負擔了，能夠精簡嗎？我希望能大刪特刪」「激進版，不用說，甚至我希望整個刪掉也OK。」「ctest也可以刪掉吧」「這個鐵律刪掉，不用ctest」——`proto8/tests`、`proto8/impls/*/tests`、`core/*/tests` 與 ctest 設定全刪（盤點與清單：[thinking 11-04 tests-trim](../../proto8/thinking/2026-11/04/tests-trim.md)）。驗證只剩「**build 得過**」，行為對不對靠手跑。（11-10 註：之後各處又長回一些定向 〔proto8 現役約 48 支，如 、、〕；build 仍是唯一統一必跑，改到哪就挑那處既有的定向測試跑，[prefix-fixes 坑-55](../../proto8/thinking/2026-11/04/tests-trim.md)。）

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

repo 根沒有 CMake（08～09 月那一代 11-05 封存到 `archive/aos-v1/`、不再建），要建的只有 `proto8/impls/`：頂層 `impls/CMakeLists.txt` 一次建全部（11-05 S3；各專案仍可單獨 `cmake -B build`，兩種擇一、不要同時跑，見 impls/docs/04；`bin/`、`build/` 不進 git）：

```sh
(cd proto8/impls && cmake -B build && cmake --build build)
```

`proto8/cmd/`（指令）、`proto8/py/`（共用模組）、`proto8/lib/`、`proto8/kernel/`、`proto8/templates/` 是 Python／sh，沒有建置步驟；要確認就手跑（用法在各自的 README）。aos 的程式都不動 PATH，手跑時把 `proto8/impls/<名>/bin/`、`proto8/cmd/<名>/bin/` 放進 PATH（`proto8/install.sh` 一次放進 `~/.local/bin`）。

## 綠燈不等於有檢查

**一道檢查通過，可能是因為它根本沒在檢查。** 新增或修改一道檢查（例如 `wf/tools/wf-lint.sh` 的一條）時，要證明它能變紅：先餵一個**應該被擋**的輸入，確認 exit ≠ 0；再餵正確的輸入，確認 exit = 0。**build 得過不等於跑起來是對的**；真模型、外部 CLI 的行為只有實跑看得出，這類記到 [WAIT_USER](../WAIT_USER.md)，不要自己宣稱通過。

## 交接

- build 過了回 [feature-dev](feature-dev/README.md) 接完剩下的步驟（code map → 文檔 → commit）。
- 同一個紅燈第二次撞到 → [common/gotchas](common/gotchas.md)。
