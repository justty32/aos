# 使用說明

← [文件索引](README.md)｜[總覽](overview.md)｜[建置](build.md)

這份文件回答「第一次接觸 aos，要怎麼把一個資料夾跑起來，以及程式如何連它的
函式庫」。它不逐項定義 instruction schema 或 POSIX 執行細節；需要時分別查
[`format.md`](../core/inst/docs/format.md)、[`exec.md`](../core/inst/docs/exec.md) 與
[`handoff.md`](../core/inst/docs/handoff.md)。環境指示詞的函式庫契約見
[`resolve.md`](../core/inst/docs/resolve.md)。

aos 有兩種用法，背後是同一份實作。

---

# 一、當命令列工具用

只有一支執行檔 `aos`，每個小專案是它的一條子命令。

```bash
$ aos --help
usage: aos <command> [args...]

commands:
  exec         推進一個 aos 資料夾的一回合
  init         初始化一個 aos 資料夾
```

不給子命令、或給了不認得的名字，都會印出這張表並回 exit code 2。

## `aos init` 與 `aos exec` —— 初始化並推進一回合

這裡的 **world** 是一個由普通資料夾和其中 `.aos/` 本機執行狀態組成的工作空間。
一個**回合**是：取走當下的一批 instruction、全部執行完成，再清除「正在執行」標記。
instruction 是描述一支 POSIX 命令的 JSON；它和 shell script 一樣具有執行程式的權限。

```bash
aos init my-world
printf '%s\n' '{"argv":["echo","hello"],"stdout":"hello.txt"}' \
  > my-world/.aos/inst.json
aos exec my-world
```

`aos init [folder]` 要求 folder 已存在，建立 `.aos/`、`inst.tempd/` inbox 並寫入版本 `1`。若 `.aos/`
已存在會明確拒絕，不會覆寫。整個 `.aos/` 都是本機執行狀態，應加入 `.gitignore`。
省略 folder 時使用目前目錄 `.`。

`aos exec [folder]` 會先依檔名的字典序聚合 `.aos/inst.tempd/<name>.json`，再讀取
`.aos/inst.json`；每份投遞可以是**一個** JSON 物件，或**一個陣列**
的物件。檔案會先完整讀入並立刻 rename 成 `inst.json.runi`，然後整批驗證；所以第 5
筆有語法錯誤時前 4 筆不會執行。回合正常返回後（包含退出碼 1）會刪除 `.runi`；只有
crash、被 kill 或斷電才會留下它。沒有 `inst.json` 是正常的空回合，安靜回 0；若啟動
時 `.runi` 已存在則拒絕並回 3。

聚合只接受恰好一個副檔名的 `<name>.json`；`.temp`、`.bad` 與 `name.part.json` 都
不會被取走。語法或 schema 錯誤的投遞會改名為 `.bad`、印警告，其他有效投遞仍會
發佈。已有 `inst.json` 時會先執行它並保留 inbox，留待下一回合；有效批次發佈完成
後才刪除其來源投遞，空 inbox 不會製造 `[]`。

**投遞**是生產者放進 `inst.tempd/` 的一份待辦 JSON；**彙整**是把多份有效投遞攤平
成下一個 `inst.json` 批次；**取件**是把它 rename 成 `.runi`，防止另一個執行者重複
取走。完整的檔案狀態與公開 API 見 [handoff 指南](../core/inst/docs/handoff.md)。

上面的第一個例子完成後沒有 stdout；結果在檔案裡：

```bash
cat my-world/hello.txt
```

```text
hello
```

要讓呼叫 `aos exec` 的 shell 在執行前填入一個值，可用 `$env` 指示詞。它讀的是
**解析當下的父行程環境**，不是同一筆 instruction 的 `env` 欄位；變數不存在會讓
整批在任何命令啟動前失敗：

```bash
export AOS_GREETING='hello from environment'
printf '%s\n' '{"argv":["printf","%s\\n",{"$env":"AOS_GREETING"}],"stdout":"env.txt"}' \
  > my-world/.aos/inst.json
aos exec my-world
cat my-world/env.txt
```

```text
hello from environment
```

另一種做法是用 `$ref` 從 world 裡的另一份 JSON 取一個值。`#` 後面是 JSON Pointer，
用來指出檔案內的位置；相對檔名以 world 為基準：

