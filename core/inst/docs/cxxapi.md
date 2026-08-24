# C++ API

這份文件回答「C++23 程式如何直接解析、產生、交接與執行 instruction」。如果目標是
操作 `aos` 命令列，請看[使用說明](../../../docs/usage.md)；跨語言或需要穩定 ABI 時看
[C API](capi.md)；handoff 的檔案生命週期與完整例子另見 [handoff](handoff.md)。
外部值指示詞的解析契約與完整例子見 [resolve](resolve.md)。

公開的 C++23 介面由 `<aos/inst.hpp>` 宣告，全部位於 `aos` 命名空間中。C ABI 的
`<aos/inst.h>` 是同一份實作的另一道邊界，兩者可以並存於同一個編譯單元。

## 型別

`inst_t` 代表一筆指令。它的公開成員有 `argv`（一個
`std::vector<std::string>`）、`stdin_path`、`stdout_path`、`stderr_path`、
`exit_path` 與 `cwd`（字串）、`stderr_merge` 與 `parallel`（布林）、`env`（一個
`std::map<std::string,std::string>`），以及 `timeout_ms`（`std::uint64_t`，
預設為零）。兩個布林預設為 false；`clear()` 會把所有成員還原成預設值。

`InstState` 用來回報格式／驗證的結果：`Ok`、`InvalidArgument`、
`JsonSyntax`、`NotAnObject`、`UnknownKey`、`FieldTypeMismatch`、`EmptyArgv`，
`EnvKeyInvalid`、`DirectiveKeyCountInvalid`、`UnknownDirective`、
`DirectiveValueTypeMismatch`，以及 `UnknownOption`。

format 讀到 `$env` 時，會在 `inst_t::pending_directives` 記住種類、位置和變數名稱，
既有字串欄位暫時維持空值。`ResolveContext` 明示環境快照與相對路徑基準；
`ResolveResult` 在失敗時指出欄位、索引或 env key，以及變數名稱。

`ExecState` 包含 `Ok`、
`InvalidArgument`、`SpawnFailed`、`WaitFailed`，以及 `ExitWriteFailed`。
`ExecResult` 包含回報的 `status`、`signalled`、`timed_out`，以及一個
`error`，在相關的 API 失敗時帶著 `errno`。子行程狀態與 API 錯誤兩者的差別，
請參閱[執行語意](exec.md)。

`HandoffState` 回報檔案交接的整體結果，包括成功、參數錯誤、已有 `.runi`、沒有
instruction，以及 inbox／讀取／寫入／rename／釋放失敗。`HandoffResult` 帶出是否
發佈、相關路徑、`errno`，以及可恢復的 `issues`；每個 `HandoffIssue` 會標示壞投遞、
讀取失敗、隔離失敗或發佈後刪除失敗，並附路徑、`InstState` 或 `errno`。

## 函式

`read_all(data, size, out, error_record)` 會解析一整份 JSON 文件。
頂層物件會產生一筆指令；頂層陣列會產生零到多筆指令。它會先清空 `out`，只有在
整份文件與每個物件都有效時，才發佈記錄。發生物件驗證錯誤時，選用的
`error_record` 會收到以一為基底的記錄序號；它一開始被初始化為零，成功、JSON
語法錯誤或無效指標時都維持為零。空輸入是語法錯誤；空陣列
則成功並得到一個空的向量。

`read_one(data, size, out)` 會從這段位元組範圍中，正好解析一個 JSON 值。
它會在檢查或解析之前先清空 `out`。它不接受批次陣列；空緩衝區同樣是語法錯誤。

兩者都**不設任何上限**：位元組數、`argv` 元素數、`env` 條目數、JSON 巢狀深度都
沒有上界。整份輸入都會進到記憶體，所以記憶體用量由輸入大小決定，並由呼叫端的
環境（`ulimit`／cgroup）設界；配置失敗會以 C++ 例外的形式往外傳播，而不是變成
一個 `InstState`。深層巢狀的輸入會讓解析器遞迴爆堆疊而崩潰——請只餵可信來源的
指令檔。

`write_one(inst, out)` 會驗證 `inst`，序列化成緊湊的 JSON 並在最後補上一個 LF，
再把它附加到 `out`。驗證失敗時它不會附加任何東西。維持預設值的選用欄位會被省略。

`write_all(insts, out, error_record)` 是 `read_all` 的反向操作：它把整個批次
序列化成一個緊湊的 JSON 陣列，最後補上一個 LF，再附加到 `out`。空的 vector 會
得到 `[]`，也就是 `read_all` 接受的那個合法空批次。它**先驗證每一筆，才寫出
第一個位元組**——任何一筆無效就完全不動 `out`，並透過選用的 `error_record` 回報
以一為基底的記錄序號（成功時為零）。輸出可以直接餵回 `read_all`。

