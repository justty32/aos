# code map — core/tooljson/

← [code map 總圖](../code-map.md)｜[本資料夾導覽](README.md)

`core/tooljson/` 這個小專案的逐檔職責：公開 API、內部邊界、spec／registry／exec_type／args 等實作檔、CLI 與測試。
**新增／刪除 `core/tooljson/` 底下的原始碼或測試檔，就在這一份加／減那一列。**

---

## core/tooljson/ — tool spec 外殼與參數展開

讀取格式版本 `0.1.0` 的 OpenAI tool JSON 加 `_extra`，在載入時驗證外殼與 exec
配方，並把模型給的參數純函式地展開成 argv／stdin。S1 完全不 fork、不 exec；
對外是 `aos::tooljson`（`libaos_tooljson.so`）與只提供 `list`／`check` 的
`aos tooljson` 子命令。

| 檔案 | 負責 |
|------|------|
| `include/aos/tooljson.hpp` | 不含 nlohmann 的公開 C++ API：`Spec` pimpl、`SpecState`、字串 JSON 的 load/save、開放 registry、`ExpandedArgs` 與文字收尾函式；所有公開函式與 out-of-line 成員都標 `AOS_API` |
| `src/tooljson_internal.hpp` | 只供本小專案使用的 nlohmann 邊界、`Spec::Impl`、exec binding/body 與內部存取器 |
| `src/spec_internal.hpp` | 三個 `spec*` 檔共用的內部宣告：格式版本常數、把訊息塞進 out 參數的 `fail()`、`parse_one()` |
| `src/spec.cpp` | `Spec` pimpl 的對外成員（name／schema_json／run／stale 等）、`SpecState` 與版本字串，以及 `json_repr`／`resolve_path` 兩個共用小工具 |
| `src/spec_parse.cpp` | 單一份 tool 物件的解析：外殼兩個保留鍵、`_extra._version`／`_type` 派發到 parser、function schema 的 properties／required 驗證 |
| `src/spec_load.cpp` | 文件層的載入與存檔：讀檔、object／array 兩種入口、單檔撞名、跨檔先到先贏、相對路徑中心的計算，與縮排寫回 |
| `src/registry.cpp` | 執行環境的 `_type` → parser 開放登記表；同名覆蓋、排序列出目前型別 |
| `src/exec_internal.hpp` | 四個 `exec*` 檔共用的內部宣告：單項 argv 上限常數、`bad()`／`unknown_keys()` 等小工具與三個分段解析函式 |
| `src/exec_type.cpp` | 內建 `exec` parser 的 registry 登記與解析入口（依序叫三個分段），共用小工具的實作，以及 `ExecBody` 的 `target()` PATH 查找與 S1 只回尚未實作字串的 `run()` |
| `src/exec_argv.cpp` | `_extra.exec` 與 `_extra.argv` 的載入期驗證：程式路徑解析、各參數的 position／flag／separate／repeat 與排序 |
| `src/exec_io.cpp` | `_extra.stdin`／`stdout`／`stderr` 三條標準串流接法的載入期驗證 |
| `src/exec_limits.cpp` | `_extra.ok_exit`／`timeout`／`cwd`／`limits`／`source` 的載入期驗證與 cwd 路徑解析 |
| `src/args_internal.hpp` | `args*` 兩檔共用的單值處理宣告：`render`／`coerce`／`schema_type`／`truthy`／`numeric`／`json_type_name` |
| `src/args.cpp` | 模型 args JSON → argv + stdin 的純函式主流程；未知／缺少參數、limits 檢查、flag/repeat/separate 展開與單項 128KB 上限 |
| `src/args_value.cpp` | 單一 JSON 值的處理：argv 字串化、照 schema 型別把字串 coerce 回數字／布林、真值判斷與 Python 風格型別名 |
| `src/text.cpp` | 輸出 UTF-8 解碼、NUL 二進位偵測，以及按 Unicode 字元計數的 head／tail 裁切 |
| `src/fingerprint.cpp` | 不依賴外部雜湊函式庫的串流 SHA-256；供 `Spec::stale()` 比對 `_extra.source.sha256`，讀不到時回「不知道」 |
| `src/run.hpp`／`src/run.cpp` | CLI 層與 `aos_tooljson_cli_main`；只透過公開 API 實作 `aos tooljson list`／`check`，是 CLI 的配置失敗例外邊界 |
| `CMakeLists.txt` | 建 `aos::tooljson`、CLI OBJECT library、登記 `tooljson` 子命令與 `aos_tooljson_tests` |

### core/tooljson/tests/ — 測試

| 檔案 | 涵蓋 |
|------|------|
| `test_support.hpp` | 建立 exec spec、暫存檔與目錄的共用測試工具 |
| `test_spec.cpp` | object／array、版本、同檔與跨檔撞名、schema 剝除、以 spec 位置解析路徑、save/load、source 指紋 stale 三態 |
| `test_validation.cpp` | function schema 與 exec 的 argv／stdio／runtime／limits 載入期壞檔案例 |
| `test_registry.cpp` | 未知與 python 型別訊息、第三方字串 JSON parser/body、內建 exec 同門登記 |
| `test_args.cpp` | position＋Unicode 排序、JSON 字面、flag/repeat/separate、coerce、null／缺席、stdin、未知參數與 byte limits |
| `test_text.cpp` | NUL 二進位、無效 UTF-8、head／tail 與 Unicode 字元裁切 |
| `test_run.cpp` | `list`／`check` 成功與失敗，以及 S1 不接受 `run` |

細節契約與 C++ registry 的 JSON 邊界見 `core/tooljson/docs/format.md`。