```bash
printf '%s\n' '{"message":"hello from reference"}' > my-world/values.json
printf '%s\n' '{"argv":["printf","%s\\n",{"$ref":"values.json#/message"}],"stdout":"ref.txt"}' \
  > my-world/.aos/inst.json
aos exec my-world
cat my-world/ref.txt
```

```text
hello from reference
```

引用取回另一個 `$ref` 或 `$env` 時會繼續解析，沒有固定深度限制；但同一條鏈再次
遇到相同的「正規化檔案路徑＋pointer」會以循環錯誤停止。完整規則與可修正的錯誤資料
見 [resolve 指南](../core/inst/docs/resolve.md)。

要持續推進同一個 world，使用毫秒為單位的 loop 模式：

```bash
aos exec --loop 1000 my-world
```

間隔只用於空回合：有工作時會立刻進下一輪；沒有 instruction 或可彙整投遞時才等待。
`--loop 0` 合法，但會 busy poll。回合回 0 或 1 都會繼續（1 的診斷已印到 stderr）；
遇到既有 `.runi` 則停止並回 3。第一次 `SIGINT`／`SIGTERM` 會喚醒等待，並讓正在跑的
回合完成及釋放 `.runi` 後正常回 0；再送一次同樣的信號則採預設處置立即終止。
單回合與 loop 都可省略 folder，省略時使用目前目錄 `.`。

```json
[
  {
    "argv": ["/bin/sh", "-c", "printf 'hello\\n'"],
    "stdout": "hello.txt",
    "exit": "hello.status"
  },
  {
    "argv": ["/bin/sh", "-c", "sleep 30"],
    "timeout_ms": 500
  }
]
```

常用欄位：`argv`（必要，不可為空）、`stdin` / `stdout` / `stderr`（重導向到
檔案）、`exit`（把 exit code 寫進這個檔）、`cwd`、`env`、`timeout_ms`。
**完整 schema 與每個欄位的語意見 [`core/inst/docs/format.md`](../core/inst/docs/format.md)；
執行語意（逾時怎麼算、訊號怎麼送、exit code 怎麼對應）見
[`core/inst/docs/exec.md`](../core/inst/docs/exec.md)。**

所有相對路徑，以及未指定 `cwd` 時的子行程工作目錄，都以 `<folder>` 為基準。

### 退出碼：注意，它不反映子行程的成敗

這點很容易誤會。`aos exec` 的退出碼只回答「**這一回合有沒有正常跑完**」，不回答
「你叫它跑的那些指令有沒有成功」。

| 情況 | `aos exec` 的退出碼 |
|------|-------------------|
| 全部順利 | `0` |
| 子行程回非零、指令不存在、逾時被砍、重導向的檔開不起來 | **`0`** |
| 指令檔語法或 schema 有問題（一筆都沒執行）| `1` |
| aos 自己失敗了：`fork` 失敗、`waitpid` 失敗、`exit` 檔寫不進去 | `1` |
| 用法錯誤（沒給子命令、給了不認得的名字）| `2` |
| `.aos/inst.json.runi` 已存在 | `3` |

loop 正常因信號收尾回 0；曾出現回合錯誤 1 不改變最後的 loop 退出碼，只有遇到 `.runi`
才以 3 停止。

```bash
$ printf '{"argv":["/bin/false"]}' > my-world/.aos/inst.json
$ aos exec my-world ; echo $?
0
```

**要拿到子行程的結果，用 `exit` 欄位**——那正是它存在的理由：

```json
{"argv": ["/bin/false"], "exit": "job.status"}
```

跑完 `job.status` 裡會是 `1`。

批次執行時，單筆的 `ExecState` 失敗會印到 stderr 但**不會中止**後面的，最後整體
回 1。

> **指令檔必須是可信來源。** 它沒有任何大小限制，可以指名任意程式與環境變數，
> 並以你的身分執行。把它當成可執行檔看待。

---

# 二、當函式庫用

