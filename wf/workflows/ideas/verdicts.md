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
| **normative SPEC（§30）** | 裁於 2026-08-28：[`docs/SPEC.md`](../../../docs/SPEC.md) 是**唯一 normative**，其他派生、衝突以 SPEC 為準；verdicts＝判例索引、SPEC＝法典。裁決進入 SPEC 的流程寫在 SPEC 開頭 |
| **§22 凍結的矽** | 裁於 2026-08-28：exec 層永不長新機制，演化只在指令內容與外圈（SPEC §A-6）。推論：exec 永不認識 header、**`$ref` 不擴到取指令**（instruction §3 那條路封死，SPEC §C-9） |
| **批 header（B1）** | 裁於 2026-08-28：**sidecar 檔**（建議 `<名字>-head.json`），欄位 v1＝`version`／`id`／`origin`／`result`，彙整層寫、loop 讀、exec 不認識（SPEC §C-8，planned M1）。manifest（§23）留 v2 |
| **漂移三向標記** | 裁於 2026-08-28：已裁已實作＝直接寫；已裁未實作＝`(planned)`；未拍板矛盾＝不入條款、進 SPEC「已知未決」附錄 |
| **M1 階段裁決** | 裁於 2026-08-28（SPEC B／D／E 區條款）：§27 三小（turn 由 loop 持有、release 成功遞增、進 git）；`.gitignore` 政策取代 aos-folder 十（暫態不進、version/turn 進、inst.json＝MAY）；`.bad` 歸人／recover 清；投遞名 `<pid>-<seq>`＋排他發布；deliver 輸出單行 JSON、發布 canonical 位元組；header 檔名 `inst-head.json`；批 id＝FNV-1a 摘要兼去重依據（隨機 id 需名冊＝manifest，與「manifest 留 v2」相撞）；舊世界缺 turn 視為 0 不拒絕；去重只保證整組殘留。細節見 [build-cycle/archive/m1-loop-side](../build-cycle/archive/m1-loop-side/plan.md) 第一節 |
| **M1 審查修補三裁** | 裁於 2026-08-28（B 隊審查 28 條後，調度者拍板；SPEC §B-2／§C-8／§D-4／§D-5／§D-6）：① **header 加 `swept` 標記**——投遞清完並落盤後把 header 標 `swept:true`，**只有未 swept 的 header 才啟用去重**。內容導出的批 id 在原理上分不出「崩潰殘留」與「同名同內容的重投」，sweep 標記正好把去重的射程收斂到「sweep 沒完成」這個殘留的定義上，且不需要 manifest（不牴觸「manifest 留 v2」）。② **§D-5 耐久性射程延伸到取件與釋放**——claim 的 rename 後、release 的 unlink 後各補一次目錄 fsync，不再靠 `advance_turn` 順帶（turn 於 M2 搬到 loop 層之後那個巧合就沒了）。③ **彙整的批發布改排他**——批與 header 的 `.temp` 用每行程唯一名寫、批再 rename 進固定的 `.temp` 槽位（roll-forward 的錨），最後 `publish_exclusive()` 進 `inst.json`；`EEXIST` ＝別人先發布了，本輪放棄、不清投遞、不重寫 header。這一刀同時解掉固定名 `O_TRUNC` 共寫與併發雙重彙整（19% 重複執行的真正機制）。**去重擋投遞殘留、排他發布擋併發雙重彙整，是兩件事。** 詳見 [m1-loop-side/review/report.md](../build-cycle/archive/m1-loop-side/review/report.md) |
| **`.gitignore` 的執行者** | 裁於 2026-08-28（M1 審查修補 #14）：§E-4 原本是一條**沒有執行者**的法。定為 **`aos init` MUST 建立 `.aos/.gitignore`**（內容照 §E-4：`*.temp`／`*.runi`／`*.bad`／`*.tempd/` 排除；`version`／`turn` 納入；`inst.json`／`inst-head.json` 是 MAY 所以不寫進 ignore）；**舊世界缺這個檔 MUST NOT 視為錯誤**。條款寫進 §B-2 版面樹 |

## B. 仍開著（值得打）

1. ~~**「批」沒有名字、沒有 header**~~ — **已裁（2026-08-28）**：header sidecar＋欄位
   v1，見 A 表「批 header」與 SPEC §C-8。實作在 M1。
2. **loop 沒有可分支的狀態** — 「loop 是控制流」目前是志向；`result` 只有 `== 3` 被用過。
3. ~~**一個回合內沒有資料流**（實測）~~ — **已立法（2026-08-28）**：SPEC §A-3。
4. **四階段管線沒被命名** — fetch(claim)／decode(resolve)／execute／writeback(exit)。
   照這條線 **decode 目前卡在錯的一層**，而 **writeback 只有單筆、沒有整批**。
5. **外層契約會反噬基石** — 一旦外層有型別與回傳值，inst 可能退化成啟動器。使用者**還沒
   想好**。
6. **跨資料夾排程屬於 `exec_loop` 還是更外層** — 決定 `exec_loop` 的介面是「跑這個資料
   夾」還是「跑這一組」。
7. **`.aos` 版面需要第二個軸** — events／status 不是 `inst.json` 的「狀況」，塞不進
   `<名字>.<副檔名>.<狀況>`。
8. ~~**沒有 `deliver`**~~ — **已做（M1，2026-08-28）**：`aos deliver` 子命令＋C ABI
   （`aos_deliver_buffer`／`aos_deliver_file`）落地，SPEC §D-3。
   > [T5 實測](../experiments/t5-agent-loop/subcommand-specs.md)開出的五支裡，
   > `aos recover`／`aos status --json` 仍缺（M3）；`aos agent step`／
   > `aos agent emit-context` 未排。
