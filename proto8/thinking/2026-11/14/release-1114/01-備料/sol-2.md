# sol-2 答案（依賴軟體與實際安裝步驟），11-14
> 存檔註（11-14 commit 前）：家目錄絕對路徑換成 `~`、帳號名換成 `<帳號名>`；其餘是 sol 原文。


結論：目前是「先建置 C／C++，再用 `install.sh` 登記指令，最後自行複製範本搭樹」，不是一支腳本完成全部安裝。`install.sh` 會寫使用者的指令目錄與 Python user site，但不建立 `~/aos-home`、不安裝依賴、不啟動 daemon。LiteLLM endpoint pack 的設定已在現行文件與範本找到；必讀文件 07 的「待補」段落落後於這些內容。〔`proto8/install.sh`；`proto8/templates/daemon-root/README.md`；`proto8/kernel/docs/01-llm-kernel.md`；`wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md`〕

以下路徑除另註外，皆相對於 `~/repo/aos`。本次只讀檔案與搜尋，未執行安裝、建置或 aos 指令。

## A. `install.sh` 全文結果

已讀全文，執行順序如下：

| 步驟 | 實際行為 | 出處 |
|---|---|---|
| 1 | 解析 `--dry-run`、`--uninstall`、`--help` 與一個目的地參數；預設目的地為 `~/.local/bin`。 | `proto8/install.sh:43` |
| 2 | 以 `readlink -f` 找腳本所屬的 `proto8/` 絕對路徑；repo 位於 `/mnt/*` 時警告。目的地已存在但不是目錄則拒絕。 | `proto8/install.sh:58` |
| 3 | 呼叫 `python3 -m site --user-site` 找啟用的 user site；不可用則警告，繼續安裝指令。 | `proto8/install.sh:66` |
| 4 | 正常安裝時，目的地不存在就建立。 | `proto8/install.sh:91` |
| 5 | 掃描 `impls/*/bin/*`、`cmd/*/bin/*`，只連結普通且有執行權限的檔案。C++ 專案還必須存在 `CMakeLists.txt`，避免裝到舊殘留產物。 | `proto8/install.sh:115` |
| 6 | 在目的地建立指向 repo 原檔的 symlink，不複製程式。相同連結不動；同名別物不覆蓋，最後報 `LinkFailed`。 | `proto8/install.sh:96` |
| 7 | 在 Python user site 建立 `aos-proto8.pth`，內容精確為 repo 的 `proto8/py`、`proto8/lib` 兩個絕對路徑。相同內容不動，不同內容不覆蓋。 | `proto8/install.sh:126` |
| 8 | 警告目的地內指向本 repo 的斷鏈，以及 PATH 上優先命中的其他同名指令；不自行刪除或修正。 | `proto8/install.sh:141` |
| 9 | 目的地不在 PATH 時，只提示使用者修改 `~/.bashrc`；腳本自己不改 PATH、shell rc。 | `proto8/install.sh:155` |
| 10 | 印統計；沒有任何指令則 `CommandMissing`，`impls/*/bin/*` 完全沒有檔案則最後報 `ImplsMissing`。因此失敗前可能已建立部分連結。 | `proto8/install.sh:123`；`proto8/install.sh:159` |

補充：

- **前置軟體**：Bash、一般 Linux 命令工具，如 `readlink`、`dirname`、`basename`、`mkdir`、`ln`、`ls`、`cmp`；`--help` 使用 `sed`。Python user-site 登記需要 `python3`。腳本沒有替使用者安裝這些軟體。〔`proto8/install.sh`〕
- **C++ 必須先建**；腳本不呼叫 CMake、vcpkg 或套件管理器。Python 指令則直接連到 repo。〔`proto8/install.sh:115`；`wf/workflows/dev-env.md`〕
- **會碰家目錄**：預設寫 `~/.local/bin` 和 Python user site；**不會建立 `~/aos-home`、不抄 `lib/templates/knowledge`、不寫 shell rc、不啟動樹**。〔`proto8/install.sh`〕
- `--dry-run` 不建立連結或 `.pth`；`--uninstall` 只移除目的地內指向這份 repo 的連結，以及內容完全符合這份 repo 的 `.pth`。〔`proto8/install.sh:73`；`proto8/install.sh:108`；`proto8/install.sh:126`〕

## B. C／C++ 建置需求

### 專案清單

`impls/` 下有 12 個專案：