`resolve(inst, context, result)` 以 `context.environment` 替換所有 `$env`，清除待解析
項目後重新呼叫 `validate(inst)`。不存在的變數回
`EnvironmentVariableMissing`；替換後值不合法回 `ValidationFailed`。失敗時採交易式
語意，原本的 `inst` 不變。`capture_environment(envp, base_path, context)` 可把明示的
POSIX `envp` 複製成 context；它不會套用 instruction 自己的 `env`。

`execute(inst, result)` 會重設 `result`、驗證 `argv` 非空、準備並執行一個子行程、
等待、視情況寫出它的狀態檔，最後回傳一個 `ExecState`。子行程狀態非零時仍然回傳
`ExecState::Ok`。這個非 const 的指令為 `argv` 提供穩定、可變的字元儲存空間；
呼叫者在執行期間不得變動它。
若 instruction 來自 JSON 且含指示詞，呼叫端必須先 resolve；exec 層刻意不知道
指示詞，也不會代替呼叫端檢查。

`aggregate_instructions(path, result)`、`claim_instruction(path, document, result)` 與
`release_instruction(path, result)` 以一個結尾為 `.json` 的 instruction base path
操作完整交接。它們分別推導 `path + ".temp"`、`path + ".runi"`，以及把結尾
`.json` 換成 `.tempd` 的 inbox。聚合只收名字正好為 `<name>.json` 的檔案並按字典序
攤平物件／陣列；壞投遞改名 `.bad` 後繼續，已有 base 時不碰 inbox，發佈成功後才
刪除已接受投遞。缺少或沒有有效記錄的 inbox 是成功 no-op，不會發佈空批次。
這三個 API 不印訊息、不執行 instruction，也不決定 CLI 退出碼。

各狀態列舉（包含 `HandoffState`／`HandoffIssueKind`）的 `to_string` 會回傳指向靜態、以 NUL 結尾的診斷字串的指標，
且為 `noexcept`。

解析、序列化與執行準備都會用到會配置記憶體的 C++ 容器。配置失敗以及其他未預期的
C++ 例外並不會被這個介面轉譯，而可能往外傳播到呼叫者。上述的輸出保證只適用於回傳的
`InstState` 驗證失敗，不適用於例外。

## 範例

```cpp
#include <aos/inst.hpp>

#include <cstring>
#include <string>
#include <vector>

int main() {
    const char input[] =
        "[{\"argv\":[\"printf\",\"hello\\n\"],\"exit\":\"status.txt\"}]";
    std::vector<aos::inst_t> jobs;
    std::size_t record = 0;
    if (aos::read_all(input, std::strlen(input), jobs, &record) !=
        aos::InstState::Ok) return 1;

    for (auto &job : jobs) {
        aos::ExecResult result;
        if (aos::execute(job, result) != aos::ExecState::Ok) return 2;
        if (result.status != 0) return result.status;
    }

    std::string encoded;
    return aos::write_one(jobs.front(), encoded) == aos::InstState::Ok ? 0 : 3;
}
```

對著共享函式庫建置，從儲存庫根目錄、建置目錄為預設的 `build/` 時例如：

```sh
c++ -std=c++23 example.cpp -Icore/inst/include -Icommon/include \
    -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst -o example
./example
```

會看到：

```text
hello
```

同時目前目錄會出現內容為 `0` 加換行的 `status.txt`。

如果用戶端本身也是 CMake 專案，改用 `find_package(aos CONFIG REQUIRED)` 再連
`aos::inst` 更省事（見[架構](architecture.md)）——上面這行手動旗標是給不透過
CMake 的場合用的。

## 執行緒與選擇 ABI

各自獨立的 `inst_t` 物件可以並行地使用。`execute` 適合用在多執行緒的行程裡，
因為所有會配置記憶體的環境與 PATH 準備都發生在 `fork` 之前；子行程在 `execve`
之前只使用 async-signal-safe 的操作。對於共用同一筆指令、同一個輸出字串／向量，
或借用來的應用程式狀態，並沒有任何內部的同步機制：不要並行地變動同一批物件，
也不要在一筆指令執行的過程中去改它。

C++ API 與 C API 揭露的是同一套指令、格式、執行結果與上限。若想要直接存取容器，
以及具原子性的多記錄 `read_all`，就選 C++。若想要以 opaque
handle 管理所有權、明確的配置失敗狀態、給 C 或其他 FFI 語言使用，或需要一個穩定的
二進位邊界，就選 C API。

C++ 介面**不**保證跨版本之間的 ABI 相容性。它匯出的簽章與佈局裡含有 `std::string`、
`std::vector`、`std::map`，以及編譯器特定的 C++ ABI 細節。要跨越編譯器、標準函式庫、
語言或版本邊界的程式碼，應該改用 `<aos/inst.h>` 與 C ABI。
