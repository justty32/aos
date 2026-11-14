# sol-1 答案（repo 盤點、公開範圍、隱私初掃、LICENSE），11-14
> 存檔註（11-14 commit 前）：家目錄絕對路徑換成 `~`、帳號名換成 `<帳號名>`；其餘是 sol 原文。


結論：現有 README 已有一句話介紹，但主要是開發導航，尚不是外人可從零照做的 demo 入門文件；產品程式、規範與私人討論紀錄混在 `proto8/`。指定範圍初掃未查到個人帳號／信箱字串，關鍵字命中多為文件、測試與設定名稱，不能當成秘密外洩證據；repo 根與 `proto8/` 頂層均未見 LICENSE。出處：`README.md:3`、`README.md:10`、`proto8/README.md:7`、`proto8/README.md:46`；授權另見 D。

以下路徑均相對 `~/repo/aos/`。全程僅用唯讀工具，沒有執行 shell 指令、寫檔或寄信。

## A. README 現況與缺口

| 檔案 | 現在寫了什麼 | 對外入門缺口 |
|---|---|---|
| `README.md` | 已有「資料夾＝程式的 AI agent 體系」一句話介紹、C++20／CMake／vcpkg 需求、安裝腳本說明、repo 佈局與文件入口。 | 本文沒有可直接照抄的完整建置流程，指令轉到內部 `wf/`；沒有從安裝到第一次成功執行的快速開始、預期輸出、實際使用情境。出處：`README.md:3`、`README.md:7`、`README.md:10`、`README.md:25`。 |
| `proto8/README.md` | 以原型重啟背景開場，列各夾用途、概念／規範／慣例入口、實作現況、歷史討論與開發規矩；有 templates、kernel 等入口。 | 本文沒有完整的零起點 demo 教學；讀者先遇到內部名詞、日期與裁定紀錄。圖解指向 Claude artifact，並引用 `scratchpad/pages/` 源碼位置；連結是否仍可公開存取，未查到。出處：`proto8/README.md:1`、`proto8/README.md:38`、`proto8/README.md:40`、`proto8/README.md:46`、`proto8/README.md:60`。 |

不能說「整個 repo 完全沒有範例或使用文件」：目前已有 CLI 用法、agent 範本、數學 smoke 考題，以及 sandbox 範例；缺的是兩份 README 中串起來的首次體驗路徑。出處：`proto8/cmd/README.md`、`proto8/templates/README.md`、`proto8/cases/README.md`、`proto8/cmd/aos-sandbox/examples/shell-boxed/README.md`。

## B. 頂層資料夾盤點

分類僅描述現有內容，不代表公開／排除決定：

- 產品：外人會用到的產品本體。
- 參考：外人看得懂但偏內部的規範、開發或歷史資料。
- 內部：純內部調度／私人紀錄。

檔數以唯讀 `glob("**", hidden=true)` 統計，沿用 `.gitignore` 排除規則；含文件與測試，不等於 Git 追蹤檔數。各列數字出處為該路徑的 glob 結果，角色出處列於末欄。

**Repo 根目錄**

| 資料夾 | 分類 | 約檔數 | 一句話用途／出處 |
|---|---|---:|---|
| `proto8/` | 產品，混有參考與內部資料 | 2,699 | 現役第八版原型，含核心、CLI、工具、範本及討論紀錄。`proto8/README.md` |
| `impl_cpp/` | 參考 | 46 | 使用者另行手寫的獨立 C++23 核心重寫，目前不是 proto8 的依賴。`impl_cpp/README.md` |
| `archive/` | 參考 | 8,629 | 封存 proto～proto7-2 與 aos-v1，不再維護。`archive/README.md` |
| `wf/` | 內部 | 1,468 | 開發工作流、agent 調度、進度、交接、待使用者與信件。`wf/INDEX.md` |
| `.claude/` | 內部 | 1 | Claude compact 後重讀工作狀態的 hook 設定。`.claude/settings.json` |
| `.vscode/` | 內部 | 1 | 本機 VS Code 設定，含個人絕對路徑。`.vscode/settings.json` |
| `.git/` | 內部 | 未查到 | 根目錄 ls 有列出；未深入讀取，內容與檔數未查到。`.git/` |

根目錄沒有 `.github/` 或產品頁資料夾；這只表示頂層 ls 未見，GitHub 遠端 Pages 設定未查到。出處：`~/repo/aos/` 的含隱藏檔 ls。

**`proto8/` 全部 15 個頂層資料夾**

