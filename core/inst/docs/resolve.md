# 指示詞解析

這份文件回答「為什麼 instruction 需要在 JSON 解析後再做一次 resolve、`$env` 如何
取得值、`$ref` 如何跨檔取值，以及 C++ 呼叫端怎麼知道哪裡失敗」。它不說 JSON 的
全部欄位（見[記錄格式](format.md)），也不執行行程（見[執行語意](exec.md)）。

## 為什麼另設 resolve

**指示詞（directive）**是產生某個欄位值的單鍵 JSON 物件，例如
`{"$env":"TARGET"}` 或 `{"$ref":"shared.json#/target"}`。format 層只負責辨認
這個語法，不能自行偷讀行程環境或額外檔案；exec 層
則只該收到可直接執行的字串，不能知道指示詞存在。因此兩者之間有一個公開的
**resolve（解析值）**步驟：

```text
JSON bytes → read_one/read_all → 未解析 inst_t → resolve → 可執行 inst_t → execute
```

未解析的 `inst_t` 仍保留既有字串欄位型別。額外的 `pending_directives` 逐項記住指示詞
種類、所在欄位、`argv` 索引或 `env` key，以及環境變數名稱；沒有用特殊字串冒充
指示詞。因此字面值永遠不需要跳脫，`write_one`／`write_all` 也能把尚未解析的物件
原樣寫回。

## `$env` 從哪個環境取值

`$env` 讀的是呼叫端明確交給 `ResolveContext::environment` 的環境快照，不是該筆
instruction 的 `env` 欄位。`ResolveContext::base_path` 同時明示未來解析相對路徑時的
基準。`$env` 不使用路徑，`$ref` 的相對路徑則一定從這個基準起算；API 不把選擇
藏在目前目錄或 instruction 檔的位置裡。

CLI 的 `aos exec` 會在每批 instruction 解析完成後捕捉自己的父行程環境，接著逐筆
resolve，全部成功才開始執行。變數存在但值是空字串和「變數不存在」不同：前者會被
替換成空字串，然後接受正常的值驗證；後者直接回
`EnvironmentVariableMissing`。

可使用 `$env` 的位置是每個 `argv` 元素、`stdin`、`stdout`、`stderr`、`exit`、
`cwd`，以及 `env` 的值。`env` 的 key 是 JSON 物件 key，只能是字面字串；
`timeout_ms` 仍只接受無號整數。`stderr` 另外保留字面路徑和
`{"$opt":"merge"}`，所以三種形式互不混淆。

## `$ref` 如何取值

`{"$ref":"shared/values.json#/build/target"}` 先以 `base_path` 解出檔案，再用 `#`
後面的 **JSON Pointer** 取值。JSON Pointer 是 RFC 6901 定義的 JSON 內部路徑；例如
`/a~1b/~0key` 代表 key `a/b` 底下的 key `~key`。沒有 `#` 時取整份文件，因此頂層
是 JSON 字串時合法，頂層是陣列或物件時會遇到型別錯誤。

核心規則是：**取回來的值就當成原本寫在目標位置。** 字串直接填入；如果取到另一個
`$ref` 或 `$env`，就繼續解析；取到 `{"$opt":"merge"}` 時只有 `stderr` 合法。
陣列與一般物件不能展開成多個 `argv` 元素，也不能改變 instruction 結構。絕對路徑、
`..` 與 base_path 外的檔案沒有額外拒絕清單，實際可讀範圍就是行程權限。

### 深鏈與循環

巢狀引用沒有固定深度上限，但每次進入 `$ref` 都會記錄一個引用身分：

```text
正規化後的絕對檔案路徑 + JSON Pointer
```

檔案先經 `weakly_canonical` 正規化，所以 `a.json` 與 `./a.json` 不能假裝是不同檔案。
同一條解析鏈再次遇到相同身分就是循環；同檔案的 `/x` 再引用 `/y` 則是不同身分，
合法。`ResolveResult::reference_chain` 會保留從第一個引用到重複節點的完整鏈，診斷
可以直接顯示哪一段繞回去了。

## 驗證與錯誤位置

format 遇到仍是指示詞的 `argv[0]` 時只驗語法，不對暫存的空字串判錯。resolve 會在
所有替換完成後清掉待解析項目，再呼叫 `validate()`；例如環境變數存在但內容為空，
此時才得到 `ValidationFailed`，而 `ResolveResult::validation_state` 是 `EmptyArgv`。

`ResolveState` 除了 `Ok`、`InvalidArgument`、`EnvironmentVariableMissing`、
`ValidationFailed`，另有 `ReferenceReadFailed`、`ReferenceJsonInvalid`、
`ReferencePointerInvalid`、`ReferenceValueInvalid` 與 `ReferenceCycle`。失敗時
`ResolveResult` 會帶出
`field`、`argv_index` 或 `env_key`、變數名稱 `variable`，以及需要時的
`validation_state`；引用錯誤另帶 `reference_path`、`pointer`、`reference_chain` 與
檔案 I/O 的 `errno`。resolve 是交易式操作：任何替換或驗證失敗，傳入的 `inst_t`
維持未解析狀態。

## 可直接執行的 C++ 範例

把以下內容存成 `/tmp/aos-resolve-example.cpp`：

```cpp
#include <aos/inst.hpp>

#include <cstdio>
#include <cstring>

int main() {
    const char json[] =
        R"({"argv":["printf","target=%s\n",{"$ref":"/tmp/aos-resolve-values.json#/target"}]})";
    aos::inst_t job;
    if (aos::read_one(json, std::strlen(json), job) != aos::InstState::Ok)
        return 1;

    aos::ResolveContext context;
    context.base_path = ".";
    aos::ResolveResult resolved;
    const auto state = aos::resolve(job, context, resolved);
    if (state != aos::ResolveState::Ok) {
        std::fprintf(stderr, "%s: %s\n", aos::to_string(resolved.field),
                     aos::to_string(state));
        return 2;
    }

    aos::ExecResult executed;
    return aos::execute(job, executed) == aos::ExecState::Ok
               ? executed.status : 3;
}
```

先建立被引用的檔案，再從儲存庫根目錄編譯並執行：

```sh
printf '%s\n' '{"target":"staging"}' > /tmp/aos-resolve-values.json
c++ -std=c++23 /tmp/aos-resolve-example.cpp \
  -Icore/inst/include -Icommon/include -Lbuild/lib \
  -Wl,-rpath,"$PWD/build/lib" -laos_inst -o /tmp/aos-resolve-example
/tmp/aos-resolve-example
```

輸出是：

```text
target=staging
```
