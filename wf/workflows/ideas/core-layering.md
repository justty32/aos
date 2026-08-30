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

> **為什麼 loop 在 core 裡而不是外掛**：`aos core` 就是**整套 CPU 類比**（雖然不是完全
> 類比）。`exec` 是指令，`exec_loop` 是**取指與控制流**——一批 inst 本身沒有 PC、沒有
> 跳轉、沒有分支，控制流那一件事就落在 loop 上。兩個合起來才是那顆 CPU。詳見
> [call-format/cpu-analogy](call-format/cpu-analogy.md)。

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
  `aos_instruction_timeout_ms`／`aos_instruction_set_timeout_ms`）。**使用者已拍板：
  `timeout_ms` 確實要移出最核心**，改由 loop 層管。動到的是**已釋出的 C ABI**，不是
  單純搬程式碼——落地時 C++ 型別、format 的 encode/decode、C ABI 鏡像宣告與
  `static_assert` 要同一個 commit 一起改（見 [conventions](../common/conventions.md)）。

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
- **呼叫格式本身的缺口會反過來限制這套分層**：沒有回傳值、`exit` 檔只有 8 bit、`$ref`
  是坐在最內圈的求值語言、`UnknownKey` 與「loop 選項寫進同一份 json」相撞——整份清單
  見 [call-format](call-format.md)。其中第 4、8 條直接落在本檔的分層上。
- **「真的很核心」的判準**：決定什麼東西可以再包一圈、什麼只能當普通 inst。目前沒有
  判準，deliver 被歸到後者是個案判斷。

## 判準試跑：拿成品逐條過一次（2026-08-30）

**判準**取 [verdicts B12](verdicts.md) 那條未裁的：**「loop 只收無法成為 inst 的東西」**。
**標的**取 [top-down-cli](top-down-cli.md) 的八條指令——那份定死了成品長相，所以「core 要
承擔多少」第一次有了終點可以量。**以下全是我的分類，不是裁決。**

### 一、判準在第一步就裂了：它只對「回合內」適用

八條指令有七條是**使用者在終端機打的**——發起者不在回合裡。對一個不在回合裡的人問
「這能不能是一筆 inst」是沒有意義的：他手上沒有 loop 幫他跑 inst，他要的就是一支能打的
指令。所以判準要補一個前置軸：

| | **能**成為 inst | **不能**成為 inst |
|---|---|---|
| **回合內執行**（loop 幫你跑） | 普通 inst，不進 core | **core** |
| **回合外執行**（人／別的世界） | **指令面（CLI）**，不進 core | 同左 |

> **結論一：core 的名冊與指令的名冊不是同一份。** 本檔既有的邊緣狀況已經記過它的特例
> （「`exec_loop` 是獨立小專案 ≠ 獨立命令」），這是同一個區分的一般化。
>
> `deliver` 卡在這裡就是最好的例子：照判準它**能**是 inst（寫檔 ＋ `rename`，兩個 POSIX
> 指令），但需要它的人**在世界外面**，所以它照樣得是一支指令。verdicts 把「補 `deliver`」
> 列為最高槓桿第二件事，跟判準不衝突——**它進的是 CLI 名冊，不是 core。**

### 二、逐條分類

| 能力 | 誰執行 | 能不能是 inst | 落在哪 |
|---|---|---|---|
| `pu init`：建立 `.aos` 版面 | 使用者 | 能 | CLI |
| **取件 claim**（`inst.json` → `.runi`） | loop | **不能——時點在「執行任何一筆之前」** | **core/loop** |
| **回合邊界**（等所有 thread 跑完） | loop | **不能——一筆 inst 等不了它的同批兄弟** | **core/loop** |
| **彙整發布** | loop | **不能——時點在「全部跑完之後」** | **core/loop** |
| **超時砍子行程** | loop | **不能——一筆 inst 砍不了自己** | **core/loop** |
| `--interval` 睡眠 | loop | 能（`sleep` 是 POSIX），但放進去沒意義 | core/loop |
| `--step N` 的計數／**停止** | loop | 計數能（寫檔）；**停止不能** | **core/loop** ⚠ |
| `agent init`：問答 ＋ 佈置 `.aos` ＋ 投第一份 | 使用者 | 能 | CLI |
| agent 的**自我複製投遞** | inst | 能 | inst |
| 組 prompt／讀寫對話與記憶 | inst | 能 | inst |
| **跨資料夾投遞**給 llm pu | inst | 能，**但格式沒有合法方式表達「別人的資料夾」** | inst（缺口推給 [call-format](call-format.md)） |
| **等 LLM 好了沒** | inst | 檢查能（`test -f`）；**「沒好就下回合再試」不能** | **core/loop** ⚠ |
| `agent say`／`listen`／`talk`／`--interface` | 使用者 | 能 | CLI |
| `agent state`：**讀** | 使用者 | 能 | CLI |
| `agent state`：**寫** | inst | 能 | inst |

**判準通過的第一個驗證**：它獨立推出「超時必須在 loop」，跟已裁決的
「`timeout_ms` 移出最內圈」一致——不是我倒推的。

**順手結清一項存貨**：判準把**彙整**判進 core（時點在回合外，inst 摸不到），
[roadmap](../../../docs/roadmap.md) 停打時剩的四項存貨之一「匯聚 lib-vs-inst」
因此有了答案的一半：**它在 core 裡**，剩下的只有「怎麼跟 loop 接」。

### 三、結論二：八條指令對 core 的新增需求只有一項

上表兩個 ⚠ 是同一件事：**loop 要能看懂本回合的結果，來決定繼續／停／睡**。
`--step` 的停、等 LLM 的重試、`--interval` 的節奏，三條需求同一個根——就是
[verdicts B2](verdicts.md)「loop 沒有可分支的狀態」。

**除此之外，昨天那八條沒有任何一條需要 core 長出新東西。** 也就是說，照這個判準：

```text
core ＝ exec（inst_t ＋ 執行它的函數 ＋ 序列化）
      ＋ loop（claim、回合邊界、彙整發布、超時、← 加一個「分支」）
                                                    ↑ 唯一的新增
到此封閉。
```

**agent 整套一個字都不進 core**——跟 [usage-and-agent-loop](turn-based-folder/usage-and-agent-loop.md)
早就寫的「第一版 agent loop 不需要 `core/llms`，整個 loop 就是一份 `inst.json` 加幾支
腳本」對上了。

### 四、判準管不到、我推薦下一個看的

CLI 名冊那幾支（`pu init`／`deliver`／`say`／`listen`／`state`）**全都要會讀寫 `.aos`
版面**。它們共用的是**協定知識**，不是某一圈的功能——判準問的是「這件事該包第幾圈」，
而這東西根本不是圈。它放 core 之內給外面用、還是獨立成一份，判準沒有意見。

這正是本檔既有那條「注入式 lib 的相依方向」的鏡像：一個問**向內**（匯聚怎麼給 loop
用），一個問**向外**（版面知識怎麼給 CLI 用）。兩條大概是同一個決定。
