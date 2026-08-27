# aos/core 的專案分層構想

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

`core/` 底下該切成哪幾個小專案、每個功能該落在第幾圈。這是**開發架構**，不是回合制
模型本身——模型看 [turn-based-folder](turn-based-folder.md)，這裡談那個模型該怎麼分家。

## 分層本體（方向已定，細節待談）

由內往外四圈，**每一圈只知道自己以內的**：

```text
┌─ deliver 之類 ── 不再往外包，就是普通的一筆 inst
│ ┌─ 匯聚 ─────── core 專案，但用「注入式 lib」跟 loop 配合
│ │ ┌─ exec_loop ─ core 專案：重複讀 inst.json 並執行；timeout_ms／thread 等選項
│ │ │              寫在 json 裡，由它在 exec 讀之前先納入並套用
│ │ │ ┌─ exec ──── 最核心的 core 專案
│ │ │ │   · aos exec xxx：讀 xxx/.aos/inst.json，執行裡面所有 inst_t
│ │ │ │   · inst_t 的序列化／反序列化（目前用 JSON）
│ │ │ │   · inst_t 這個資料結構 + 執行它的函數 ← 最初始最核心
```

### 最核心：`exec`

三小圈同屬一個小專案，由內而外：

1. **`inst_t` 這個資料結構，以及執行這個資料結構的函數。** 甚至**沒有
   `timeout_ms`**——超時這塊由外面去管理。
2. **`inst_t` 的序列化／反序列化**，目前是說用 JSON。
3. **一個指令 `aos exec xxx`**：讀取 `xxx/.aos/inst.json`，然後執行 `inst.json` 內的
   所有 `inst_t`。

### 次外圈：`exec_loop`

另一個 `aos/core` 專案，**用於補 `aos exec` 沒考慮到的缺口**，功能稍微多一些：重複
讀取 `inst.json` 並執行，還有 `timeout_ms`、thread 等。**這些選項都在 json 中**，它會
在 exec 讀之前就納入並應用。

### 再外圈：匯聚

也是 `aos/core` 內的專案，但**使用方式是跟 loop 配合、做注入式 lib 來用**，不是再把
loop 包一層。

### 更外面：不再往外包

deliver 之類的東西，**除非真的很核心，不然不繼續套在 loop 外面，而是做為普通 inst
來做**。這是 [model](turn-based-folder/model.md)「`inst` 執行的是 POSIX 指令，所以可以
承載任何東西」的直接後果——上層能力不必是新的一圈。

## 與目前程式碼的落差

- `core/` 目前是 `inst`、`llms`、`tooljson`；**沒有 `exec_loop`、沒有匯聚專案**，而
  `llms`／`tooljson` 已被使用者判定為失敗作（見 [ideas README](README.md)）。
- **`inst_t` 現在有 `timeout_ms`**（`core/inst/include/aos/inst.hpp:65`，C ABI 是
  `aos_instruction_timeout_ms`／`aos_instruction_set_timeout_ms`）。這個構想要把它從最
  核心移到 loop 層，動到的是**已釋出的 C ABI**，不是單純搬程式碼。

## 我挖到的邊緣狀況（待使用者判斷）

- **超時由誰動手砍**：`timeout_ms` 移出最核心後，loop 拿到超時值，但「執行 `inst_t`
  的函數」是同步的——loop 要能在它跑的時候介入。要嘛核心提供非阻塞入口，要嘛 loop
  自己持有子行程 handle；這兩條路會反過來決定核心的介面長相。
- **注入式 lib 的相依方向**：鐵律是下層不可以知道上層存在，所以 loop 不能 include
  匯聚。那組裝的人是誰？是 `aos` 這支執行檔在最外面把兩者接起來，還是 loop 暴露一個
  匯聚去填的 hook。
- **「匯聚」與 [layout-handoff](turn-based-folder/layout-handoff.md) 的「彙整」是不是
  同一件事**。如果是，這個構想就順手回答了 [decided-and-open](turn-based-folder/decided-and-open.md)
  那條開放問題「彙整者什麼時候跑、由誰跑」＝由 loop 注入。
- **`exec_loop` 是獨立小專案，但是不是獨立命令**：decided-and-open 已定「持續執行是
  `aos exec --loop 0`，不另做 `core/daemon`」。小專案獨立 ≠ 命令獨立，兩者可以並存
  （`aos exec --loop` 背後連的是 `exec_loop` 這個 lib），但這一條要明說，否則之後會被
  當成兩份真相。
- **選項寫在 json 裡、由 loop 在 exec 讀之前套用**：那份 json 對最核心的 `exec` 來說會
  多出它不認得的 key，而 `format.cpp` 目前對不認得的 key 直接回 `UnknownKey`。是 loop
  先把 loop 專屬的欄位剝掉再交給 exec，還是 exec 改成忽略未知 key——這決定兩層共不
  共用同一份 schema。
- **`core/inst` 要不要改名成 `core/exec`**：layout-handoff 訂過「`inst` 是名詞、`exec`
  是動詞，子命令改名不代表小專案跟著改名」。這個構想把最核心的專案直接叫 `exec`，
  跟那條相反，需要一句話拍板。
- **「真的很核心」的判準**：決定什麼東西可以再包一圈、什麼只能當普通 inst。目前沒有
  判準，deliver 被歸到後者是個案判斷。
