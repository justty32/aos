本輪有 **6 項必修**。審查包含差異閱讀、呼叫鏈核對，以及 `python -B` 的記憶體模擬；未修改任何檔案。既有測試會建立暫存檔，因此未在這次唯讀任務執行完整測試套件。

## 必修

### 1. `check` 與 `start` 的 KernelMismatch 判定不同

**位置：** `proto5/lib/aos_agent_check.py:21`；對照 `proto5/lib/aos_agent.py:115`。

- **問題：** `check` 只在 `raw is not None` 時比較；`start` 則在 `tick.json` 存在時，要求綁定值必須是字串且逐字相同。
- **重現：** 設 `AOS_KERNEL_HOME=/K`，既有 `tick.json` 為 `{}`、缺 `envs`、K 為 `null`，或 JSON 損壞。`find_kernel()` 都回傳 `/K` 且沒有問題；`start` 會報 `KernelMismatch`。其他設定正常時，檢查可能通過卻無法啟動。
- **建議改法：** 區分「檔案不存在」與「存在但讀不到合法綁定」，共用與 `_tick_inst()` 相同的判定。沒有環境變數時，也不要把損壞的既有檔說成「沒有 tick.json（沒 start 過）」。

### 2. 缺欄位的 proc 會成功輸出不符合表格的 schema

**位置：** `proto5/lib/aos_kernel_ls.py:64`；規範 `proto5/spec/kernel/cli-ls.md:78`。

- **問題：** `target` 缺少時輸出 `null`，但規範只承諾絕對路徑；`pool`、`status` 也會輸出 `null`，表格沒有定義其可空型別。`runs`／`fails` 若明確為 `null`，也不會套用整數預設值。
- **重現：** 帳本放入 `"procs":{"p":{}}`，輸出包含：
  ```json
  {"pool":null,"status":null,"target":null,"runs":0,"fails":0}
  ```
  若放 `"runs":null`，輸出仍是 `null`。
- **建議改法：** 在發布 v1 前明定缺鍵、`null`、錯型別的處理：要麼驗證失敗、退 1 且 stdout 空；要麼明確把可空型別列入規範。不要直接透傳卻承諾固定型別。

### 3. `status: null` 的統計會產生歧義，甚至重複 JSON 鍵

**位置：** `proto5/lib/aos_kernel_ls.py:70`。

- **問題：** Python 的 `None` 被當成字典鍵，序列化後變成字串 `"null"`；與真的字串狀態 `"null"` 衝突。
- **重現：** 兩個 proc 分別使用 `status: null` 與 `status: "null"`，實際輸出：
  ```json
  "status": {"null": 1, "null": 1}
  ```
  一般 JSON reader 只留下其中一筆，統計總和不再等於行程數。單獨 `null` 時，文字標題則印 `None 1`，與 proc 表的 `-` 不一致。
- **建議改法：** 統計前驗證並正規化 status；明定未知狀態如何表示，避免靠 JSON 自動轉換鍵。

### 4. 沒有字面 `stderr` 時，`look` 並非規範要求的 target

**位置：** `proto5/lib/aos_kernel_ls.py:32`；規範 `proto5/spec/kernel/cli-ls.md:40`。

- **問題：** 普通檔、資料夾、缺少 `stderr` 的 JSON，都可能回傳 `"<target> 的 stderr 設定"`，而不是 target 路徑。JSON 的 `look` 因而混入說明文字。
- **重現：** `stderr_hint("/A/tool")`，或讀取內容 `{}` 的 `/A/plain.json`，都會附加「的 stderr 設定」。
- **建議改法：** 無可用字面 `stderr` 時回傳 `str(path)`；若要保留診斷說明，另設欄位。這是沿用舊碼的落差，`test_kernel_cli.py:300` 還有測試固定了與新規範衝突的結果。

### 5. health 已判 `broken`，CLI 仍退 0

**位置：** `proto5/lib/aos_kernel_ls.py:38`、`proto5/lib/aos_kernel_cli.py:157`。

- **問題：** `health()` 會把部分讀取失敗轉成 `("broken", ...)`，但 `_run()` 印完摘要後無條件退 0，違反規範「broken 退 1」。
- **重現：** `status()` 讀完執行中的帳本後，檔案在 `health()` 查詢 mtime 前消失或變得不可讀。以 `Path.stat()` 拋 `FileNotFoundError` 模擬，文字版與 JSON 版都輸出 broken、stderr 空、退出碼 0。
- **建議改法：** 在輸出之前處理 broken，依 `cli-ls.md` 的錯誤契約統一退 1、stdout 空、stderr 一行。這個退出碼問題也是舊行為延續。

### 6. 不同池被顯示用的 `-` 合併

**位置：** `proto5/lib/aos_kernel_ls.py:147`。

- **問題：** 分組前使用 `cpu["pool"] or "-"`，將空字串池、字面 `"-"` 池，以及 info 不含該 cpu 的 `null` 池合成同一組。
- **重現：** info 有 `a.pool=""`、`b.pool="-"`，兩者均通過現有 info 驗證；文字表只印一次 `-`，下一顆池欄留白，誤表示同池。
- **建議改法：** 以原始 pool 值分組，只在渲染時轉換顯示文字，並區分空字串、未知池與字面 `-`。