| 資料夾 | 分類 | 約檔數 | 一句話用途／出處 |
|---|---|---:|---|
| `impls/` | 產品 | 281 | C／C++ 核心與標準庫：執行、loop、FSM、daemon 等。`proto8/impls/README.md` |
| `cmd/` | 產品 | 173 | 給人在終端操作 agent、daemon、工具、信箱、MCP 等的指令。`proto8/cmd/README.md` |
| `py/` | 產品 | 20 | CLI、範本與 kernel 共用的 Python 模組，不直接進 PATH。`proto8/py/README.md` |
| `lib/` | 產品 | 454 | agent 可呼叫的工具函式庫與共用模組。`proto8/lib/README.md` |
| `kernel/` | 產品 | 25 | 收請求、管資源／排程及問模型的可複製範本。`proto8/kernel/README.md` |
| `templates/` | 產品 | 84 | agent-fsm、eca-claude、根 daemon、裁判等範本及測試。`proto8/templates/README.md` |
| `knowledge/` | 產品 | 153 | 出廠知識樹，包含 aos 說明及通用 wf 工作流資料。`proto8/knowledge/README.md` |
| `cases/` | 產品 | 14 | measure 共用考題格式、固定答案與 smoke／box-probe 套題。`proto8/cases/README.md` |
| `docs/` | 參考 | 139 | CONCEPTS、NORMS、CONVENTION 三套概念、規範與慣例。`proto8/docs/README.md` |
| `extras/` | 參考，混合內容 | 31 | 尚未定位的實驗、開發檢查、語言嘗試與換樹腳本。`proto8/extras/README.md` |
| `archive/` | 參考 | 97 | 舊 demo、工具與概念封存，不測試、不維護內部連結。`proto8/archive/README.md` |
| `thinking/` | 內部 | 1,190 | 按日期保存使用者原文、決定、結論及未決問題。`proto8/thinking/README.md` |
| `user-advice/` | 內部 | 12 | 使用者親手寫的構想與意見稿。`proto8/_index.json`、`proto8/user-advice/README.md` |
| `notes/` | 內部 | 17 | AI 撰寫的外部技術對照與參考筆記，明定不是規範。`proto8/notes/README.md` |
| `feedback/` | 內部 | 6 | 跨 session 的指令／工具使用意見與評分者辨識規則。`proto8/feedback/README.md` |

另外，`proto8/install.sh` 是產品安裝入口：建立命令 symlink，並設定 Python user-site 匯入路徑；不是獨立資料夾。出處：`proto8/cmd/README.md`、`proto8/_index.json`。

## C. 隱私初掃

範圍嚴格限定為題目指定的七處：`proto8/README.md`、`proto8/docs/`、`proto8/templates/`、`proto8/lib/`、`proto8/cmd/`、`proto8/install.sh`、`proto8/knowledge/`。

grep 啟用隱藏檔、停用 gitignore 排除；仍會跳過二進位與超過工具大小上限的檔案。因此以下是文字初掃，不是完整秘密稽核。templates／lib／cmd 分別有 21／96／54 個二進位檔被跳過，出處為各範圍 grep 回報。

**命中檔數**

| 類別／字串 | 命中檔數 | 分布或說明 |
|---|---:|---|
| `/home/<帳號名>` | 0 | 指定七處未查到。 |
| `<帳號名>` | 0 | 指定七處未查到。 |
| `justty` | 0 | 指定七處未查到。 |
| `@gmail` | 0 | 指定七處未查到。 |
| `.zshrc` | 0 | 指定七處未查到。 |
| `sk-` | 17 | docs 4、templates 3、lib 7、cmd 3。包含 `task-` 等子字串誤報。 |
| `token` | 92 | docs 15、templates 16、lib 48、cmd 5、knowledge 8。 |
| `api_key` | 1 | docs 1，為名稱示例。 |
| 主機／環境關鍵字 | 23 | 搜尋 `hostname`、`主機`、Manjaro／WSL 大小寫；docs 2、templates 2、lib 6、cmd 11、install 1、knowledge 1。 |
| 補掃主機名／位址形狀 | 6 | 搜尋 skyrim／Argon、desktop／laptop 名字形狀、prod-db／prod-web、IPv4；與前列有重疊，不可相加。 |

上述數字出處為各指定路徑的逐類 grep 結果；零命中類別沒有可列的例子。以下僅列路徑、行號與類別，不抄命中整行或任何值。

**`sk-` 前 10 個例子（以不同檔案列示）**

1. `proto8/docs/CONCEPTS/05-agent/03-C-84.md:15` — `sk-` 子字串。
2. `proto8/docs/CONCEPTS/附錄3-條號表/01-條號-檔.md:28` — `sk-` 子字串。
3. `proto8/docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md:11` — `sk-` 子字串。
4. `proto8/docs/NORMS/附錄3-舊名對照.md:18` — `sk-` 子字串。
5. `proto8/templates/docs/01-eca-claude.md:82` — `sk-` 子字串。
6. `proto8/templates/eca-claude/README.md:9` — `sk-` 子字串。
7. `proto8/templates/tests/agent-fsm/test_do_task_fold.py:53` — 測試名稱／暫存前綴。
8. `proto8/lib/agent/cli_cfg.py:58` — `sk-` 子字串。
9. `proto8/lib/agent/cli_mcp.py:220` — `sk-` 子字串。
10. `proto8/lib/agent/cli_screen.py:67` — `sk-` 子字串。

