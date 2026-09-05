> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# inst 執行策略構想

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

## 父行程環境繼承開關

### 構想

在每筆 `inst` 增加一個布林欄位，用來明確表示子行程是否繼承 aos 父行程的環境變數。

- 開啟繼承：沿用目前行為，先取得父行程 env，再由 instruction 的 `env` 覆寫同名值
  或加入新值。
- 關閉繼承：不把父行程 env 帶進子行程；子行程只取得 instruction 明確提供的 `env`。

這個開關讓 instruction 可以在「便利地延續呼叫環境」和「較可重現、較封閉的明示
環境」之間選擇，也避免父行程中的金鑰或其他非預期變數被自動傳給子行程。

### 目前行為

目前沒有這個欄位，`core/inst` 一律走繼承模式：`spawn_prep` 先遍歷 `environ`，保留
未被覆寫的父行程變數，再加入 instruction 的 `env`。

### 開放問題（尚未拍板）

- JSON 欄位正式名稱，例如 `inherit_env` 或其他命名。
- 欄位省略時的預設值。若要保持既有 instruction 行為相容，預設 `true` 是候選，但
  尚未定案。
- 關閉繼承且 instruction 沒有提供 `PATH` 時：可執行檔查找是否仍使用系統預設 PATH，
  以及該預設 PATH 是否也要出現在子行程 env 中。
- 是否同步加入 C++ `inst_t`、C ABI getter／setter，以及序列化 round trip。
- 這會改動目前標為凍結的 `core/inst` 核心層；進入實作前需明確解除該項凍結或決定
  兼容策略。

## 非阻塞／新 thread 執行模式

### 構想（方向已定）

每筆 `inst` 增加欄位，表示該指令要同步等待，還是用「開新 thread」的非阻塞方式
執行。同時在 argv／`run` 層提供選項，設定未明示該欄位之 instruction 的預設模式。

- instruction 層：每筆可以明確選擇 blocking／non-blocking。
- runner 層：CLI argv 或 `run` options 可以設定整次執行的預設值。
- instruction 明示值應覆蓋 runner 預設；欄位省略時才採 runner 預設。
- 遇到 non-blocking 那筆之後，**下一筆立刻啟動**（真並行，不排隊）。
- **回合的邊界不因此鬆掉**：`aos exec` 仍會等**所有** thread 跑完才算本回合結束。
  non-blocking 是「同一回合之內可以並行」，不是「跨回合非同步」。這一條把
  [回合制模型](turn-based-folder.md) 那邊「何時算本回合執行完畢」直接定義掉了——
  答案是**所有 thread 都收完**。

這裡的「新 thread」是產品層的非阻塞語意。現有 `execute()` 本來就會 `fork` 子行程，
但呼叫端同步 `waitpid`；實作時要決定是讓 worker thread 托管現有同步 `execute()`，還是
新增真正的非同步／背景 process API，不能把「已有 child process」誤當成已經非阻塞。

### 明確不管的事

**多個子行程同時繼承同一個終端，stdout／stderr 會互相插入**——這不修，是使用者下
instruction 時自己要小心的事（要乾淨輸出就各自重導向到不同檔案）。

### 目前行為

目前所有 instruction 都是 blocking：`execute()` 等子行程完成才返回，同一批次的下一筆
也要等前一筆結束。長命令會阻塞目前的 `aos inst` 呼叫。

### 開放問題（尚未拍板）

- JSON 欄位、CLI flag 與 `run` option 的正式名稱，以及最外層預設是 blocking 還是
  non-blocking。
- non-blocking 工作由誰持有與回收，避免 detached thread／child 變成失控工作或 zombie。
- runner／CLI 已返回或 daemon 關閉時，背景工作要繼續、等待、取消，還是移交其他服務。
- `timeout_ms`、`exit` 狀態檔、signal／錯誤結果在非阻塞模式下由誰追蹤與寫回。
- 是否需要最大並行數或依賴控制。
- 是否同步擴充 C++／C ABI；這同樣會改動目前標為凍結的 `core/inst` 核心層。
  **這一項是硬阻塞**：新增 JSON 欄位一定要改 `format.cpp`（它對不認得的 key 直接回
  `UnknownKey`），thread 化要改 `exec.cpp`／`run.cpp`。落地前必須明確解凍，不能繞過。
