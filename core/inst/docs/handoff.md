# Instruction 交接協定

這份文件回答：「多個生產者把工作交給一顆執行 CPU 時，檔案怎麼安全地彙整、取走與
釋放？」它說明 `aos::inst` 公開的 handoff API 與磁碟狀態；JSON 欄位請看
[記錄格式](format.md)，子行程如何執行請看[執行語意](exec.md)，CLI 的完整入門則看
[使用說明](../../../docs/usage.md)。

## 為什麼需要獨立的 handoff 層

一個 aos world（由某個資料夾及其 `.aos/` 執行狀態組成的工作空間）可能同時有多個
工作生產者。生產者不能一起覆寫同一份 `inst.json`，否則後寫者會吃掉先寫者的工作；
未來不同的抽象 CPU 也會各有自己的 instruction 檔，需要完全相同的交接步驟。

handoff 因此只接受一個 instruction base path，例如 `.aos/inst.json` 或
`.aos/insts/llm.json`，並負責三件事：

1. **投遞與彙整**：投遞是生產者放進 inbox 的一份待辦 JSON；彙整是把多份有效投遞
   攤平成一個批次，再原子發布成 base path。
2. **取件**：把 base path 改名為 `.runi`，表示這一批已被某個回合占有。回合就是一次
   「取走一批、全部執行、清掉執行中標記」的完整處理。
3. **釋放**：回合正常返回後刪除 `.runi`。

它不印 stdout／stderr、不決定 CLI 退出碼，也不執行 instruction。呼叫端可以自行把
結構化結果映成自己的 UI 或錯誤政策。

## 路徑怎麼推導

以 `/srv/demo/.aos/inst.json` 為例：

| 用途 | 路徑 |
|---|---|
| base：下一批等待取件的 instruction | `/srv/demo/.aos/inst.json` |
| 發布中的暫存檔 | `/srv/demo/.aos/inst.json.temp` |
| 已取件、正在處理 | `/srv/demo/.aos/inst.json.runi` |
| inbox：生產者投遞目錄 | `/srv/demo/.aos/inst.tempd/` |

base 必須以 `.json` 結尾。inbox 是把最後的 `.json` 換成 `.tempd`；另外兩個狀態則
直接附加在 base 後面，所以 `insts/llm.json` 會配到 `insts/llm.tempd/`。

## 彙整規則

`aggregate_instructions(base, result)` 依檔名字典序讀 inbox。只接受第一個副檔名就是
結尾的 `<name>.json`；`123.json.temp`、`123.json.bad`、`name.part.json` 都會跳過。
每份內容都可是一個 instruction 物件或一個陣列，最後攤平成單一陣列。彙整會經過
format 層完整的讀取與重新寫出，因此尚未解析的 `$env`、`$ref`、`$opt` 指示詞必須
能無損寫回；否則交接雖成功，執行時的語意卻會悄悄改變。

一份投遞若不是合法 JSON 或不符合 instruction schema，API 會把它改名成
`<name>.json.bad`、加入 `result.issues`，然後繼續處理其他投遞。有效投遞先寫進
`<base>.temp`，再以 `rename` 發布；只有發布成功後才刪除來源投遞。有效但展開後沒有
任何 instruction 的空投遞是例外：沒有資料需要發布，因此不建立空的 base，卻仍會
刪除來源；否則它會永遠留在 inbox、每個回合都被重新讀取。

以下情況都是成功的 no-op（什麼都不做）：

- inbox 不存在或是空的；
- 沒有任何有效投遞（無效投遞仍照前述規則隔離）；
- base 已存在，代表前一批仍在等候取件。此時不覆蓋 base，也不碰 inbox。

## 取件與釋放

`claim_instruction(base, document, result)` 先拒絕既有 `.runi`，再完整讀取 base，最後
把 base rename 成 `.runi`。成功時 `document` 是讀到的完整 JSON；base 不存在則回
`NoInstruction`，不是錯誤。既有 `.runi` 回 `Busy`，讓呼叫端知道不能啟動另一個回合。

`release_instruction(base, result)` 刪除推導出的 `.runi`。應在批次解析與所有子行程
（包含 parallel thread）都結束後呼叫。若行程 crash、被強制終止或斷電，`.runi` 會
保留下來，下一次取件會回 `Busy`；這是刻意保留的未完成現場。

## 公開 API 與錯誤資料

```cpp
HandoffState aggregate_instructions(const std::string &base,
                                    HandoffResult &result);
HandoffState claim_instruction(const std::string &base,
                               std::string &document,
                               HandoffResult &result);
HandoffState release_instruction(const std::string &base,
                                 HandoffResult &result);
```

`HandoffResult` 每次呼叫都會先重設：`published` 表示本次彙整是否真的發布；`path` 與
`error`（errno）描述致命失敗；`issues` 則是彙整仍可繼續時的逐檔問題。`HandoffIssue`
用 `kind` 區分無效投遞、讀取失敗、隔離失敗與發布後刪除失敗，並附帶投遞路徑、
`InstState` 或 errno。

整體 `HandoffState` 不是 CLI 退出碼。`Ok` 可能代表已發布，也可能代表 no-op；呼叫端
要看 `published`。`Busy` 與 `NoInstruction` 是協定狀態，其餘非 `Ok` 值表示這次操作
無法完成。

## 可直接執行的完整例子

先從 repo 根目錄準備投遞：

```bash
rm -rf /tmp/aos-handoff-demo
mkdir -p /tmp/aos-handoff-demo/inst.tempd
printf '%s\n' '{"argv":["printf","hello\\n"]}' \
  > /tmp/aos-handoff-demo/inst.tempd/100.json
```

把以下內容存成 `/tmp/handoff-demo.cpp`：

```cpp
#include <aos/inst.hpp>

#include <iostream>
#include <string>

int main() {
    const std::string base = "/tmp/aos-handoff-demo/inst.json";
    aos::HandoffResult result;

    auto state = aos::aggregate_instructions(base, result);
    std::cout << "aggregate=" << aos::to_string(state)
              << " published=" << result.published << '\n';

    std::string document;
    state = aos::claim_instruction(base, document, result);
    std::cout << "claim=" << aos::to_string(state) << '\n';

    state = aos::release_instruction(base, result);
    std::cout << "release=" << aos::to_string(state) << '\n';
}
```

編譯並執行：

```bash
c++ -std=c++23 /tmp/handoff-demo.cpp -Icore/inst/include -Icommon/include \
  -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst -o /tmp/handoff-demo
/tmp/handoff-demo
```

輸出是：

```text
aggregate=Ok published=1
claim=Ok
release=Ok
```

執行後 `100.json`、`inst.json` 與 `inst.json.runi` 都不存在，代表投遞已發布、取件並
釋放。這個例子只示範交接；真正執行 `document` 裡的指令，仍是呼叫端自己的責任。
