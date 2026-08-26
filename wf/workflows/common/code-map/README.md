# code map 各分冊導覽

← [code map 總圖](../code-map.md)（頂層結構圖、單向相依鐵律、快速索引都在那裡）

這個資料夾是 code map 的逐檔表格部分，**按小專案分冊**。要找「某個檔負責什麼」，先看下表選一冊。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|------|-----------|---------------|
| [inst.md](inst.md) | `core/inst/` 這一冊的**入口**：小專案總述、「新增一個 instruction 欄位」的維護鏈，以及指向 [`inst/`](inst/README.md) 底下 library／capi／cli／tests 四份逐檔表格的路由 | 要改 instruction 結構、format／resolve／handoff／exec、C ABI 或 `aos init`／`aos exec` CLI |
| [tooljson.md](tooljson.md) | `core/tooljson/` 的公開 API、內部邊界、spec／registry／exec_type／args／text／fingerprint、CLI 與測試逐檔表格 | 要改 tool spec 驗證、`_type` registry、argv 展開或 `aos tooljson` CLI |
| [llms.md](llms.md) | `core/llms/` 的公開 API、內部邊界、content／params／transport／SSE／caps／Reply／Bot／presets、CLI 與測試逐檔表格 | 要改 LLM client、串流、toolset、presets 或 `aos llms` CLI |
| [build.md](build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |

**新增或刪除原始碼檔案時**：檔案在哪個小專案底下，就去那一冊的表格加／減那一列（`common/`、`app/`、建置設定檔一律進 `build.md`）。這是 AGENTS.md「改了程式碼就要同步 code map」那條鐵律的落點。
