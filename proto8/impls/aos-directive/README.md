# aos-directive

`aos-directive - 解 JSON 裡的指示詞（$ref、$env）`（NAME，C-54 R1）

**一句話：解 JSON 裡的指示詞——`{"$ref": "檔#/指標"}` 換成那份檔裡那個位置的值、`{"$env": "名字"}` 換成環境變數的值（可帶 `$path`、`$prefix`）。** 一個 lib（`lib/libaos-directive.a`）加一支命令列（`bin/aos-directive`，不對外提供）。
aos-exec 連這個 lib 解單子、argv 陣列入口與 JSON `.env` key 裡的指示詞（loop／fsm／daemon 的每一次都經 aos-exec）；
10-23 晚起 aos-loop、aos-daemon、aos-fsm 讀設定檔與 ctl 時也用它（使用者「aos 讀的 JSON 全部支援」，N-45；每支程式只解自己讀的格，用 `resolve_shallow` 一層層往下）。全家慣例見 [impls/README.md](../README.md)。
**10-21 照 `proto8/bin/aos_inst.py` 的 resolve 改版**（10-20 ideas D1、D7、D9～D15；N-45）。

```sh
echo '{"argv": {"$ref": "cfg.json", "$at": "/tools/stamp"}, "out": {"$env": "AOS_STACK", "$path": "out", "$prefix": "--o="}}' | aos-directive
# {"argv": ["sh", "-c", "exit 3"], "out": "--o=/ws/.stack/out"}
```

## 用法

### 指示詞

解 JSON 時找出所有帶 `$ref` 或 `$env` 的物件，**整個物件換成它指到的值**；物件裡其餘東西不管（D12）。同一物件兩個都寫只看 `$ref`。

| 寫法 | 換成 |
|---|---|
| `{"$ref": "file.json"}` | 那份 JSON 檔的整份內容（第一行 `#!` 跳過），換進來的值接著解 |
| `{"$ref": "file.json#/a/b"}`、`{"$ref": "file.json", "$at": "/a/b"}` | 檔內那個位置（JSON pointer，`~1`＝`/`、`~0`＝`~`）；兩個都寫＝`$at` 接在 `#/` 後面（D1、D7）。修飾詞都帶 `$`（`$at` 10-23 統合前叫 at；沒帶 `$` 的寫了是普通 key、不作用）。指標取的是檔的原文，取到的值再接著解 |
| `{"$env": "NAME"}` | 環境變數的值 |
| 加 `"$path": "子路徑"` | 換出來是字串時**照字串接上去**（D9；10-21 傍晚 ideas § 9 改，原照 `os.path.join`）：子路徑 `#` 開頭＝直接接（`x.json` ＋ `#/a`＝`x.json#/a`）；空字串＝不接；其他＝去掉值結尾的 `/` 與子路徑開頭的 `/`，中間剛好一個 `/`（子路徑是絕對路徑也是接上去：`/s` ＋ `/abs/p`＝`/s/abs/p`，不再整個取代） |
| 加 `"$prefix": "--file="` | 換出來是字串時接在前面；先接 `$path` 再加 `$prefix`（D10） |

- 換出來不是字串（`$ref` 取到數字、物件…）：`$path`／`$prefix` 靜默不作用（D11）。舊的 `"path"` 已改名，寫了是普通 key、不作用。
- 相對檔名：最外層的 `$ref` 從呼叫者給的 `base_dir` 算（命令列＝cwd）；被 `$ref` 進來的檔裡的 `$ref`，從**那個檔解開捷徑後所在的資料夾**算（使用者 2026-10-17 定）。
- **錯分兩類**（D13～D15）：
  - **真的解不開＝`DirectiveBad`**：環境變數沒設、`$ref` 的檔讀不到（含不是 JSON；**指到資料夾也算讀不到**，不走進去找入口，10-21 傍晚 ideas § 9「維持報錯」）、指標指不到、繞圈（同一個檔＋指標又出現）。
  - **寫法寬容、不報錯**：不認得的 `$xxx`（含 `$fmt`）與其餘 key 不管；`$path`、`$prefix` 不是字串＝當沒寫；`$at` 不是字串、或不是空字串也不是 `/` 開頭＝當沒寫；
    `$ref`／`$env` 的值不是非空字串、`$ref` 的 `#` 後面不是 `/`、只有 `#/…` 沒寫檔名＝換不了，**整個物件原封不動留著**（裡面也不解）。