## 建議

### 1. 舊旗標的錯誤優先順序要說清楚

**位置：** `proto5/lib/aos_kernel_cli.py:179`、`:136`。

已實測以下寫法都退 2、stdout 空，並指向 `aos-agent check`：

- `--agent X`
- `--agent`
- `--agent=X`
- 重複 `--agent`
- 與 `--probe` 混用
- 放在合法的 `--target /K` 前

`check -h` 退 0、stderr 空，且不顯示 `--agent`。

但 `--agent --target` 會先報缺參數；混入未知旗標會先報 argparse 錯誤；`--target=`、`--` 也會先被其他檢查攔截。**這些仍然退 2，但沒有搬家提示。**

建議明定搬家提示只適用於其餘參數合法時；若要求任何組合都優先提示搬家，就必須在完整解析前辨識舊旗標，並保留 help 行為。

### 2. 穩定承諾應區分固定欄位與資料映射

**位置：** `proto5/spec/kernel/cli-ls.md:70`、`:80`；`proto5/lib/aos_kernel_ls.py:86`。

`counts.procs.status` 隨帳本內容增減鍵，是資料映射的正常行為，**不應直接視為 schema 刪鍵**；建議規範明說「只加鍵」約束的是固定欄位名稱。

目前 `settings` 的五個值經 `load_info()` 驗證、補預設，確實都是整數，沒有現存型別破約。但 schema 直接迭代內部 `DEFAULTS`，未來內部改名容易意外影響 v1；建議固定 v1 欄位清單。

### 3. `_cut` 的極小寬度與 Unicode 邊界

**位置：** `proto5/lib/aos_kernel_ls.py:94`、`:98`。

已確認空字串、全形字、24 格整不截斷，以及一般中日韓字對齊正常。`_cut("x", 0)` 卻回傳寬度 1 的 `…`；目前呼叫端固定 24，因此不影響現行 CLI。

建議限定 `limit >= 1` 或處理零寬度。另 `_width()` 把結合符號算一格，日文分解濁音等輸入仍可能錯位；若要涵蓋這類文字，可使用顯示寬度函式。

### 4. 未 boot 時，kernel 池 cpu 被算成工作 cpu

**位置：** `proto5/lib/aos_kernel_ls.py:55`、`:73`。

只有 info、沒有帳本時，`kcpu` 為 `null`，因此 info 中 `pool="kernel"` 的 cpu 也被算進 idle，工作欄印「閒」。這符合「是不是帳本 kcpu」的字面定義，但容易讓使用者誤判可用工作容量。

建議明定未 boot 時的分類方式；若依 pool 辨識預定 kernel cpu，需同步調整規範。

### 5. library README 還留著舊 JSON 說明

**位置：** `proto5/lib/README.md:364`。

仍寫「`--json` 印 `status()` 加 `health`」，與本輪穩定 schema 不符。建議改成連到 `kernel/cli-ls.md`，避免維護第二份描述。

### 6. 值得補的測試

**位置：** `proto5/lib/test/test_advice_r1.py:215`；現有 schema 測試主要確認鍵集合。

建議補以下具體情境：

- 本報告六項必修的重現案例，包含 JSON 重複鍵檢查。
- `tick.json`：不存在、損壞、缺 K、K 為 null／非字串、舊 `AOS_K`；逐一與 `_tick_inst()` 判定比較。
- daemon 選擇：環境變數與 info 同時存在且不同、只有 info、兩者皆無；分別驗 agent check 與 ls 的不同優先順序。
- 帳本頂層缺鍵、proc 缺鍵／明確 null，驗證型別與兩種輸出的退出碼。
- cpu 聯集：只有 kernel cpu、帳本額外 cpu、kcpu 不在 info、重複名稱不重複列出。
- 文字表：中日韓混合長名、24／25 格、空 proc／queue、queue 8／9 個、交錯出現的池、`忙（rm）`。
- `--json -v` 與 `--json` 相同；所有 health／agent mark 分支都只有一個 JSON 物件及尾端換行。
- 上述舊旗標成功搬家組合，以及同時存在其他用法錯誤的優先順序。

## 其餘核對結果

| 項目 | 結果 |
|---|---|
| `check` 正常路徑的項目順序、訊息格式、總結與 probe 去重 | 無其他問題 |
| K 缺失／相對環境路徑時略過 kernel；info 失敗仍檢查 agent 工具 | 無其他問題 |
| daemon 找法 | CLI 路徑符合各自規範 |
| health 原有順序、字句及 agent 判定順序 | 本輪未改動；退出碼例外見必修 5 |
| 沒帳本、帳本頂層缺鍵 | 正常提供 null／空集合，不會單因缺帳本失敗 |
| daemon 沒活、info 沒 daemon、cpu 不在 info | 分別符合 child=null、環境／cwd fallback、pool=null |
| JSON stdout 混入 health／agent 標記文字 | 無；目前這些收集函式不印東西，最後才一次輸出 |
| 其他 bug | 除上述項目，無新增發現 |