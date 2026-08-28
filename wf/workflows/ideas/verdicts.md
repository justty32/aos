# 拷問總表：已裁決、仍開著、欠帳

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**要重新拷問 aos 的人先讀這份。** 到目前為止已經打過十輪，涵蓋格式／原語／CPU 類比／
交接協定／前作對照／機器形狀。這份把散在各檔的**裁決**收成一張表，目的只有一個：
**不要重問已經拍板的東西，把火力放在仍開著的地方。**

## 十輪打了哪些面向

| 輪 | 面向 | 記在哪 |
|---|---|---|
| 1 | 格式與序列化的九個缺口 | [call-format/format-gaps](call-format/format-gaps.md) |
| 2 | fork/exec 這個原語夠不夠通用 | [call-format/universality](call-format/universality.md) |
| 3 | CPU 類比撐得住多少 | [call-format/cpu-analogy](call-format/cpu-analogy.md) |
| 4 | 交接協定的實作缺陷、世界／歷史／控制流 | [call-format/handoff-and-world](call-format/handoff-and-world.md) |
| 5 | 回饋路徑、失敗語意、協定完整性 | [call-format/feedback-and-failure](call-format/feedback-and-failure.md) |
| 6 | 跨 repo 前作對照（`simple_tools/docs`，早 aos 兩天） | [prior-work](prior-work.md) |
| 7 | 指令的地位、loop 的職權、資料夾與規範 | [machine-shape/](machine-shape/README.md) |
| 8 | 裁決的欠帳 ＋ `run_loop.cpp` 實測 | [machine-shape/debts](machine-shape/debts.md)、[loop](machine-shape/loop.md) |
| 9 | 沒有回合內資料流、四階段管線、彙整崩潰窗口 | 同上 ＋ [feedback-and-failure](call-format/feedback-and-failure.md) |
| 10 | （Fable）「地位」的承載物：類比可證偽性、loop 身份判準、ownership、名冊封閉、normative | [machine-shape/](machine-shape/README.md) 三檔的第十輪（§22–30） |

不該被改掉的優點收在 [call-format/keep](call-format/keep.md)——**打之前先讀那份**，免得
把對的東西打掉。

## A. 已裁決（不必再問）

| 主題 | 裁決 |
|---|---|
| **格式的定位** | fork/exec 只是呼叫**機制**、不是呼叫**約定**；它不能成為通用契約，只作為「fork/exec as CPU instruction」的**基石** |
| **`timeout_ms`** | 移出最內圈，改由 loop 層管 |
| **exit status** | 分不開傳輸失敗與應用失敗，**之後會改** |
| **daemon** | 這東西天生會變 daemon，就這樣；LLM CPU 之後是另一個 daemon |
| **抽象 CPU 的回合** | **投遞式**，不在本回合同步跑完——工作投遞到外部資料夾，好了寫回來，「類似 CPU 與 GPU 的交流」。結果落在**未來某個回合** |
| **呼叫粒度** | 本來就這樣設計：細粒度在程式內，這裡是更高層次的 CPU 指令 |
| **權限／安全** | 交給上層呼叫 `aos exec` 的那一方，核心不管 |
| **高階形式** | 確實缺，解法在**外層另做更通用的呼叫契約**（怎麼做**還沒想好**） |
| **跨機器** | 沒差，之後用 plan 9 |
| **CPU 類比的三樣無解** | 原子性、封閉 ISA、確定性——認了，這終究不是能完全類比 CPU 的 |
| **控制流** | 就是 loop；所以 `aos core` ＝ 整套 CPU 類比，loop 在 core 裡不是外掛 |
| **世界沒有圍牆** | 沒關係，快照／回滾／複製都用 **git** |
| **回合歷史** | 是實作上要加的新東西，**加在 loop** |
| **PC 不自己前進** | **這就是要的**——控制流在投遞者手上 |
| **嚴解析、鬆執行** | **刻意的**：序列化要嚴格，`inst_t` 的實際執行故意弄鬆 |
| **delta time 從 loop 走回來** | 之後在 loop 處理 |
| **停機** | 之後在 loop 內再說 |
| **第 4～6 輪的實作缺陷** | 實作時自然會遇到，要嘛放外圈、要嘛交給使用者自行 handle 風險 |
| **前作那批（`simple_tools/docs`）** | 有些可以參考，但**很多機制可以在 loop 或更外層處理** |
| **2000ms 那個常數** | 不是使用者設計的，是 AI 自己加的，別管 |

## B. 仍開著（值得打）

1. **「批」沒有名字、沒有 header** — 真正的指令是批，但被命名的是 `inst_t`。ISA 版本、
   指令來源、批次彙總狀態、去重 id 全都沒地方放。**第 1／2／6 條是同一個決定。**
   → [machine-shape/instruction](machine-shape/instruction.md)
2. **loop 沒有可分支的狀態** — 「loop 是控制流」目前是志向；`result` 只有 `== 3` 被用過。
3. **一個回合內沒有資料流**（實測）— 整批先 resolve 完才執行，`$ref` 引不到同批前一筆的
   產物。乾淨的語意，但**沒寫在任何地方**。
