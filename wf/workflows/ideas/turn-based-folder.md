# 指定資料夾的回合制演化模型

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

## 核心理想（基礎模型已定）

把 `inst` 視為「指定資料夾的狀態轉移函數」。它類似遊戲裡的 `process(delta_time)`：
輸入目前狀態，推進世界，再得到新的資料夾狀態；但 aos **不以經過時間作為語意輸入**，
而是採回合制。

- 指定資料夾是被演化的世界／狀態容器。
- `inst` 描述一次狀態轉移；每消費並執行一份 `inst`，就是切換到下一回合。
- daemon 的輪詢週期只是實作細節，不代表世界內的 `delta time`。
- 使用者可以在回合之間介入，影響資料夾狀態或下一回合的指令。

可把最小模型寫成：

```text
folder(state N) + inst(turn N → N+1) → folder(state N+1)
```

## `aos inst` 就是這個模型的實作（方向已定）

上面的狀態轉移不是另外做一套機制：**`aos inst` 針對指定資料夾底下的 `.aos/inst` 跑
東西，這就是「持續變換」模型的實作本體**。

```text
aos inst <folder>   ==   folder(state N) + .aos/inst → folder(state N+1)
```

- 指定資料夾＝世界；`.aos/inst`＝這個世界待執行的指令流。
- 跑一次 `aos inst <folder>`＝推進一回合。
- `core/daemon` 因此不是另一種轉移機制，只是**反覆觸發同一個原語**的外殼：等待、
  觸發、彙整 `.aos/next/`、再等待。回合語意完全由 `inst` 這一層決定。

**關鍵性質：`inst` 執行的是 POSIX 指令，所以它可以承載任何東西**——包括 `aos` 自己。
上層要長出什麼能力，不必改回合模型，只要讓它成為某一筆 instruction 的 argv。這就是
下一節「抽象 CPU」能站在這層之上的原因。

## 擴充模型：抽象 CPU 疊在 inst 之上（方向已定）

LLM 這類「抽象 CPU」**建立在上述基礎之上**，不是與 `inst` 平起平坐的第二套原語。
做法是讓它以一筆普通 instruction 的身分出現在 `.aos/inst` 裡，例如：

```text
.aos/inst          ── 一筆 instruction: `aos llm next`
                          ↓ （POSIX exec，對 inst 來說就是普通指令）
                    aos llm next 讀 .aos/llm_inst（另一份 instruction 檔）
                          ↓
                    做「類似的事情」：取出、執行、推進該 CPU 的下一回合
```

- 每種抽象 CPU＝**一個 aos 子命令 + 它自己的 instruction 檔**，共用同一套「取出一
  筆、執行、寫下一回合」的形狀。
- 只有 process CPU 擁有原生的回合迴圈；其他 CPU 的回合是**被 `.aos/inst` 叫到時才
  取得的**——回合由下層授予，不必各自再養一支獨立迴圈。
- 新增處理器不需要新的核心機制，只需要新的子命令與新的 instruction 檔。
- **「轉介到另一顆 CPU」不是協定，就是 `exec`**：所謂把工作交給 LLM CPU，實際動作
  只是用 POSIX 跑另一支程式（`aos llm inst` / `aos llm next` 之類）。沒有訊息格式、
  沒有 IPC、沒有握手——**跨處理器的交接就是 fork/exec 本身**，要傳的東西走 argv、
  env、檔案系統（那份 instruction 檔）。
- 因此排程、隔離、資源上限這些問題都被推遲到「那支程式自己怎麼做」，而不是回合模型
  必須先回答的事。

完整的 LLM 排程、資源有限性與跨資料夾問題見 [全域 LLM CPU](llm-cpu.md)。

## 最基礎的 aos 使用方式（方向已定）

1. 給 aos 一個指定資料夾。
2. `core/daemon` 持續查詢該資料夾的 `.aos/inst.json` 是否有待執行內容。
3. instruction 出現後，daemon 先把內容完整讀進記憶體，**立刻刪除** `inst.json`，
   然後才執行其中的指令。
4. 指令造成的資料夾變化構成下一回合的狀態；執行期間要排入下一回合的生產者，將
   instruction 寫入 `.aos/next/` 底下的檔案。
5. 本回合執行完畢後，daemon 讀取 `.aos/next/` 下的所有檔案，彙整成 instruction
   batch，附加／發布到 `.aos/inst.json`。
6. 新的 `inst.json` 成為下一回合輸入，daemon 再次消費，形成循環。

因此 daemon 不是靠時間連續更新資料夾，而是等待離散的 instruction 批次；沒有新的
`inst.json` 就停留在目前回合。

## agent loop 如何建立在回合模型上

```text
aos daemon 監看 folder
        ↓
使用者在 folder 執行 aos agent start
        ↓
準備 .aos/ 與 agent 所需資料
        ↓
下一回合加入 aos agent init ...
        ↓
載入 folder 資訊、LLM、工具、人格與記憶
        ↓
啟動一次 LLM，完成 agent 的本回合動作
        ↓
需要繼續時，在結束前把下一步寫入 .aos/next/
        ↺
```

