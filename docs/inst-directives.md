# inst 的 `$` 指示詞：`$ref`、`$env`、`$opt`

← [文件索引](README.md)｜[roadmap](roadmap.md)｜格式現況 [`core/inst/docs/format.md`](../core/inst/docs/format.md)

**狀態**：方向由使用者定下——引入 `../freepy` 那套 `$ref`／`$env`，並用
`{"$opt": "merge"}` 表達 stderr 併流。`core/inst` 核心層**已解凍**，可以改。下面標
「待拍板」的細節還沒定，**不要自己補答案**。

> `$ref` 的形式取自 freepy 的
> [`memory_tools`](../../docs/freepy/future/memory-tools/PLAN.md)；`$env` 在 freepy 裡
> **沒有先例**（那邊的 `$env:` 是 PowerShell 語法），是把同一個家族推廣出來的。

這份只講 schema 與分層設計。它落地之後才去改
[`core/inst/docs/format.md`](../core/inst/docs/format.md)——那份描述的是**現況**，不是
計畫。

---

## 一、核心概念

> **一個「只有一個 `$xxx` 鍵」的 JSON 物件不是字面資料，是指示詞（directive）：
> 它產生那個位置的值。**

```json
{"argv": ["deploy", {"$env": "TARGET"}], "stderr": {"$opt": "merge"}}
```

三個指示詞，各回答「值從哪來」：

| 指示詞 | 值從哪來 |
|---|---|
| `$ref` | 別的地方（另一份 JSON 的某個位置） |
| `$env` | 環境變數 |
| `$opt` | 都不是——它是一個**具名選項**，不是字串 |

**為什麼用物件而不是哨兵字串**：因為沒有跳脫問題。如果寫成 `"stderr": "merge"`，你就
永遠沒辦法把 stderr 導到一個真的叫 `merge` 的檔案。物件形式讓**字面字串永遠是字面**，
不需要 `\merge` 這種逃生口。這個性質值得整套沿用。

## 二、`$opt` 與 stderr 併流（[D5](roadmap.md#d5) 的落地）

```json
{"argv": ["build"], "stdout": "out.log", "stderr": {"$opt": "merge"}}
```

`merge` 的意思就是 shell 的 `2>&1`：**兩條流共用同一條管子**，輸出交錯而不是互相蓋寫。

實作上要換掉現在的做法：

```text
現在：  stdout 開一次 open(O_TRUNC)，stderr 再開一次 open(O_TRUNC)
        給同一個路徑 → 各自截斷、各自有獨立偏移量 → 互相蓋寫

merge： stdout 照舊設好，然後 dup2(fd_1, 2)
        兩條流共用同一個 open file description 與偏移量 → 才會交錯
```

- 順序：`merge` 一定在 stdout 重導向**之後**做。
- `stdout` 沒設（＝繼承呼叫端）時 `merge` 仍然合法且有意義——就是把繼承來的 fd 1 複製
  到 fd 2，跟在終端機下打 `2>&1` 一樣。
- **`inst_t::stderr_path` 仍然是字串**（已定）。「繼承／併入 stdout」不塞進那個字串
  的型別裡，而是**另外加一個變數**，由後續環節配合處理。好處是 C ABI 只需要**新增**
  存取子，既有的 `stderr_path` getter／setter 不動——`inst.h` 那條「列舉值只能在尾端
  加、不能重排或刪」的規則也不會被踩到。

**待拍板**：`$opt` 目前只定義 `merge` 這一個值。其他候選（`stdin` 的 `close`、
`stdout` 的 `null`）先不開——**每個 opt 都要指定它在哪些欄位合法**，否則 `$opt` 會變成
一個無法驗證的洞。

## 三、`$env`

```json
{"argv": ["deploy", {"$env": "TARGET"}]}
```

**待拍板 ①：取誰的環境？**

- (a) **解析當下的父行程環境**（＝呼叫 `aos exec` 的那個 shell 的環境）。
- (b) 套用該筆 instruction 自己的 `env` 之後的**合併**環境。

**建議 (a)**。理由：instruction 檔的心智模型是「呼叫端填進去的模板」，(a) 就是這個意
思；而 (b) 會產生順序問題——`env` 自己的值也可能是 `{"$env": ...}`，那就要定義解析
順序甚至偵測循環。(a) 沒有這個問題。

**待拍板 ②：變數不存在怎麼辦？**

**建議：直接算錯誤**，不要安靜地變成空字串。一個空的 `argv` 元素或空的路徑會變成很難
追的 bug。要「不存在就用預設值」的話得另設形式（例如 `{"$env": "X", "default": "y"}`）
——但那就不是單鍵物件了，會破壞第一節那條規則，**所以它是一個要單獨拍板的決定**。

## 四、`$ref`

沿用 freepy [`memory_tools`](../../docs/freepy/future/memory-tools/PLAN.md) 的形式：

```json
{"$ref": "shared/argv.json#/build/release"}
```

`#` 後面是 JSON Pointer，指到該檔裡的某個位置。

**沒有拒絕清單**（已定）。不擋絕對路徑、不擋 `..` 逃出目錄——**能讀到什麼檔，完全看
`aos` 這個行程本身的權限**。理由是 instruction 檔本來就是完整的可執行權柄（見
[`exec.md`](../core/inst/docs/exec.md) 的安全性一節）：一份能寫 `argv: ["cat","/etc/…"]`
的檔案，再去限制 `$ref` 能讀哪裡是沒有意義的——**能力早就是全的**，清單只是安全劇場。
把關的位置在「誰能寫這份 instruction 檔」，不在指示詞。

