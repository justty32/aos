← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽

`proto8/` 是現役主線。這一冊照 proto8 的資料夾分檔，一檔一列：路徑＋它負責什麼。行為細節以各程式的 README 為準（[impls/README](../../../../proto8/impls/README.md)、[bin/README](../../../../proto8/bin/README.md)、[lib/README](../../../../proto8/lib/README.md)、[extras/README](../../../../proto8/extras/README.md)、[demo/README](../../../../proto8/demo/README.md)）。

**新增、刪除檔案或某個檔的職責變了**：去下表涵蓋那個資料夾的分檔加／改／刪那一列，跟程式碼同一個 commit。分檔裡的路徑相對於各段標題的資料夾；`archive/`、`thinking/`、`docs/`、`notes/` 不列。

| 分檔 | 涵蓋的資料夾 |
|---|---|
| [01-impls](proto8/01-impls.md) | `impls/` 共通建置（`cmake/`、各專案 `CMakeLists.txt`／`vcpkg.json`／`.gitignore`）、`impls/inst/`、`impls/aos-util/`、`impls/aos-directive/`、`impls/aos-schema/`、`impls/aos-exec/` |
| [01-impls-2](proto8/01-impls-2.md) | `impls/aos-loop/`、`impls/aos-fsm/`、`impls/aos-daemon/`、`impls/aos-post/`、`impls/aos-lock/` |
| [01-impls-3](proto8/01-impls-3.md) | `impls/aos-llm-kernel/`、`impls/aos-llm-send/`、`impls/aos-json/` |
| [06-周邊工具](proto8/06-周邊工具.md) | `bin/`、`extras/human/`、`extras/ai_tools/`、`extras/eca/`、`extras/grow/`、`extras/langs/janet/`、`extras/langs/lua/`、`extras/sandbox/` |
| [09-lib](proto8/09-lib.md) | `lib/base/`、`lib/aos/`、`lib/agent/`、`lib/endpoint/` |
| [13-demo](proto8/13-demo.md) | `demo/`（`run.sh`、agent-nia、bob、ann、eve、gus、hal、kai、liv、meg、pip、talk、eca-claude、eca-codex、daemon、daemon-2、daemon-3、tick） |
| [02-tests](proto8/02-tests.md) | `tests/`（共用模組、impls 與 bin、agent 的格與 lib、demo agent、extras、eca） |

依賴由小到大：`inst`（C lib）→ `aos-exec` → `aos-loop`／`aos-fsm` → `aos-daemon`；`aos-util`、`aos-directive`、`aos-schema` 是庫；`aos-post`（連 `aos-lock`）是信箱，aos-daemon、aos-llm-kernel、aos-llm-send 連它。