4. **四階段管線沒被命名** — fetch(claim)／decode(resolve)／execute／writeback(exit)。
   照這條線 **decode 目前卡在錯的一層**，而 **writeback 只有單筆、沒有整批**。
5. **外層契約會反噬基石** — 一旦外層有型別與回傳值，inst 可能退化成啟動器。使用者**還沒
   想好**。
6. **跨資料夾排程屬於 `exec_loop` 還是更外層** — 決定 `exec_loop` 的介面是「跑這個資料
   夾」還是「跑這一組」。
7. **`.aos` 版面需要第二個軸** — events／status 不是 `inst.json` 的「狀況」，塞不進
   `<名字>.<副檔名>.<狀況>`。
8. **沒有 `deliver`** — handoff 只有消費端（`aggregate`／`claim`／`release`），且**都沒進
   C ABI**；唯一由外部生產者執行的那一步沒有實作。
   > **不是新發現**：[T5 實測](../experiments/t5-agent-loop/subcommand-specs.md)已經寫出
   > `aos deliver`／`aos recover`／`aos status --json`／`aos agent step`／
   > `aos agent emit-context` 五支的需求。**規格有了，還沒做。**
9. **沒有控制介面** — 沒有 `aos status`、沒有 pid 檔、不能暫停。同上，`aos status --json`
   與 `aos recover` 的規格已在 T5 那份裡。
10. **格式沒有版本，版面也沒有** — 兩件不同的事，兩個都缺。
11. **規範有三份真相且在漂**（規格／實作文件／手寫 parser），第四份是 LLM 的理解。
12. **第十輪整組（§22–30，未裁；使用者：邊實作邊想）** — 五條是**待裁判準**而非缺陷：
    類比的可證偽版本（凍結的矽——與 `$ref` 取指令相撞）；**loop 只收無法成為 inst 的
    東西**（其餘是 OS-as-inst，一次回答 B6 與中斷欠帳）；控制面走投遞協定 or ad-hoc；
    程式名冊封閉判準（exec/loop/deliver/status/recover/check）；規範要一份 normative
    SPEC。另四條是缺口：opcode 懸空（header 加 manifest 欄可補）、核心方程要宣告
    footprint（**git 第三筆帳：拍的 ≠ 改的**）、**PC 不存在**（回合編號無表示，是歷史／
    記憶體模型／status／去重的共同前提）、版面要 ownership table。
13. **`path` 是 symbol、handle 才是 capability** — 這條**推不到上層**：namespace 必須在
    `fork` 之後、`execve` 之前建，只有 exec 層碰得到。與「安全交給別人」的裁決有出入。

## C. 欠帳（已下裁決相乘產生的，不是待辦）

| 欠帳 | 來自哪個裁決 |
|---|---|
| **兩顆 CPU 共寫一份記憶體，沒有記憶體模型**（沒有 barrier／happens-before／去重） | GPU 模型 |
| **沒有中斷線** — 非同步結果只能靠每回合塞一筆輪詢指令 | GPU 模型 |
| **git 撞上 `.aos/` 的暫態** — 回滾含 `.runi` 的 commit 會讓世界死鎖；`.gitignore` 政策是規範的一部分，還沒寫 | 用 git 做快照 |

→ [machine-shape/debts](machine-shape/debts.md)

## D. 已驗證的實作缺陷（跟設計問題分開）

可查版本在 [common/gotchas](../common/gotchas.md)：

- `.runi` **不是鎖**（`lstat` 後 `rename`，且 read 在 rename 之前）→ 同回合可能跑兩次
- **整個 `core/inst/src/` 沒有 `fsync`** → 崩潰後「保留的現場」可能是零長度檔
- **投遞檔名用 pid 不唯一**
- **彙整崩潰窗口**（發布後才刪投遞）→ 同一批可能執行兩次
- **`--loop 0`（文件唯一示範的用法）＝ 忙碌輪詢**，`interval == 0` 永不睡
- **失敗算「有做事」** → 關掉唯一的節流閥；`did_work` 甚至設在執行之前
- **loop 忽略除 3 以外的所有回傳值**
- **`.bad` 是命名標準不認識的第三種狀況**，而且沒人清

## 最高槓桿的三件事

1. **給「批」名字與 header** — 一次解決 B1／B2／B4 與 C 的去重問題。
2. **補 `deliver`**（B8）— 最便宜，擋掉最多真實故障。
3. **把「一個回合內沒有資料流」寫進規範**（B3）— 零成本，而它是這個 ISA 最重要的約束。

## 拷問之外還開著的東西

這份只收拷問產生的裁決。**其他 open 狀態不在這裡**：手上的 in-flight 看
[SESSION-LOG](../../SESSION-LOG.md)（含 T5 實測沒全過的驗收、規格與實作三處對不上），
等使用者親自做的看 [WAIT_USER](../../WAIT_USER.md)，研討會累積的問題看
[workshop/OPEN-QUESTIONS](../workshop/OPEN-QUESTIONS.md)。

**拷問已停打（十輪）。** 停打時剩的四項存貨（序列化、外層契約 B5、LLM CPU 形狀、
匯聚 lib-vs-inst）與實作排程都在 **[roadmap](../roadmap.md)**——邊實作邊裁，裁了記回這裡。