另外兩個值得人工核對的命中檔是 `proto8/lib/base/llm_http/tests/test_llm_http.py:74`、`proto8/cmd/aos-tools/tests/test_env_file.py:45`；讀到的是測試輸入與斷言，未查到它們是真實憑證的證據。

**`token` 前 10 個例子**

1. `proto8/docs/CONCEPTS/01-設計理念/04-C-54.md:20` — token／計數命名。
2. `proto8/docs/CONCEPTS/01-設計理念/C-54-命名方法/01-R1～R7.md:14` — token／計數命名。
3. `proto8/docs/CONCEPTS/01-設計理念/C-54-命名方法/02-R8～R13.md:8` — token 額度欄位。
4. `proto8/docs/CONCEPTS/05-agent/01-續-C-22.md:6` — token 消耗。
5. `proto8/docs/CONVENTION/02-題目stack停錯腦/05-P-23～P-26.md:8` — token 用量。
6. `proto8/docs/CONVENTION/02-題目stack停錯腦/07-P-44.md:11` — 命令列 tokenize。
7. `proto8/templates/agent-fsm/brain.py:7` — 模型參數。
8. `proto8/templates/agent-fsm/interfaces.json:1` — 模型參數宣告。
9. `proto8/templates/agent-fsm/llm_settings.py:11` — 模型參數。
10. `proto8/templates/docs/01-eca-claude.md:108` — 憑證環境變數名稱。

**`api_key` 全部例子**

- `proto8/docs/CONCEPTS/abbr.json:179` — 設定名稱示例。

**主機／環境關鍵字前 10 個例子**

1. `proto8/docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md:15` — WSL 環境。
2. `proto8/docs/NORMS/附錄4-持久檔.json:364` — hostname 識別機制。
3. `proto8/templates/docs/01-eca-claude.md:107` — 主機佔位符。
4. `proto8/templates/eca-claude/README.md:19` — 主機確認 hook。
5. `proto8/lib/agent/cli_cell.py:13` — 主機識別機制。
6. `proto8/lib/aos/_index.json:3` — 主機隔離檢查說明。
7. `proto8/lib/aos/box_check/README.md:1` — 主機隔離檢查。
8. `proto8/lib/aos/shell_report/README.md:41` — 主機 PATH 行為。
9. `proto8/lib/base/llm_http/_entry:84` — URL hostname 欄位。
10. `proto8/lib/docs/02-索引-base與索引-aos.md:59` — 主機隔離檢查索引。

**補掃主機名／位址形狀：全部 6 個命中檔**

- `proto8/templates/eca-claude/README.md:25` — 示範主機名／位址前綴。
- `proto8/lib/agent/tests/test_cli_external_mcp.py` — 測試端點位址；行號未查到。
- `proto8/lib/base/llm_http/tests/test_llm_http.py` — 測試端點位址；行號未查到。
- `proto8/lib/tests/test_mcp_client.py` — 測試端點位址；行號未查到。
- `proto8/cmd/aos-sandbox/README.md` — 位址形狀；行號未查到。
- `proto8/knowledge/aos/user_zone.json:5` — 本機監聽位址。

範圍外另有明確個人路徑：`.vscode/settings.json`。這不計入 C 的命中數，但屬根目錄公開素材需知的現況；未抄出其值。

## D. LICENSE／授權

- repo 根與 `proto8/` 頂層的含隱藏檔 ls 均未見 LICENSE／LICENCE；兩份 README 的 `License|授權|MIT|Apache` 搜尋均無命中。出處：`README.md`、`proto8/README.md` 及兩層目錄 ls。
- proto8 原始資料中查到一處真正談軟體授權的紀錄：提及工作流模板的 CC0＋MIT，並明寫 aos 根目錄當時沒有 LICENSE。這是討論紀錄，不能據此認定整個 aos 已採 MIT。出處：`proto8/thinking/2026-11/13/workflows-into-aos.md:96`。
- 其他「授權」命中多是允許刪除／封存／操作的授權，不是軟體使用授權；例如 `AGENTS.md:36`、`proto8/archive/README.md:15`。
- 含忽略檔的補掃可見 vcpkg 建置相依的授權資料，但那不是 aos 本體的授權聲明。出處：`proto8/impls/build/vcpkg_installed/x64-linux/share/nlohmann-json/copyright`。
- aos 本體適用哪種公開授權：未查到。

實際已依序讀完必讀清單 1～6；第 1 項包含 `_description.json` 全文及該資料夾的 `index_view`。