9. **沒有控制介面** — 沒有 `aos status`、沒有 pid 檔、不能暫停。同上，`aos status --json`
   與 `aos recover` 的規格已在 T5 那份裡。
10. ~~**格式沒有版本，版面也沒有**~~ — **已裁（2026-08-28）**：格式版本＝header 的
    `version`（SPEC §F-1，planned M1）；版面版本＝`.aos/version`（已存在，SPEC §F-2）。
11. **規範有三份真相且在漂** — **主從已定（2026-08-28）**：SPEC 唯一 normative，inst
    側（欄位表／驗證表）已搬入 SPEC 收斂；loop 側（版面／交接）的收編在 M1。機器可讀
    schema 仍缺（`aos check` 那步）。
12. **第十輪整組（§22–30）** — **§22 與 §30 已裁（2026-08-28，見 A 表）**。仍開：
    **§25 loop 只收無法成為 inst 的東西**（M2 前必裁，一次回答 B6 與中斷欠帳）；§26
    控制面走投遞協定 or ad-hoc（M2 前）；§29 名冊封閉判準（M3 前）。缺口類：opcode
    懸空（§23，header v2 的 manifest 欄可補）仍在；~~footprint 宣告（§24）~~ **已入
    SPEC §E-2（M1）**；~~**PC 不存在**（`.aos/turn`）~~ **已做（M1，SPEC §B-3）**；
    版面 ownership table 仍缺（M3 進 SPEC）。
13. **`path` 是 symbol、handle 才是 capability** — 這條**推不到上層**：namespace 必須在
    `fork` 之後、`execve` 之前建，只有 exec 層碰得到。與「安全交給別人」的裁決有出入。

## C. 欠帳（已下裁決相乘產生的，不是待辦）

| 欠帳 | 來自哪個裁決 |
|---|---|
| **兩顆 CPU 共寫一份記憶體，沒有記憶體模型**（沒有 barrier／happens-before／去重） | GPU 模型 |
| **沒有中斷線** — 非同步結果只能靠每回合塞一筆輪詢指令 | GPU 模型 |
| **git 撞上 `.aos/` 的暫態** — 回滾含 `.runi` 的 commit 會讓世界死鎖。~~`.gitignore` 政策還沒寫~~ → **已寫（M1，SPEC §E-3／§E-4）**；欠帳本身（回滾語意）仍在 | 用 git 做快照 |

→ [machine-shape/debts](machine-shape/debts.md)

## D. 已驗證的實作缺陷（跟設計問題分開）

可查版本在 [common/gotchas](../common/gotchas.md)：

- `.runi` **不是鎖**（`lstat` 後 `rename`，且 read 在 rename 之前）→ 同回合可能跑兩次
  — **仍未修**（不在 M1 範圍：spec 只點名 fsync 與彙整崩潰窗口）
- ~~**整個 `core/inst/src/` 沒有 `fsync`** → 崩潰後「保留的現場」可能是零長度檔~~
  — **已修（M1）**：寫檔全 fsync＋每次 rename 後 `fsync_dir`；兩處已知豁免（子行程的
  stream 檔、`aos_instruction_write_fd`）。SPEC §D-5
- ~~**投遞檔名用 pid 不唯一**~~ — **已修（M1）**：`<pid>-<seq>`＋排他發布
  （`RENAME_NOREPLACE`／`link`+`unlink` 退階），撞名換序號重試。SPEC §D-2
- ~~**彙整崩潰窗口**（發布後才刪投遞）→ 同一批可能執行兩次~~ — **已修（M1）**：header
  先 rename 當提交點＋批 id 去重＋roll forward。**只保證整組殘留**，部分殘留混入新投遞
  仍可能重複（照實記，不誇大）。SPEC §D-5／§D-6
- **`--loop 0`（文件唯一示範的用法）＝ 忙碌輪詢**，`interval == 0` 永不睡 — 留 M2
- **失敗算「有做事」** → 關掉唯一的節流閥；`did_work` 甚至設在執行之前 — 留 M2
- **loop 忽略除 3 以外的所有回傳值** — 留 M2
- ~~**`.bad` 是命名標準不認識的第三種狀況**~~，而且沒人清 — 命名**已正名收編（M1，
  SPEC §B-1 的封閉狀況清單）**；「誰清」也已裁（SPEC §D-8：彙整者 MUST NOT 自動刪，
  歸人或 `aos recover`）——`aos recover` 本身留 M3

## 最高槓桿的三件事

1. **給「批」名字與 header** — 一次解決 B1／B2／B4 與 C 的去重問題。
2. **補 `deliver`**（B8）— 最便宜，擋掉最多真實故障。
3. **把「一個回合內沒有資料流」寫進規範**（B3）— 零成本，而它是這個 ISA 最重要的約束。

> **三件都已兌現**（2026-08-28）：1 → SPEC §C-8 的 header sidecar（M1 實作）；
> 2 → `aos deliver`（M1，SPEC §D-3）；3 → SPEC §A-3（M0 立法）。下一批槓桿在
> [roadmap](../roadmap.md) 的 M2 起。

## 拷問之外還開著的東西

這份只收拷問產生的裁決。**其他 open 狀態不在這裡**：手上的 in-flight 看
[SESSION-LOG](../../SESSION-LOG.md)（含 T5 實測沒全過的驗收、規格與實作三處對不上），
等使用者親自做的看 [WAIT_USER](../../WAIT_USER.md)，研討會累積的問題看
[workshop/OPEN-QUESTIONS](../workshop/OPEN-QUESTIONS.md)。

**拷問已停打（十輪）。** 停打時剩的四項存貨（序列化、外層契約 B5、LLM CPU 形狀、
匯聚 lib-vs-inst）與實作排程都在 **[roadmap](../roadmap.md)**——邊實作邊裁，裁了記回這裡。