| 專案 | 類型／本機 `bin` 狀況 | 依賴來源 |
|---|---|---|
| `aos-inst` | C11 函式庫；未查到 bin 產物 | `proto8/impls/aos-inst/CMakeLists.txt` |
| `aos-util` | 共用函式庫；未查到 bin 產物 | `proto8/impls/aos-util/vcpkg.json` |
| `aos-directive` | C++；有 `bin/aos-directive` | `proto8/impls/aos-directive/vcpkg.json` |
| `aos-exec` | C++；有 `bin/aos-exec` | `proto8/impls/aos-exec/vcpkg.json` |
| `aos-json` | C++；有 `bin/aos-json` | `proto8/impls/aos-json/vcpkg.json` |
| `aos-loop` | C++；有 `bin/aos-loop` | `proto8/impls/aos-loop/vcpkg.json` |
| `aos-lock` | C++；有 `bin/aos-lock` | `proto8/impls/aos-lock/vcpkg.json` |
| `aos-post` | C++；有 `bin/aos-post` | `proto8/impls/aos-post/vcpkg.json` |
| `aos-fsm` | C++；有 `bin/aos-fsm` | `proto8/impls/aos-fsm/vcpkg.json` |
| `aos-daemon` | C++；有 `bin/aos-daemon` | `proto8/impls/aos-daemon/vcpkg.json` |
| `aos-llm` | C++；有 `bin/aos-llm` | `proto8/impls/aos-llm/vcpkg.json` |
| `aos-llm-kernel` | 舊 C++ kernel；本機仍有 bin，但不在目前頂層建置清單 | `proto8/impls/aos-llm-kernel/CMakeLists.txt`；`proto8/impls/CMakeLists.txt:16` |

本機上述 10 個 bin 路徑確實存在；其中 `aos-daemon` 已核為有執行權限的二進位檔。但這不能當成公開發佈的預編譯套件：README 明寫 `build/bin/lib` 是建置產物、不進 git，根 `.gitignore` 也忽略 `bin/`。**可供外人下載的預編譯發佈包：未查到。**〔`proto8/impls/*/bin/*`；`proto8/impls/aos-daemon/bin/aos-daemon`；`proto8/README.md`；`.gitignore:1`〕

### 工具鏈與依賴

- **CMake ≥ 3.21**：頂層與 12 個專案的 `CMakeLists.txt` 均如此宣告。〔`proto8/impls/CMakeLists.txt:1`；`proto8/impls/*/CMakeLists.txt:1`〕
- **C++20、必須支援、關閉 GNU extensions**；`aos-inst` 是 **C11**。GCC／Clang 的最低版本：未查到明文要求。〔`proto8/impls/cmake/settings.cmake`；`proto8/impls/aos-inst/CMakeLists.txt:21`〕
- 已讀頂層與各份 `vcpkg.json`：全部只列 **`nlohmann-json`**，baseline 都是 `b781af668027bbf77f2f827f47b5c6cd8d825c08`；`aos-inst` 沒有自己的 manifest。`aos-exec` 另以 CMake 尋找 `Threads REQUIRED`。〔`proto8/impls/vcpkg.json:5`；上表各 manifest；`proto8/impls/aos-exec/CMakeLists.txt:23`〕
- vcpkg toolchain 優先序：**明給 `CMAKE_TOOLCHAIN_FILE` → `VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake` → 存在的 `~/dev/vcpkg/scripts/buildsystems/vcpkg.cmake`**；都沒有就不設定。〔`proto8/impls/cmake/settings.cmake:9`〕
- 預設 Release、PIC，執行檔採 `-static-pie`；帶 `-fsanitize` 時不加全靜態旗標。因此除了 C++20 編譯器，也需要能完成此連結方式的工具鏈與靜態庫；確切發行版套件清單未查到。〔`proto8/impls/cmake/settings.cmake`〕

文件的建置與安裝順序是：

```sh
cd proto8/impls
cmake -B build
cmake --build build
cd ../..
proto8/install.sh
```

產物寫回各專案的 `bin/`、`lib/`；頂層建置與單專案建置不可同時跑，因為會互蓋產物。淺層 clone 的 vcpkg 若缺 baseline，文件要求補 fetch 該 commit；完整 vcpkg 初次安裝／bootstrap 步驟未查到。〔`proto8/impls/CMakeLists.txt:3`；`proto8/impls/docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md`；`wf/workflows/dev-env.md`〕

## C. Python

