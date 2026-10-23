# aos-schema

**一句話：拿一份 JSON Schema（draft-07）去檢查一份 JSON，告訴你「哪一格、哪裡不對」——有 C++ 函式庫，也有命令列。**
全家慣例（stdin、錯誤格式、建置）見 [impls/README.md](../README.md)。

像海關查行李：schema 是「哪些東西可以帶、要長怎樣」的規定，你的 JSON 是行李。查完給你一張清單：
沒問題就是空的；有問題就列出「哪一格（JSON pointer）＋為什麼」。

```sh
$ echo '{"argv": ["echo", 3], "grace_ms": -1}' | bin/aos-schema examples/inst.schema.json
{"valid": false, "problems": [{"pointer": "/argv/1", "message": "unexpected instance type"}, {"pointer": "/grace_ms", "message": "instance is below minimum of 0"}]}
$ echo $?
0
```

## 用法

```sh
aos-schema SCHEMA檔 < doc.json
```

stdin 讀一份 JSON（規則同全家：空的＝`{}`、多份＝`InputExtra`、壞尾丟掉），用 SCHEMA檔 驗，stdout 印一行
`{"valid": true/false, "problems": [{"pointer", "message"}, ...]}`。**驗不過也退 0**（那是答案，不是錯）。工具自己出錯才往 stderr 印錯誤、退 1：

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad` | 參數不是剛好一個 |
| `SchemaMissing` | SCHEMA檔 不在（只有這支會吐的代號） |
| `InputBad` | stdin 不是合法 JSON |
| `InputExtra` | stdin 有好幾份 JSON |
| `SchemaBad` | SCHEMA檔 讀不了或不是合法 JSON、schema 不合 draft-07、或 `$ref` 指不到（只有這支會吐的代號） |
| `Internal` | 照理不會發生的例外 |

代號照 [10-23 命名統合](../../thinking/2026-10-23-naming.md)：`ArgumentsBad`（10-23 統合前叫 Usage）、`SchemaMissing`／`SchemaBad`（SCHEMA檔讀不到、不是 JSON，10-23 統合前叫 ReadFailed／JsonSyntax）、`InputBad`（stdin 不是 JSON，10-23 統合前叫 JsonSyntax）。

沒有其他旗標。

## 元素

| 檔 | 做什麼 |
|---|---|
| `include/aos/schema.hpp` | 公開介面：`Problem`、`load_file`、`validate`、代號 `SchemaMissing`、`SchemaBad` |
| `src/load_file.cpp` | 檔 → `nlohmann::json`（不在＝SchemaMissing、讀不了或不是 JSON＝SchemaBad） |
| `src/validate.cpp` | **整個專案唯一碰 pboettch/json-schema-validator 的檔**：先拿 draft-07 的 meta-schema 驗 schema 本身 → 編 schema → 驗 doc、每個錯收成一個 `Problem` |
| `src/main.cpp` | 命令列：讀 → `load_file` → `validate` → 印 |
| `examples/inst.schema.json` | 示範 schema：一張 inst 的欄位，照 `proto8/lib/aos_inst.py` 的 `parse()` 寫 |

整個專案在 namespace `aos::schema`。

## 公開介面（`include/aos/schema.hpp`）

```cpp
namespace aos::schema {
using Error = aos::Error;                                         // aos-util 的 {code, msg}
struct Problem { std::string pointer; std::string message; };     // 一個驗不過的地方

nlohmann::json load_file(const std::filesystem::path&);           // SchemaMissing／SchemaBad
std::vector<Problem> validate(const nlohmann::json& schema,
                              const nlohmann::json& doc);         // 空＝通過；schema 壞＝SchemaBad
}
```

- 「驗不過」是資料：回 `Problem` 清單，不丟例外。全部收齊，不在第一個錯就停。
- 「工具自己出錯」才丟 `Error`。`pointer` 是 JSON pointer 字串，整份＝`""`，例如 `/argv/1`。
- 標頭只露 `nlohmann::json`（不是全家用的 `aos::Json`＝ordered_json：驗證器只收前者，`aos::Json` 傳進來會自動轉）與 std 型別；
  pboettch 只出現在 `src/validate.cpp`，換驗證器只改那個檔。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- 依賴 [aos-util](../aos-util/README.md)；vcpkg 比全家多一個 [pboettch/json-schema-validator](https://github.com/pboettch/json-schema-validator) 2.4.0（`vcpkg.json`）。
  別的專案要連 `aos-schema`，那邊的 `vcpkg.json` 也要列 `json-schema-validator`（manifest 只看最上層專案）。
- `ctest` 跑 `test_lib_*`（`tests/test_lib.cpp`：一個執行檔、第一個參數挑哪一條，8 條）和 `test_cli`（`tests/test_cli.py`：餵 stdin 看輸出，12 案）。測試資料在 `tests/data/`。

## 已知限制

- 錯誤訊息是驗證器給的英文（`unexpected instance type` 這種），不翻。
- 有些錯報在上一層：`required` 缺欄位報在物件本身（缺 `argv` 報 `""`、不是 `/argv`）；
  `additionalProperties` 的子 schema 驗不過也報在物件（`envs` 裡 `"A": 1` 報 `/envs`，訊息裡才寫 `'A'`）。
- `$ref` 只認同一份檔內（`#/definitions/x`）；外部檔、網址都不讀，會變 `SchemaBad`。
- 只認 draft-07。`format` 用驗證器內建的檢查（date-time、email、ipv4…），認不得的 format 不算 schema 壞，而是每個用到它的值都報一條 `format-checking failed: Don't know how to validate …`。
- 每次 `validate()` 都重編一次 schema；量大再說。
- schema 不合 draft-07 時只報第一個問題。
