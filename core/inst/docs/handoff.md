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
`.aos/insts/llm.json`，並負責四件事：

1. **投遞**：把一份待辦 JSON 放進 inbox。這是三步協定裡唯一由**外部生產者**執行的
   一步，所以協定細節（唯一檔名、先 `.temp` 後排他 rename、canonical 位元組）由
   `deliver_instructions()` 包起來，生產者不必自己手刻。
2. **彙整**：把多份有效投遞攤平成一個批次，再原子發布成 base path，並在批旁邊寫一份
   header sidecar。
3. **取件**：把 base path 改名為 `.runi`，表示這一批已被某個回合占有。回合就是一次
   「取走一批、全部執行、清掉執行中標記」的完整處理。
4. **釋放**：回合正常返回後刪除 `.runi`。

協定的 normative 條文在 [SPEC](../../../docs/SPEC.md) §D 區（§D-1～§D-8）；本檔寫的是
這個函式庫實際怎麼做。

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
| header sidecar：這一批的 metadata | `/srv/demo/.aos/inst-head.json` |
| 發布中的 header 暫存檔 | `/srv/demo/.aos/inst-head.json.temp` |

base 必須以 `.json` 結尾。inbox 是把最後的 `.json` 換成 `.tempd`，header 是把最後的
`.json` 換成 `-head.json`；另外兩個狀態則直接附加在 base 後面，所以 `insts/llm.json`
會配到 `insts/llm.tempd/` 與 `insts/llm-head.json`。

## 投遞

```cpp
HandoffState deliver_instructions(const std::string &instruction_path,
                                  const std::string &document,
                                  DeliverResult &result);
```

`document` 是一份完整的 JSON 文件（一個 instruction 物件或一個陣列），驗證走的是
format 層那個唯一的 parser——跟彙整、跟 `aos exec` 讀 `inst.json` 是同一套規則。
整份文件**先驗證再落地**：任何一筆不合格就整批拒收，回 `DeliveryInvalid`，
`result.inst_state` 是驗證狀態、`result.error_record` 是第幾筆出問題（1 起算，
還沒進到逐筆解碼時是 0），此時 inbox 裡什麼都不會多出來，連 `.temp` 都沒有。

通過之後的落地順序是：

1. 產生一個唯一檔名 `<pid>-<seq>.json`（`seq` 是行程內單調遞增的計數）；
2. 用 `O_EXCL` 建 `<名>.json.temp`，把 **canonical 位元組**寫進去、`fsync`、關檔——
   canonical 的意思是這份文件已經被 `read_all`→`write_all` 往返過一次，所以「投遞了
   什麼」與「彙整讀到什麼」永遠是同一串位元組，未解析的 `$env`／`$ref`／`$opt` 也
   在這一步被證明寫得回去；
3. **排他** rename 成 `<名>.json`（`renameat2(RENAME_NOREPLACE)`，檔案系統不支援時
   退階成 `link`＋`unlink`）；撞名就換一個序號重來，**絕不覆蓋既有的名字**——被覆蓋的
   可能正是另一個生產者寫到一半的投遞；
4. `fsync` inbox 目錄，讓那個目錄項落盤。

成功時 `result.name` 是發布後的檔名、`result.inbox` 是它落腳的收件匣、`result.count`
是這批有幾筆（空批次 `[]` 合法，`count` 為 0）。inbox **必須已經存在**：不存在回
`InboxReadFailed`，deliver 不會替你建世界（那是 `aos init` 的事）。

兩個邊角：

- `result.sync_error` 非 0 代表**投遞已經進 inbox 了**，只是第 4 步的目錄 `fsync`
  失敗——缺的是耐久性保證，不是投遞本身。這是警告不是失敗，函式仍回 `Ok`；謊報失敗
  會讓生產者重投，那才真的多出一份。
- 序號連撞 8 次（只可能來自 pid 重用後撞上別的行程留下的殘檔）會放棄並回
  `RenameFailed`／`EEXIST`：那時 inbox 有系統性問題，回報比空轉好。

同一個行程連續呼叫 N 次就是 N 份不同名的投遞，不會互相蓋掉；每一次呼叫都是一次真的
投遞，**沒有「重試」這回事**。

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

## 批 header sidecar

每次真的發布一批，彙整就在批**旁邊**寫一份 header：base 的 `.json` 換成
`-head.json`，內容是一行 JSON（實跑取樣，`id` 每批不同）：

```text
{"version":1,"id":"9a2b5422e914c659","origin":"aggregated","result":null}
```

