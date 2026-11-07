# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的夾，再去生成冊看那一段，只讀列出的檔，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂

現役程式全在 `proto8/`（repo 根的 `core/`、`app/` 那代 C++ 是 08～09 月的甲代，不再維護，逐檔表已封存）。proto8 裡：

- `impls/`：C／C++ 的 CMake 專案家族（`aos-inst` 是 C 函式庫，其餘 C++）。由下往上：`aos-inst` → `aos-exec` → `aos-loop` → `aos-fsm`／`aos-daemon`；`aos-llm` 連 `aos-llm-kernel`；`aos-util` 全家共用；`aos-post`（連 `aos-lock`）是信箱。誰連誰的表在生成冊 `impls` 冊開頭。
- `cmd/`：人打的 Python 指令，執行檔在 `cmd/<名>/bin/<名>`；命令列共用模組在 `py/`，CLI 對話與介面宣告共用模組在 `lib/agent/`（`cli_session.py`、`agent_files.py`；`lib` 不 import `py`）。`lib/`：腦叫的工具（`_entry`＋`_tooldef.json`＋`_metainfo.json`）。
- `kernel/`：掛在 daemon 上的管理元件；`templates/`：agent 範本；`knowledge/`：知識庫；`extras/`：還沒定位的嘗試。判準看 [proto8/README](../../../proto8/README.md)「頂層一覽」。
- `docs/`（條文）、`thinking/`、`notes/`、`archive/` 不是程式，不進 code map。

## 逐檔表：生成冊

**哪個檔負責什麼**不手寫：`wf/tools/codemap_gen.py` 從每個檔的檔頭一句話生成，一個 proto8 頂層夾一冊，索引在 **[code-map/proto8/README](code-map/proto8/README.md)**（照實際夾名產，夾改名後重跑就跟上）。

- 一句話寫在哪：C／C++ 第一行 `// 檔名：一句話`；腳本與 `_entry` 跳過 shebang 後第一行 `# 名 - 一句話`（Python 也可以是 docstring 第一行）；CMake 第一行註解；JSON 用 `description`（工具夾的 `_tooldef.json`）、`summary`、`$comment` 或 `title`；knowledge 的 md 用第一個標題。
- **新增、刪除檔或某檔職責變了**：改檔頭那一句，commit 前跑 `python3 wf/tools/codemap_gen.py --apply`，生成冊跟程式同一個 commit。不帶參數＝只檢查，`wf-lint` 的 CODEMAP 就是它（不一致算 broken）。
- 一句話空或只寫檔名，生成器印 warning（不擋），順手補檔頭。
- 行為細節不在 code map：看各程式自己的 README（[impls/README](../../../proto8/impls/README.md)、[lib/README](../../../proto8/lib/README.md) 等）。

## 常查的東西在哪

| 我想找… | 去哪 |
|---|---|
| 錯誤行／提醒行、stdin 讀 JSON、stdout 印一行（C++） | `impls/aos-util` 的 `aos/util/io.hpp`；旗標 `parse_cli` 在 `aos/util/cli.hpp` |
| Python 命令列的旗標與錯誤行 | `py/aos_flags.py`（人打的指令共用）；lib 工具與 `lib/agent/cli_session.py` 共用 `lib/tool_io.py` |
| Python 共用模組怎麼找到、repo 外的複本怎麼 import | 自己的資料夾 → 自己 realpath 往上找 repo `py/`／`lib/` → 標準 `sys.path`（`install.sh` 的 user site `aos-proto8.pth` 或 `PYTHONPATH`）；說明在 [py/README](../../../proto8/py/README.md) |
| claude／codex 對話、tools／llm 宣告檔位置 | `lib/agent/cli_session.py`、`lib/agent/agent_files.py`（cmd 與範本可共用） |
| 某支人打的指令 | `cmd/<名>/bin/<名>`，說明在 [cmd/README](../../../proto8/cmd/README.md) |
| agent 範本、問腦的 kernel、判官 | `templates/`、`kernel/`（判官工具本身在 `lib/aos/judge`） |
| 誰連誰（C++） | 生成冊 `impls` 冊開頭的依賴表 |
| 一個資料夾程式怎麼被找到、怎麼起 | `impls/aos-exec`（條文在 proto8 NORMS N-57～N-62） |
| Python 找 daemon、讀表／prune 自檢、寄信等回信（ping）、共用回信信箱 | `py/daemon_ctl/`（aos-daemon-ctl 是薄殼；aos-agent、aos-eca-screen import 它；prune 自檢只看檔案，行程存活由 daemon 判斷） |
| 信箱（寄、認領、處理完、撤回）與鎖 | `impls/aos-post`、`impls/aos-lock` |
| 腦的工具長怎樣、契約 | [lib/README](../../../proto8/lib/README.md)；逐支一句話在生成冊 `lib` 冊 |

---

## 真相層優先序

三份真相（程式碼／規格文件／code map）衝突時的優先序：

```text
code > proto8/docs 的 NORMS 這類 normative 規格 > schema/examples > 各程式 README > code map > 其他 docs
```

- 上層與下層衝突時，**以上層為準並修正下層**；但規格與程式碼衝突時**先確認哪一邊是刻意的**——分不清就記 [WAIT_USER](../../WAIT_USER.md)。
- 生成冊是從程式碼（檔頭）生出來的，不一致就重跑 `--apply`，不要手改生成冊。
- code map 是**導航不是規格**；行為以程式碼為準（維護鏈見 [conventions](conventions.md)）。