### 命令列

```
aos-directive < 一份 JSON
```

stdin 一份 JSON（規則同全家：空的＝`{}`、多份＝`InputExtra`、解不出來＝`InputBad`（10-23 統合前叫 JsonSyntax）），以呼叫者的 cwd 為基準解開所有指示詞，
stdout 印一行解好的 JSON、退出 0；出錯 stderr 一行、退出 1。不收任何參數（給了＝`ArgumentsBad`，10-23 統合前叫 Usage）。

## 元素

| 檔 | 做什麼 |
|---|---|
| `include/aos/directive.hpp` | 公開介面：`aos::resolve`、`aos::resolve_shallow`（10-23 晚）、代號 `aos::code::DirectiveBad` |
| `src/resolve.cpp` | 走遍整份 JSON、認出指示詞、分派給 `$ref`／`$env`；換出來是字串再接 `$path`（字串拼接 `join_path`）、加 `$prefix`（`decorate`）；`resolve_shallow`（只換這一格，10-23 晚） |
| `src/ref.cpp` | `$ref`：檢查寫法（不合回 nullopt）、`$at`、從這一層算路徑、判斷繞圈（檔＋指標）、讀檔（跳 `#!`）、照指標取值（`fetch_ref`，取原文）、往下解（`resolve_ref`） |
| `src/env.cpp` | `$env` |
| `src/internal.hpp` | 上面三個檔之間的內部宣告（namespace `aos::directive`：`$ref` 鏈 `Chain`＝（檔, 指標）清單） |
| `src/main.cpp` | 命令列：讀 → `resolve` → 印 |

## 公開介面

```cpp
namespace aos {
namespace code { inline constexpr const char* DirectiveBad = "DirectiveBad"; }
Json resolve(const Json& doc, const std::filesystem::path& base_dir, const std::string& where = "<stdin>");
}
```

```cpp
namespace aos {
struct Resolved { Json value; std::string base_dir; };
Resolved resolve_shallow(const Json& v, const std::filesystem::path& base_dir);   // 10-23 晚
}
```

`Json`、`Error` 來自 [aos-util](../aos-util/README.md)。`base_dir`＝doc 裡相對 `$ref` 的基準；`where`＝錯誤訊息裡說 doc 從哪來。

`resolve_shallow`＝**只換這一格**：`v` 本身是指示詞就換成它指到的值（換來的又是指示詞就再換），**不往物件、陣列裡面走**；回換好的值與「它裡面相對 `$ref` 的起點」
（換過 `$ref`＝最後那份檔解開捷徑後的資料夾；沒換或換的是 `$env`＝`base_dir`）。給「只解自己讀的格」的程式用：讀到哪一層就對那一層呼叫一次，讀的 key 的值再交給 `resolve`。
錯與寬容同 `resolve`。

## 跟 Python 版的差異

照 `proto8/bin/aos_inst.py` 的 `resolve`（10-20 改版；`$path` 照 10-21 傍晚的 `join`）寫，行為一樣；錯誤訊息字面不同、代號一律 `DirectiveBad`。
（舊 `proto8/lib/aos_cli.py` 那代的差異已不適用。）

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- 依賴 [aos-util](../aos-util/README.md)。
- `ctest` 跑 `test_cli`（`tests/test_cli.py`，57 組）：`$ref` 整份、巢狀、捷徑解開；`#/`、`$at`、兩個都寫、舊的 `at` 不作用、`~0~1`、索引前導 0、`#!` 跳過、同檔不同指標不算繞圈；`$env`；
  `$path`／`$prefix`（相對、結尾 `/`、絕對也是接上去、`#` 開頭直接接、兩邊多個 `/`、空字串不接、值是 `/`、null、`$ref` 字串與非字串、舊 `path` 不作用）；寫法寬容（型別不對當沒寫、不認得的 `$xxx`、原封不動十種）；
  `$ref` 指到資料夾（三種寫法）、找不到檔、壞 JSON、繞圈、stdin 空／多份、參數。