- **一般入口只要求 `python3`，統一最低版本未查到**；沒有找到 `requirements*` 或 `pyproject.toml`。可確定的功能限制是 `aos-asuser` 直接使用 `os.unshare(os.CLONE_NEWUSER)`，施工文件註明該 API 從 Python 3.12 起提供；部分 Codex MCP 測試還 import `tomllib`。不能據此宣稱所有基本功能都要求 3.12。〔`proto8/cmd/aos-asuser/bin/aos-asuser:159`；`proto8/thinking/2026-11/14/kernel-limits-1114/B3-aos-asuser.md`；`proto8/lib/agent/tests/test_cli_codex_mcp.py:8`〕
- 掃描 `cmd/`、`py/` 的 import，查到的是標準庫與 repo 自有模組，**未查到必裝的第三方 Python 套件**。HTTP LLM 呼叫用標準庫 `http.client`、`urllib.parse`，不是 OpenAI SDK 或 LiteLLM Python SDK；FSM 文件也明寫四格是純標準庫 Python。〔`proto8/py/`；`proto8/cmd/`；`proto8/lib/base/llm_http/_entry:10`；`proto8/templates/docs/02-agent-fsm.md:5`〕
- `cmd/*/bin/*` 有 **19 支 Python 入口**：`aos-agent`、`aos-asuser`、`aos-clock`、`aos-clock-register`、`aos-daemon-ctl`、`aos-eca-turn`、`aos-eca-screen`、`aos-feedback`、`aos-grow`、`aos-json-view`、`aos-mailbox`、`aos-mcp`、`aos-mcp-import`、`aos-mcp-launch`、`aos-sandbox`、`aos-share`、`aos-sweeper`、`aos-tools`、`aos-tree-start`；各入口 shebang 均為 `#!/usr/bin/env python3`。〔`proto8/cmd/*/bin/*:1`〕
- **`py/` 不是指令、不進 PATH**；它提供 `aos_flags`、`aos_ws`、`daemon_ctl`、clock register／排程與 sweeper 共用模組，透過 repo 路徑、`.pth` 或 `PYTHONPATH` 匯入。Python／sh 區沒有編譯步驟。〔`proto8/py/README.md`；`wf/workflows/testing.md`〕

## D. 外部軟體：用在哪裡、是否必需

| 軟體 | 查到的用途 | 必需／可選與出處 |
|---|---|---|
| s6／`s6-softlimit` | `aos-sandbox` 有資源上限時組進執行鏈；指定一般帳號時使用 `s6-setuidgid`，並檢查 `s6-applyuidgid`。 | **沙箱對應功能需要**，不是所有 aos 執行都需要。daemon 的原生 `limits` 則直接呼叫 `setrlimit`，不是執行 s6。〔`proto8/cmd/aos-sandbox/bin/aos-sandbox:233`；`proto8/impls/aos-daemon/src/child/limits.cpp`〕 |
| Bubblewrap／`bwrap` | `aos-sandbox` 的路徑、環境與網路隔離。 | **正常套用沙箱時需要**；找不到報 `CommandMissing`。〔`proto8/cmd/aos-sandbox/bin/aos-sandbox:294`〕 |
| tmux | 外部 Claude／Codex 的互動畫面，`open`、attach、送字。 | **開 ECA 畫面需要**；找不到報 `TmuxMissing`。一般 FSM 與非互動 CLI 呼叫不是這條路。〔`proto8/lib/agent/cli_screen.py:86`；`proto8/lib/agent/cli_print.py`〕 |
| claude CLI | ECA 的單輪呼叫與互動畫面；零起步 ECA 教學要求先登入。 | **Claude ECA 路線需要**，FSM 假腦／HTTP 端點路線不需要。〔`proto8/lib/agent/cli_print.py:120`；`proto8/thinking/2026-11/12/ops-notes-to-aos.md:44`；`proto8/templates/docs/02-agent-fsm.md`〕 |
| codex CLI | `lib/agent/codex`、`cli_print.py` 的 `codex exec` 與 resume。 | **Codex ECA 路線需要**，不是核心必需。〔`proto8/lib/agent/codex/cli.json`；`proto8/lib/agent/cli_print.py:171`〕 |
| LiteLLM proxy | `smart-high/judge/luna/terra/sol` 等 endpoint pack 指向 `localhost:4000/v1`。 | **使用這些包時需要可達的 proxy**；預設 `fake` 不需要。文件有 `litellm --config ./litellm.yaml --port 4000`，但 LiteLLM 本身安裝與 provider 設定教學未查到。〔`proto8/kernel/llm-kernel/kernel.json`；`wf/workflows/dev-env/01-跨機與外部工具.md:25`〕 |
| LM Studio | `stupid-fast` 包，`localhost:1234/v1` 的本機模型。 | **選用**；模型名稱要符合服務實際載入的名字。〔`proto8/kernel/docs/01-llm-kernel.md`〕 |
| agy | 以 Gemini Argon 提供圖紙審查與第二意見。 | 查到的是**開發工作流工具**；核心執行依賴未查到，安裝方法未查到。〔`proto8/thinking/2026-11/12/kernel-as-bridge/04-Argon審查.md:5`〕 |
| systemd／s6-supervise | 外部監管根 daemon。 | **明確可選，不預設安裝**；兩種範例均未做端到端驗證。〔`proto8/impls/aos-daemon/examples/root/README.md`；`proto8/impls/aos-daemon/docs/10-根daemon.md`〕 |
| `newuidmap/newgidmap` | `aos-asuser` 的免 root subuid 執行。 | **使用 subuid 功能時需要**，另需 user namespace 與 `/etc/subuid`、`/etc/subgid` 授權。〔`proto8/cmd/aos-asuser/README.md`〕 |
| ACL 工具 | `aos-share` 使用 `setfacl`；測試使用 `getfacl`。 | **ACL 分享功能需要**，不是基本起樹必需。〔`proto8/cmd/aos-share/README.md`〕 |