先[安裝](build.md#安裝)，然後：

```cmake
find_package(aos CONFIG REQUIRED)
target_link_libraries(myapp PRIVATE aos::inst)
```

```cpp
#include <aos/inst.hpp>
```

如果 aos 沒裝在預設路徑，configure 時給 `-DCMAKE_PREFIX_PATH=<你的 prefix>`。

## 可以連的 target

| target | 內容 | 什麼時候用 |
|--------|------|-----------|
| `aos::inst` | 只有 inst 這個小專案（`libaos_inst.so`）| 一般情況，只拿你要的 |
| `aos::core` | 傘狀：所有**核心**小專案（`core/`）| 要 aos 的基本功能，不要擴充 |
| `aos::modules` | 傘狀：所有**擴充**小專案（`modules/`）。沒有擴充時不存在 | 少見 |
| `aos::aos` | 傘狀：全部小專案 | 懶得挑 |
| `aos::merged` | 合併版 `libaos.so`，所有小專案在同一顆檔案裡 | 想單檔部署。需要建置時開 `AOS_BUILD_MERGED_LIB=ON` |

`aos::merged` 是真的自成一體——即使小專案之間互相依賴，連了它就不會再被要求去連
個別的 `libaos_<name>.so`。

## 一個完整的例子

```cpp
#include <aos/inst.hpp>

#include <cstdio>
#include <string>
#include <vector>

int main() {
    aos::inst_t job;
    job.argv = {"/bin/sh", "-c", "printf 'hi\\n'"};
    job.stdout_path = "out.txt";
    job.timeout_ms = 1000;

    // 寫成 JSON
    std::string encoded;
    if (aos::write_one(job, encoded) != aos::InstState::Ok) {
        return 1;
    }

    // 讀回來
    std::vector<aos::inst_t> jobs;
    std::size_t bad = 0;
    const aos::InstState state =
        aos::read_all(encoded.data(), encoded.size(), jobs, &bad);
    if (state != aos::InstState::Ok) {
        std::fprintf(stderr, "record %zu: %s\n", bad, aos::to_string(state));
        return 1;
    }

    // 執行
    aos::ExecResult result;
    const aos::ExecState exec_state = aos::execute(jobs.front(), result);
    std::printf("%s status=%d timed_out=%d\n", aos::to_string(exec_state),
                result.status, static_cast<int>(result.timed_out));
    return 0;
}
```

`inst` 的公開介面分五層，相依單向 `inst ← format ← handoff`、
`inst ← format ← resolve` 與 `inst ← exec`：`inst_t` 與狀態列舉、
`read_*`/`write_*`（唯一懂 JSON schema 的一層）、指示詞解析、檔案交接 API，以及
`execute()`（唯一碰 `fork`/`exec` 的一層）。resolve、handoff 與 exec 互不相依；
宣告併在同一個標頭裡**不代表它們可以互相引用**。
逐項說明見 [`core/inst/docs/cxxapi.md`](../core/inst/docs/cxxapi.md)。

## 錯誤處理的契約

C++ API **會丟例外**：記憶體配置失敗時是 `std::bad_alloc` / `std::length_error`，
不是回傳值。狀態碼（`InstState` / `ExecState`）只表達「輸入有問題」或「執行沒
成功」。要在配置失敗時也保持穩定的呼叫者，得自己 catch。

## C ABI

需要跨語言或跨編譯器邊界時，改用 C ABI：

```c
#include <aos/inst.h>
```

它相容 C99、不含任何 C++ 型別，而且**每個進入點都會把例外接成錯誤碼**
（`AOS_INST_ALLOC_FAILED` 等），例外不會逸出 `extern "C"` 邊界。同一個編譯單元
裡 `<aos/inst.h>` 與 `<aos/inst.hpp>` 可以並存。

列舉值一經釋出就凍結——只能在尾端加新值，不能重排或刪除。完整說明與範例見
[`core/inst/docs/capi.md`](../core/inst/docs/capi.md)。

目前只有 `inst` 提供 C ABI，其餘小專案會陸續補上。

## 不透過 CMake 的話

```bash
# 對著已安裝的 prefix
cc -std=c99   example.c   -I<prefix>/include -L<prefix>/lib -laos_inst
c++ -std=c++23 example.cpp -I<prefix>/include -L<prefix>/lib -laos_inst
```

對著**尚未安裝**的建置樹則要兩個 `-I`（公開標頭與 `<aos/export.h>` 分屬不同
目錄，安裝後才會合流），並補上 rpath：

```bash
c++ -std=c++23 example.cpp -Icore/inst/include -Icommon/include \
    -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst
```
