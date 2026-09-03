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
| 要真模型、外部 CLI agent、跨機的（例：T5 agent loop 實測）| 照該實驗檔的步驟 | 使用者 → [WAIT_USER](../WAIT_USER.md)；本機 LM Studio 跑得動的部分我自己跑 |

「誰跑」只有兩種值：**agent**（本機跑得動）、**使用者 → WAIT_USER**（要實機、外部服務、帳號、付費、目視）。判不準就當後者。

## 測試分類

四類對照本專案的實況：

- `fast`：`aos_*_tests` 全部——離線、單機、不需特殊環境；每次小改都跑。
- `contract`：跨 process 邊界的——exec 層真 `fork`/`exec` 的測試（`core/exec/tests/`）、`aos_agent_fake_loop` 這種靠 `.aos/` 版面與 python loop 替身協作的整合測試；已含在同一個 ctest 裡，改 producer／consumer／協定時特別盯。
- `full`：`ctest --preset default` 整套；commit 前或大改後跑。
- `external`：真 LLM、外部 CLI agent（codex／claude）、跨機（WSL）——agent 代跑不了的記到 [WAIT_USER](../WAIT_USER.md)。

| ctest 目標 | 小專案 | 涵蓋 |
|-----------|--------|------|
| `aos_exec_tests` | `core/exec/` | 整批 POSIX 行程的啟動／等待／中斷：重導向與 env／cwd、平行執行、逾時、中斷、結束時間戳 |
| `aos_wire_tests` | `core/wire/` | 指令、結果與 loop state 三種協定的 JSON round trip 與壞輸入錯誤 |
| `aos_loop_tests` | `core/loop/` | 資料夾回合機：folder 解析、agents／every 複製、deliver 投遞、idle／running state、平行執行與整回合 `run` CLI |
| `aos_llm_tests` | `core/llm/` | OpenAI 相容 client：環境變數／CLI 參數／request-response JSON、`--engine`／`--priority`，以及 LLM 並行槽（`test_slot.cpp`）；離線假 transport |
| `aos_tool_tests` | `core/tool/` | 世界層工具登記表與 agent 通訊錄：spec 驗證、registry 讀寫、探測降級、contacts 與 `tool`／`contact` CLI |
| `aos_agent_tests` | `core/agent/` | 回合制 LLM agent：CLI（say／listen／talk／state）、engine 選擇、生命周期（journal／防竄改）、`step()`、儲存層與工具展開／抽取 |
| `aos_agent_fake_loop` | `core/agent/` | python 版 loop 替身（`fake_loop.py`）自測，跨 process 驗證它能正確搬 inbox／執行 instruction／推進回合 |
| `aos_tick_tests` | `core/tick/` | heartbeat 判定：clock、到期規則（due）、routines／schedule 表讀寫、`aos tick` CLI |

日後新增小專案（不分 `core/` 或 `modules/`）照同一個命名慣例掛自己的 `aos_<專案>_tests`，跑不了的環境依賴驗證才記 [WAIT_USER](../WAIT_USER.md)。

## 綠燈不等於有檢查

**一道檢查通過，可能是因為它根本沒在檢查。** 本專案真撞過：`.runi` 看起來像鎖但不互斥（[gotchas](common/gotchas.md)）、外部消費測試沒 `env -u VCPKG_ROOT` 等於白測、測試連 OBJECT library 繞過了 `AOS_API` 可見度。

**規則：新增或修改一道檢查時，要證明它能變紅。** 先餵一個**應該被擋**的輸入，確認 exit ≠ 0；再餵正確的輸入，確認 exit = 0。**沒做過這個雙向驗證的綠燈不算證據。**

兩個推論：檢查器的**涵蓋範圍要跟著結構走**——搬走目錄、拆出小專案之後，回頭確認 ctest 與 `wf/tools/wf-lint.sh` 還看得到那些地方（見 [refactor/moving-things](refactor/moving-things.md)）；**靜態全過不等於實際跑起來是對的**，真模型、外部 CLI 的行為只有實跑看得出，這類記到 [WAIT_USER](../WAIT_USER.md)，不要自己宣稱通過。

## 交接

- 綠燈後回 [feature-dev](feature-dev/README.md) 接完剩下的步驟（code map → 文檔 → commit）。
- 同一個紅燈第二次撞到 → [common/gotchas](common/gotchas.md)。