## E. 起新樹、第一隻 agent、LLM kernel

### 1. 文件在哪裡

`proto8/docs/` 查到的是環境變數與路徑規範；完整實作步驟主要在 `templates/daemon-root/README.md`、`kernel/docs/01-llm-kernel.md`、`templates/docs/02-agent-fsm.md`。另外，`extras/aos-home/README.md` 指到一份 **17 步的 `~/aos-home`＋Claude ECA 教學**。〔`proto8/docs/NORMS/10-基礎設施-定義與工作區/09-N-67.md`；上述 README；`proto8/extras/aos-home/README.md`〕

### 2. 現行文件的 FSM 起步順序

以下是文件步驟的整理，不是本次執行紀錄：

1. **先完成 B 的建置與 `install.sh`**，確認 aos 指令在 PATH；複製出 repo 的 Python 程式還需要 `.pth` 或明給 `PYTHONPATH`。〔`wf/workflows/dev-env.md`；`proto8/templates/docs/02-agent-fsm.md:26`〕
2. **決定 `AOS_HOME`**：可直接指 `proto8`，或指包含 `lib/templates/knowledge` 等內容的抄本。若做獨立 `aos-home`，現行複製工具支援抄 `lib/templates/knowledge/py/kernel` 五夾；環境檔正本在 `extras/aos-home/env.sh`。〔`proto8/templates/docs/02-agent-fsm.md`；`proto8/extras/aos-home/README.md`〕
3. **先起 LLM kernel**：複製 `$AOS_HOME/kernel/llm-kernel` 成自己的定義，設定 `AOS_HOME`，必要時先 export `LITELLM_KEY`，再用 `aos-exec --stack <kernel-stack> <kernel-definition>` 前景啟動。啟動殼不要殘留 `AOS_KERNEL`。〔`proto8/kernel/docs/01-llm-kernel.md:36`；`proto8/kernel/docs/01-llm-kernel.md:56`；`proto8/kernel/docs/01-llm-kernel.md:60`〕
4. **建立根與第一隻 agent 定義**：複製 `templates/daemon-root` 成 `defs`，複製 `templates/agent-fsm` 成 `defs/ann`；根的環境需有正確 `AOS_LLM_KERNEL=<kernel-stack>`。〔`proto8/templates/daemon-root/README.md:20`〕
5. **在沒有其他樹環境的殼啟動根**：根範本示例是 `aos-exec --stack stacks/root defs`；較新的 `aos-tree-start` 可先拒絕 `AOS_HOME` 以外的殘留 `AOS_*`，其傳參例子是 `aos-tree-start -- --stack stacks/root defs`。〔`proto8/templates/daemon-root/README.md:25`；`proto8/cmd/aos-tree-start/README.md`〕
6. **掛第一隻 agent**：在專案目錄執行 `aos-agent -d stacks/root ctl add --auto-restart -w . defs/ann`；預設 stack 是 `stacks/root/procs/ann/`。〔`proto8/templates/daemon-root/README.md:31`〕
7. **選腦與交談**：`llm.json` 的 `model` 填 endpoint pack 代號；預設 `{}` 使用 kernel 預設 `fake`。可改成 `{"model":"sol"}`，或對已掛的 agent 使用 `aos-agent llm set`；交談使用 `say/listen/chat`。〔`proto8/templates/docs/02-agent-fsm.md:48`；`proto8/templates/docs/02-agent-fsm.md:59`；`proto8/templates/docs/02-agent-fsm.md:76`〕
8. **確認與停機**：對指定 stack 使用 `aos-daemon-ctl --daemon <stack> ping/ls`；根與獨立 LLM daemon 各自 shutdown。根回 ping 不能代表所有子服務都 ready。〔`proto8/impls/aos-daemon/docs/10-根daemon.md`；`proto8/templates/daemon-root/README.md:38`；`proto8/knowledge/aos/cli/parts/llm_kernel.json`〕