四個欄位的意義是 [SPEC](../../../docs/SPEC.md) §C-8 定的：`version` 是**指令格式**的
版本（不是 `.aos` 版面版本，兩者分開，見 §F-1／§F-2）、`id` 是批 id（去重的依據）、
`origin` 是這批打哪來（彙整發布的一律 `"aggregated"`）、`result` 留給 loop 在
writeback 時寫回（值域 M2 才定義，現在恆為 `null`）。

**誰寫誰讀**：彙整層寫，loop 讀。**exec 層不讀、也不認識 header**——`claim_instruction()`
只讀 base，`execute()` 連這個檔存在都不知道（§A-6「凍結的矽」的直接推論）。所以
header 怎麼長、將來加什麼欄位，都動不到執行機制。

幾個不會讓整輪失敗的情況：

- header 寫不成或 rename 不成：**這一批照發**，只是這一輪沒有去重保證（退回沒有
  header 時的行為），記一筆 `HeaderWriteFailed` issue 讓上層看得見。
- 現任 header 讀不到內容或格式不認得：記一筆 `HeaderInvalid` issue，一律**視同沒有
  header**，照常發布。
- 沒有東西可發布（空投遞被消化掉的那種 no-op）就不寫 header——header 描述的是
  「現任的那一批」，沒有批就沒有 header。

## fsync 與發布順序

所有由這一層寫出去的檔案都 `fsync` 之後才算寫成功（`fsync` 失敗＝寫入失敗），
`rename`／`unlink` 之後還要 `fsync` 它所在的**目錄**——目錄項有沒有落盤看的是目錄的
`fsync`，不是檔案的。發布一批的完整順序（[SPEC](../../../docs/SPEC.md) §D-5）：

```text
1. 寫批 <base>.temp        → fsync 檔
2. 寫 header <base>-head.json.temp → fsync 檔
3. rename header  ← 去重承諾的提交點
4. fsync 目錄
5. rename 批
6. fsync 目錄
7. 刪掉來源投遞 → fsync 目錄
```

**為什麼 header 要排在批前面**：崩在第 3 步與第 5 步之間，留下的現場是「header 已經是
新的 id ＋ 批還完整躺在 `.temp`」——重開機後認得出來，可以往前補完（見下一節的
roll-forward）。反過來（批先、header 後）崩掉只剩「批已發布、header 還是舊 id」，
跟「這批根本沒發布過」長得一模一樣，分不出來就會重演雙重執行。

目錄 `fsync` 失敗只記 `DirectorySyncFailed` issue、不改變控制流：目錄項本身已經換好
了，少的是耐久性保證；為此讓整輪彙整失敗只會把世界卡住，更糟。

> **邊界**：這條「寫檔就 fsync」的規矩只涵蓋**函式庫自己開的檔**。
> `aos_instruction_write_fd()` 寫的是**呼叫者自己的 fd**——函式庫不代呼叫者 `fsync`、
> 也不動它的 flag、不關它；要耐久性請自己在寫完之後 `fsync`。（`write_file()` 那種
> 自己開檔的入口就有 fsync，見 [capi.md](capi.md)。）

## 批 id、去重與 roll-forward

批 `id` 是對**排序後的每份投遞**做的確定性摘要：把「投遞檔名 `\0` 內容 `\0`」依序餵給
64-bit FNV-1a，輸出 16 位小寫 hex。吃的是**檔名**而不是完整路徑——世界整包可搬，id
不該跟著搬家變。

彙整在發布之前，會拿本輪算出來的 id 去比對**現任 header** 的 `id`。相同代表這一組
投遞上一輪已經跨過提交點（第 3 步）、只是投遞沒被清掉——崩在刪投遞之前，或
`unlink` 全數失敗。這時分兩種走法：

- 批 `.temp` 裡是一份完整的批 → **roll forward**：把 `.temp` rename 到位（補完第 5
  步）、`fsync` 目錄、清掉投遞。這一批不會丟。
- 沒有 `.temp`（或 `.temp` 解析不出非空的批）→ 上一輪已經發布完、批也已經被取走或
  正在跑：**只清投遞、不重發**。這就是「同一批不會執行兩次」的兜底。

**覆蓋範圍（照實寫，不誇大）**：這個機制只保證**同名同內容、恰好整組**的投遞殘留不會
被發布第二次。它不是內容去重，也不是通用的冪等保證：

