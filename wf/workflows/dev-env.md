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

## 跨機 / 離線差異

目前**單機開發**（Manjaro Linux，repo 在 `~/repo/simple_tools/aos`），沒有離線或 CI 差異，全部驗證都由 agent 跑。[SESSION-LOG](../SESSION-LOG.md) 裡「建置環境是 WSL、repo 在 `/mnt/c`、codex 在 `~/.local/bin/codex`」那幾條是舊環境的筆記，可能已過期（[WAIT_USER](../WAIT_USER.md) B 區有請使用者確認）。

## 外部工具與 env var

| 名稱 | 用途 | 怎麼取得 / 設定 |
|------|------|----------------|
| vcpkg（`~/dev/vcpkg`）| C++ 相依（nlohmann、curl…）| 見上面流程第 1 步；`VCPKG_ROOT` 可選 |
| codex CLI（`/usr/bin/codex`）| 隊員模型 `gpt-5.6-sol`；呼叫方式見 [dispatch](dispatch/README.md) | 已裝；需要的登入由使用者做 |
| LM Studio（`localhost:1234`）| 本機真模型實測（OpenAI 相容端點）| 使用者開著才在；換模型前先 unload 舊的；並行實測取鎖見 [resources](resources.md) |
| 外部 LLM 帳號（Claude OAuth 等）| T5 agent loop 真模型實測 | 要使用者登入 → [WAIT_USER](../WAIT_USER.md)；金鑰不進 repo |

需要帳號、付費、授權才能取得的：守鐵律 2（授權來源），並在 [WAIT_USER](../WAIT_USER.md) 記一行。

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