### 3. LiteLLM endpoint pack 的實際設定

現行範本已存在 `endpoints.sol`：

```json
{
  "exec": "endpoints/litellm",
  "url": "http://localhost:4000/v1",
  "model": "chatgpt-gpt-6.1-sol",
  "fixed": {"temperature": 0.2},
  "cost": "high",
  "summary": "LiteLLM gpt-6.1 sol"
}
```

出處：`proto8/kernel/llm-kernel/kernel.json#/endpoints/sol`。

- `exec` 指向 `endpoints/litellm`；其 `_entry` 執行 `llm_http --key-env LITELLM_KEY`。`url` 要含 `/v1`，HTTP 函數再接 `/chat/completions`。〔`proto8/kernel/llm-kernel/endpoints/litellm/_entry`；`proto8/lib/base/llm_http/_entry`〕
- **真正模型名放 pack，agent 只填 `sol`**。模型名字須由 proxy 提供；文件叫使用者用 `/v1/models` 核對。〔`proto8/kernel/docs/01-llm-kernel.md`；`proto8/templates/docs/02-agent-fsm.md:48`〕
- 金鑰在啟動 kernel 的殼／service 環境提供；不寫進 `kernel.json`，也不放 `ctl add --envs`。沒設或空值就不帶 Authorization；proxy 沒驗證時可以不提供。〔`proto8/kernel/docs/01-llm-kernel.md:56`；`proto8/knowledge/aos/cli/agent.json#/add`〕
- `fixed` 不是可讓請求覆蓋的預設：請求若重複指定固定欄位會被拒絕；要換模型／溫度就換包。加包或改模型是改自己的 `kernel.json`。〔`proto8/kernel/docs/01-llm-kernel.md:31`；`proto8/kernel/docs/01-llm-kernel.md:55`〕
- **LiteLLM 的初次安裝、登入與 `litellm.yaml` provider 設定：未查到；不能把「本機已有 proxy」當成外人已完成的步驟。**〔`wf/workflows/dev-env/01-跨機與外部工具.md:25`〕

### 4. `~/aos-home` 的另一份完整教學

17 步文件的主線是：建 `root/daemon/agents/ws` → 抄內容與 `env.sh` → 設根、時鐘、清道夫與 foreman → 複製 `eca-claude` 成 `eca_main` → 設模型與 knowledge 指引 → 首次信任工作區 → 起根 → 在 `ws/` 掛 agent → chat/open → shutdown。**這條是 Claude ECA 路線，不經上述 FSM 的 LLM kernel。**〔`proto8/thinking/2026-11/12/ops-notes-to-aos.md:55`；`proto8/thinking/2026-11/12/ops-notes-to-aos.md:91`；`proto8/thinking/2026-11/12/ops-notes-to-aos.md:119`；`proto8/thinking/2026-11/12/ops-notes-to-aos.md:148`〕

文件存在兩處版本差異，公開整理時需要註明事實，不能直接混抄：

- 舊 17 步只抄四夾，現行 `copy_tree.py` 文件列五夾、包含 `kernel`。〔`proto8/thinking/2026-11/12/ops-notes-to-aos.md:65`；`proto8/extras/aos-home/README.md`〕
- 舊 C++ `aos-llm-kernel` README 仍有舊啟動例子；現行 kernel 文件與知識庫明寫 11-14 起身體改為 `$AOS_HOME/lib/aos/kernel_llm`。〔`proto8/impls/aos-llm-kernel/README.md`；`proto8/kernel/docs/01-llm-kernel.md:7`；`proto8/knowledge/aos/cli/parts/llm_kernel.json`〕

實際已讀必讀清單：1（`_description.json` 全文及資料夾 `index_view`）、2（`AGENTS.md`）、3（`common/user.md`）、4（`aos-teams.md`）、5（06 硬規則）、6（07 預設流程與 agent-fsm），六項全部。