**已定：相對路徑以 instruction 檔自己所在的目錄為基準**（也就是 `.aos/`），這樣整個
資料夾可以連 `.aos` 一起搬走而不失效——呼應回合模型「資料夾就是世界」。絕對路徑照字面
用。

> 注意這**和子行程的 cwd 差一層**：`$ref` 以 `.aos/` 為基準，而 instruction 裡的
> `stdout`／`cwd` 等路徑欄位是另一套基準（見 [roadmap](roadmap.md) 的預設 cwd 那題）。
> 兩者是不同時機、不同層的東西——`$ref` 在 `resolve` 時解析，路徑欄位在 `exec` 時使用。

**待拍板 ②：深度。** **建議 v1 深度 1，不遞迴**——被 `$ref` 進來的內容裡如果還有
`$ref`，不再展開。理由是一個小檔可能連到整棵樹，不該一次就無上限展開；順帶也不用處理
循環。

**這是唯一會去讀額外檔案的指示詞**，也因此它是三個裡面唯一會撞到分層問題的——見下一節。

## 五、適用範圍

**建議**：凡是「字串值」的位置都可以改放指示詞。

| 位置 | 可放指示詞？ |
|---|---|
| `argv` 的元素 | ✅ |
| `stdin`／`stdout`／`stderr`／`exit`／`cwd` | ✅ |
| `env` 的**值** | ✅ |
| `env` 的**鍵** | ❌ 鍵必須是字面 |
| `timeout_ms` | ❌ 先不開（要處理字串→整數轉換） |

`$opt` 額外受限於「這個 opt 在這個欄位合法嗎」——目前只有 `stderr` 收 `merge`。

## 六、擺在哪一層？（**最重要的待拍板**）

現在的分層是 `inst ← format ← exec`，鐵律是：**`format` 只懂語法**（不懂路徑是 OS
資源、不懂行程），**`exec` 收到的是一個已經完全解析好的 `inst_t`**。

`$env` 與 `$ref` 是**解析（resolution）**，不是語法——它們要讀 `environ`、要讀檔案。
這正好卡在兩層中間，三條路：

| | 做法 | 代價 |
|---|---|---|
| **A** | `format` 直接做完 | `format` 要碰 `environ` 與檔案系統，它的純粹性沒了 |
| **B** | 新增一個 `resolve` 步驟，夾在 format 與 exec 之間 | 分層乾淨、`exec` 依然收到解析好的 `inst_t`；代價是多一層與多一組 API |
| **C** | 留在 `run.cpp`（CLI 層）做 | 函式庫使用者（走 `read_one` 的人）拿不到指示詞功能 |

**已定：B。** `format` 產出的 `inst_t` 帶著未解析的指示詞，`resolve(inst_t&, ctx)` 把
它變成可執行的 `inst_t`，`exec` 完全不變。這也讓「解析用哪個環境、相對路徑以哪裡為
基準」變成 `ctx` 的**明確參數**，而不是藏在某層裡的隱含行為。

相依方向變成 `inst ← format ← resolve ← exec`（`resolve` 與 `exec` 一樣只往下看
`inst`，彼此不相識）。

## 七、對現有契約的影響

- **round trip 變成有損，而且這沒差**（已定）。`write_one(read_one(doc))` 會吐出**已
  解析**的值，不是原本的指示詞。現有那個 round-trip 測試
  （[`test_format_write.cpp`](../core/inst/tests/test_format_write.cpp)）用的是純字串，
  所以照樣會綠。真的需要無損時，頂多加一個 `read_one(doc, raw=true)` 之類的形式保留
  未解析的樣子——**不是現在要做的事**。
- **要新增錯誤狀態**：不認得的 `$xxx`、指示詞物件有多於一個鍵、指示詞的值不是字串、
  環境變數不存在、`$ref` 目標不存在或逃出 root、`$opt` 用在不合法的欄位。
- **C ABI 只需要新增，不需要改既有的**：`stderr_path` 維持字串，併流靠另一個變數表達，
  所以既有存取子原封不動。
- **安全面沒有真的變寬**。`$ref` 讓 instruction 檔多出「讀任意檔案」這個面，但那份檔案
  本來就能直接 `argv: ["cat", …]`——**能力早就是全的**。把關在「誰能寫這份檔」，不在
  指示詞（見第四節）。

## 八、實作順序建議

由小到大，每一步獨立可驗收：

1. **`$opt` + `stderr` merge** — 最小的一步，而且直接把 [D5](roadmap.md#d5) 解掉。它不
   需要讀環境也不需要讀檔，所以**連 `resolve` 層都還不需要**（`merge` 是純語法，
   `format` 自己就能決定）。
2. **`resolve` 層 + `$env`** — `resolve` 這一層在這一步才真的長出來。
3. **`$ref`** — 最大的一步：檔案系統、JSON Pointer、相對路徑基準、深度限制。

順帶一提，[D3](roadmap.md#d3) 的 non-blocking 欄位跟第 1 步動的是同一批檔案
（`format.cpp` 加 `exec.cpp`），**兩件事應該排在一起做**。
