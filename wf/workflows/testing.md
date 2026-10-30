# testing — 跑測試／驗證（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

改完怎麼確認沒壞：有哪些驗證、各自的指令、哪些我自己跑得了、哪些得交給使用者。**一律從 repo 根目錄跑**，子專案不可單獨 configure。

**何時用**：改完程式要驗（鐵律 1）、使用者說「跑測試」、重構前要記基準。
**何時不用**：環境還沒裝好、不知道指令哪來 → [dev-env](dev-env.md)；驗證紅了要查成因 → [investigation](investigation.md)。

## Done when

- 下表標「改完必跑」的指令回傳 0，且 ctest **全綠**。
- 「誰跑」是使用者的列，已在 [WAIT_USER](../WAIT_USER.md) 各留一行（寫明跑什麼、什麼算過）。

## 驗證表

| 驗證 | 指令 | 誰跑 |
|------|------|------|
| 設定（第一次、或 `CMakeLists.txt`／`vcpkg.json` 變動後）| `cmake --preset default` | agent |
| **快速驗證（改完必跑）** | `cmake --build --preset default && ctest --preset default` | agent |
| 只跑某個小專案的測試 | `ctest --preset default -R '^aos_exec'`（或該小專案登記的測試名稱前綴）| agent |
| 完整驗證（commit 前）| 同快速驗證——目前沒有額外分出兩套，測試量還小 | agent |
| 動過 `modules/` 之後 | `cmake -S . -B /tmp/aos-nomod -DAOS_BUILD_MODULES=OFF && cmake --build /tmp/aos-nomod`（確認關掉擴充仍建得起來）| agent |
| proto8（現役主線）：先建 impls，再跑測試與 demo | 見下面「proto8」 | agent |
| 要真模型、外部 CLI agent、跨機的（例：T5 agent loop 實測）| 照該實驗檔的步驟 | 使用者 → [WAIT_USER](../WAIT_USER.md)；本機 LM Studio 跑得動的部分我自己跑 |

「誰跑」只有兩種值：**agent**（本機跑得動）、**使用者 → WAIT_USER**（要實機、外部服務、帳號、付費、目視）。判不準就當後者。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../STRUCTURE.md) 按 `##` 標題拆開；本檔留前言、Done when、驗證表、交接，其餘各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-proto8](testing/01-proto8.md) | proto8（不在 ctest 裡） |
| [02-測試分類與綠燈](testing/02-測試分類與綠燈.md) | 測試分類、綠燈不等於有檢查 |

## 交接

- 綠燈後回 [feature-dev](feature-dev/README.md) 接完剩下的步驟（code map → 文檔 → commit）。
- 同一個紅燈第二次撞到 → [common/gotchas](common/gotchas.md)。

<a id="proto8不在-ctest-裡"></a>
