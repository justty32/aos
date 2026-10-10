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

## 跨機 / 離線差異

兩台輪流開發：家裡 Manjaro Linux（repo 在 `~/repo/simple_tools/aos`）、公司 WSL2 Ubuntu（repo 在 `~/projs/aos`，見下方「公司那台」；2026-10-01 使用者確認仍在用）。沒有 CI 差異，全部驗證都由 agent 跑。[SESSION-LOG](../SESSION-LOG.md) 裡「repo 在 `/mnt/c`」那條已過期。

**公司那台**（2026-09-07 他開場說的，10-01 從那台的舊記憶搬來）：公司 WSL（Ubuntu），repo 在 `~/projs/aos`，codex 在 `~/.local/bin/codex`。區網 **`192.168.1.146`** 有 ollama（當時有 qwen2.5:14b、qwen3:32b、deepseek-r1:8b、gemma3:1b）；142 那台沒開 ollama 的口（他一開始說錯）。兩台都可能是當下這台，所以**開場先確認在哪台、LLM 走哪個端點**；146 跟下面「模型端點」（09-25 定的「只走 LiteLLM」）哪個優先沒講清楚，在公司要用 146 先問他一句。

## 外部工具與 env var

| 名稱 | 用途 | 怎麼取得 / 設定 |
|------|------|----------------|
| vcpkg（`~/dev/vcpkg`）| C++ 相依（nlohmann、curl…）| 見上面流程第 1 步；`VCPKG_ROOT` 可選 |
| codex CLI（`/usr/bin/codex`）| 10-09 家機實測 9 個 slug 可用（09-24～10-08 曾只剩 `gpt-6-astra`）；清單、呼叫與沙箱見 [aos-teams](dispatch/aos-teams.md) | 已裝；需要的登入由使用者做 |
| LiteLLM 代理（`localhost:4000/v1`）| 真模型實測的預設端點，見下方「模型端點」| 家機已架好（使用者自己的 `~/repo/llm_proxy`，`litellm --config ./litellm.yaml --port 4000`，10-10 確認在跑）；公司那台未確認；不用 api_key |
| LM Studio（`localhost:1234`）| 本機真模型（吃 GPU）| 使用者開著才在；換模型前先 unload 舊的；並行實測取鎖見 [resources](resources.md) |
| 外部 LLM 帳號（Claude OAuth 等）| T5 agent loop 真模型實測 | 要使用者登入 → [WAIT_USER](../WAIT_USER.md)；金鑰不進 repo |

## 模型端點（2026-09-25 定，10-10 核對）

家機的 LiteLLM 已架好、跑在 `localhost:4000`（見上表），開工前仍先 `curl localhost:4000/v1/models` 看當下名單。


**只走 LiteLLM `http://localhost:4000/v1`**。使用者 09-25 原話：「只許使用這個，想要啥模型都可以用，額度無上限，可以的話盡量用 codex／gpt 系；就是不能碰 LM Studio」。用之前先 `curl localhost:4000/v1/models` 看當下有哪些名字，強模型優先挑 gpt／codex 系。LiteLLM 沒開時才直連 `https://api.deepseek.com/v1`，金鑰只從環境變數 `DEEPSEEK_API_KEY` 讀，不印、不寫進檔。

**GPU 是他的**：他常在打遊戲，不准碰 LM Studio、不准用 LiteLLM 上的 `ollama-*`（本機、吃 GPU）、不准 `lms load`。`deepseek-*`、gpt、claude 這些雲端的不吃 GPU。

**2026-10-09 使用者准許 aos 的 LLM 包（llmcall／author）接真 AI**：走同一個 LiteLLM，**不用 `lm-*`**（也照舊不用 `ollama-*`），盡量用 gpt 系（`chatgpt-gpt-6-sol`、`chatgpt-gpt-6-astra` 等，帶 `-high`／`-max` 後綴可調推理強度）。token 額度、輸出長度、context 上限**全部拉到極限、不用省**；跑完一個大段落後再依實際消耗量訂限制。

`deepseek-chat` 是別名，回應的 `model` 欄寫 `deepseek-flash`；任何「回應 model 要等於設定」的檢查都要對它放行。

他明講可以用 LM Studio 時：一次只能載一顆，**換模型前先 `lms unload --all`**（VRAM 不夠會回看起來像端點壞掉的錯）；`lms ps` 看載了什麼（`/v1/models` 只代表下載了）；模型 id 用問的、不要猜。gemma 這類會先「想」的模型，想的字數算在 `max_tokens` 裡——冒煙測試不要設 `max_tokens`，要設就 1500 以上。

需要帳號、付費、授權才能取得的：守鐵律 2（授權來源），並在 [WAIT_USER](../WAIT_USER.md) 記一行。

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
