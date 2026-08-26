# 回合制模型本體：核心理想與抽象 CPU
← [turn-based-folder](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

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

## `aos exec` 就是這個模型的實作（方向已定）

上面的狀態轉移不是另外做一套機制：**`aos exec` 針對指定資料夾底下的 `.aos/inst.json`
跑東西，這就是「持續變換」模型的實作本體**。

```text
aos exec <folder>   ==   folder(state N) + .aos/inst.json → folder(state N+1)
```

- 指定資料夾＝世界；`.aos/inst.json`＝這個世界待執行的指令流。
- 跑一次 `aos exec <folder>`＝推進一回合。
- `core/daemon` 因此不是另一種轉移機制，只是**反覆觸發同一個原語**的外殼：等待、
  觸發、彙整 `.aos/next/`、再等待。回合語意完全由 `inst` 這一層決定。

**關鍵性質：`inst` 執行的是 POSIX 指令，所以它可以承載任何東西**——包括 `aos` 自己。
上層要長出什麼能力，不必改回合模型，只要讓它成為某一筆 instruction 的 argv。這就是
下一節「抽象 CPU」能站在這層之上的原因。

## 擴充模型：抽象 CPU 疊在 inst 之上（方向已定）

LLM 這類「抽象 CPU」**建立在上述基礎之上**，不是與 `inst` 平起平坐的第二套原語。
做法是讓它以一筆普通 instruction 的身分出現在 `.aos/inst.json` 裡，例如：

```text
.aos/inst.json     ── 一筆 instruction: `aos llm exec`
                          ↓ （POSIX exec，對 exec 這顆 CPU 來說就是普通指令）
                    aos llm exec 讀 .aos/insts/llm.json（另一份 instruction 檔）
                          ↓
                    做「類似的事情」：取出、執行、推進該 CPU 的下一回合
```

- 每種抽象 CPU＝**一個 aos 子命令 + 它自己的 instruction 檔**，共用同一套「取出一
  筆、執行、寫下一回合」的形狀。
- 只有 process CPU 擁有原生的回合迴圈；其他 CPU 的回合是**被 `.aos/inst.json` 叫到時才
  取得的**——回合由下層授予，不必各自再養一支獨立迴圈。
- 新增處理器不需要新的核心機制，只需要新的子命令與新的 instruction 檔。
- **「轉介到另一顆 CPU」不是協定，就是 `exec`**：所謂把工作交給 LLM CPU，實際動作
  只是用 POSIX 跑另一支程式（`aos llm exec` 之類）。沒有訊息格式、
  沒有 IPC、沒有握手——**跨處理器的交接就是 fork/exec 本身**，要傳的東西走 argv、
  env、檔案系統（那份 instruction 檔）。
- 因此排程、隔離、資源上限這些問題都被推遲到「那支程式自己怎麼做」，而不是回合模型
  必須先回答的事。

完整的 LLM 排程、資源有限性與跨資料夾問題見 [全域 LLM CPU](../llm-cpu.md)。
