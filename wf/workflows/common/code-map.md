# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。


## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| instruction 有哪些欄位、JSON 長什麼樣 | `inst/include/aos/inst.hpp` 的 `inst_t`；schema 細節在 `inst/src/format.cpp` 的 `known_key`／`encode`／`decode` |
| exit code、逾時、行程群組怎麼處理 | `inst/src/exec.cpp` |
| PATH 怎麼解析、環境變數怎麼合併 | `inst/src/spawn_prep.cpp` |
| C ABI 怎麼對應到 C++ API | `inst/src/capi.cpp` 開頭的 `static_assert` 一串 |
| CLI 怎麼讀輸入、怎麼跑一批 instruction | `inst/src/run.cpp` |
| 為什麼要先把整份輸入讀完才開始執行 | `inst/docs/architecture.md`「為什麼要先把整份輸入讀完」|
| `fork` 前後各自能做什麼 | `inst/docs/architecture.md`「`fork` 兩側各自要做的工作」；程式碼在 `inst/src/exec.cpp` 的 `run_child` |
| 新增一個小專案（像 inst 那樣）要照什麼模子 | `cmake/AosSubproject.cmake` 的 `aos_add_subproject()`（目前唯一的範例是 `inst/`）|