- 只有一部分投遞殘留，或殘留的投遞和新來的投遞混在一起，本輪算出來的 id 就跟現任
  header 不同，那一批會照常發布——**其中重複的那幾筆會再跑一次**。這個情況不在保證
  內。
- 同樣內容重新投遞一次會拿到新的檔名（`<pid>-<seq>` 每次不同），id 也就不同。
  「投兩次一樣的東西」本來就該跑兩次，那是使用者的意思，不是這個機制要擋的事。

## 取件與釋放

`claim_instruction(base, document, result)` 先拒絕既有 `.runi`，再完整讀取 base，最後
把 base rename 成 `.runi`。成功時 `document` 是讀到的完整 JSON；base 不存在則回
`NoInstruction`，不是錯誤。既有 `.runi` 回 `Busy`，讓呼叫端知道不能啟動另一個回合。

`release_instruction(base, result)` 刪除推導出的 `.runi`。應在批次解析與所有子行程
（包含 parallel thread）都結束後呼叫。若行程 crash、被強制終止或斷電，`.runi` 會
保留下來，下一次取件會回 `Busy`；這是刻意保留的未完成現場。

## 公開 API 與錯誤資料

```cpp
HandoffState deliver_instructions(const std::string &base,
                                  const std::string &document,
                                  DeliverResult &result);
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
用 `kind` 區分無效投遞、讀取失敗、隔離失敗、發布後刪除失敗、header 寫入失敗
（`HeaderWriteFailed`）、現任 header 讀不懂（`HeaderInvalid`）與目錄 fsync 失敗
（`DirectorySyncFailed`），並附帶投遞路徑、`InstState` 或 errno。後三種都不代表這一輪
失敗，只代表少了一項保證。

`DeliverResult` 是投遞專用的結果（同樣每次呼叫先重設）：成功時看 `name`（發布後的
投遞檔名）、`inbox`（落腳的收件匣）、`count`（這批幾筆）與 `sync_error`（非 0 ＝ 已投遞
但目錄 fsync 失敗的警告）；`DeliveryInvalid` 時看 `inst_state` 與 `error_record`；
其餘失敗看 `path` 與 `error`。

整體 `HandoffState` 不是 CLI 退出碼。`Ok` 可能代表已發布，也可能代表 no-op；呼叫端
要看 `published`。`Busy` 與 `NoInstruction` 是協定狀態，`DeliveryInvalid` 表示投遞的
文件過不了驗證，其餘非 `Ok` 值表示這次操作無法完成。

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
釋放；留在原地的是 `inst-head.json`——那一批的 header sidecar，發布時寫的。這個例子
只示範交接；真正執行 `document` 裡的指令，仍是呼叫端自己的責任。

### 換成用 `deliver_instructions()` 投遞

上面的例子是手動把檔案放進 inbox（示範用）。真正的生產者應該走 deliver，讓協定細節
由函式庫負責。先準備一個空世界的 inbox：

```bash
demo=$(mktemp -d)
mkdir -p "$demo/inst.tempd"
```

把以下內容存成 `$demo/deliver-demo.cpp`：

```cpp
#include <aos/inst.hpp>

#include <iostream>
#include <string>

int main() {
    const std::string document = R"({"argv":["printf","hello\n"]})";
    aos::DeliverResult result;

    const aos::HandoffState state =
        aos::deliver_instructions("inst.json", document, result);
    std::cout << "deliver=" << aos::to_string(state)
              << " name=" << result.name << " count=" << result.count
              << " inbox=" << result.inbox << '\n';
}
```

從 repo 根目錄編譯，然後進 `$demo` 跑兩次（base 是相對路徑，所以要在那個目錄裡跑）：

```bash
c++ -std=c++23 "$demo/deliver-demo.cpp" -Icore/inst/include -Icommon/include \
  -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst -o "$demo/deliver-demo"
cd "$demo"
./deliver-demo
./deliver-demo
ls -1 inst.tempd
cat inst.tempd/*.json
```

輸出是（`90507` 之類的數字是實跑當下的 pid，每次都不一樣）：

```text
deliver=Ok name=90507-0.json count=1 inbox=inst.tempd
deliver=Ok name=90508-0.json count=1 inbox=inst.tempd
90507-0.json
90508-0.json
[{"argv":["printf","hello\n"]}]
[{"argv":["printf","hello\n"]}]
```

兩次呼叫得到兩份不同名的投遞，內容都是 canonical 的批陣列——投的是單一物件，落地的
是 `[{...}]` 加一個 LF。接著對同一個 base 呼叫 `aggregate_instructions()`，就會把它們
併成一批。