- `aos agent start` 是使用者在指定資料夾內啟動 agent 的入口；它準備所需內容，並讓
  `.aos/inst.json` 的下一回合包含 `aos agent init ...`。
- `aos agent init ...` 會載入該資料夾的各類資訊，包括使用哪個 LLM 思考引擎、可用
  工具、核心人格與記憶，然後觸發 agent 的第一次 LLM 動作。
- agent loop 不必是一個永遠不返回的函式。需要跨多回合長期運作的工作，在本回合快
  結束時把下一次動作寫進 `.aos/next/`；daemon 在回合結束後彙整並發布下一份
  `inst.json`，下一次消費它就形成下一回合。
- 使用者介入也成為回合模型的一部分：可以在後續 instruction 被消費前改變世界狀態，
  或提供會影響下一回合的輸入。

## 與目前 aos 元件的關係

- `core/inst` 提供「執行一次狀態轉移」的底層能力。
- `core/llms` 與 `core/tooljson` 可提供 agent 回合中的思考與工具能力。
- **`core/daemon` 是下一個要做的 core 功能**：負責資料夾監看、當前 instruction
  的消費，以及 `.aos/next/` → `.aos/inst.json` 的下一回合發布。
- agent 初始化與 LLM 回合邏輯仍是建立在 daemon／inst 之上的後續能力，不混進
  daemon 的基礎職責。

## daemon 的單回合流程（已定）

```text
等待 .aos/inst.json
        ↓
完整讀入記憶體
        ↓
立刻刪除 .aos/inst.json
        ↓
執行本回合 instruction（資料夾狀態轉移）
        ↓
掃描 .aos/next/ 下所有檔案
        ↓
彙整並附加／發布成 .aos/inst.json
        ↓
進入下一回合
```

先刪除當前 `inst.json` 再執行，是基礎協定的一部分，不等執行成功才刪。`.aos/next/`
則是本回合各個生產者提交後續動作的匯流區；daemon 只在本回合執行結束後收集它們。

## 開放問題（尚未拍板）

- daemon 如何原子地取得 instruction，避免讀到寫了一半的 JSON。
- 讀入並刪除 `inst.json` 後，daemon 或主機在執行中 crash 時，是否接受本回合遺失，
  或另設 in-flight／journal 供恢復；「先刪再跑」本身不變。
- `.aos/next/` 下所有檔案的格式（每檔 object／array）、確定性排序與合併規則。
- 彙整成功後何時刪除 `.aos/next/` 來源檔，以及發布 `inst.json` 的原子操作順序。
- 彙整時若已有使用者或其他程式建立新的 `.aos/inst.json`，如何在不覆蓋的情況下附加。
- 多個產生者同時寫入 `.aos/next/` 時，檔名、鎖定與「檔案已寫完」的交接協定。
- 某個 next 檔案無效時，是整批保留並停止、隔離壞檔，還是處理其餘檔案。
- 本回合有長命令時，daemon 是否刻意同步等待整回合結束，或執行與監看要分離；目前
  `core/inst::execute()` 會同步等待。
- 一個 daemon 只監看一個資料夾，還是能同時管理多個資料夾；其生命週期與啟停介面。
- `aos agent start`／`init` 是否必須冪等，重複執行時要保留、重建還是拒絕既有狀態。
- 回合失敗的語意：停在原回合、進入失敗回合、重試，或交由使用者另投 instruction。
- 指令以指定資料夾為 cwd 執行時的信任、安全與權限邊界。
- instruction 檔的正式路徑尚未統一：本檔流程寫 `.aos/inst.json`，新的說法是
  `.aos/inst`（可能是目錄，也可能是省略副檔名的簡稱），抽象 CPU 那側則出現
  `.aos/llm_inst`。候選布局至少有「並列檔案（`.aos/inst` + `.aos/llm_inst`）」與
  「目錄分處理器（`.aos/inst/<processor>.json`）」兩種，落地前要挑一個。
- `aos inst <folder>` 與現有 `aos inst jobs.json`（直接指定 JSON 檔）的 argv 關係：
  是同一子命令依參數型別分支，還是另開一個以資料夾為對象的模式。
- 抽象 CPU 的回合由 `.aos/inst` 授予後，該 CPU 要在本回合內同步跑完（`aos llm next`
  阻塞直到模型回覆），還是只做投遞、結果之後再取；這與
  [inst 執行策略](inst-execution.md) 的非阻塞欄位是同一個決定。
- 子命令名稱只是形狀範例，目前出現過 `aos llm next` 與 `aos llm inst` 兩種寫法；動詞
  （`next`／`inst`／`step`／`tick`）與是否所有處理器共用同一個動詞尚未拍板。

> 本條目的「核心理想」與「最基礎使用方式」已由使用者定案；開放問題只是在落地前
> 必須回答的設計點，不改變上述回合制模型。
