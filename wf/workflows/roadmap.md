# roadmap — 邊實作邊解決拷問出的問題

← [WORKFLOWS](../WORKFLOWS.md)｜裁決總表 [ideas/verdicts](ideas/verdicts.md)｜每階段怎麼跑 [build-cycle](build-cycle/README.md)

**這個工作流做什麼**：十輪拷問停打後的實作進度表。**動工前查這裡**：現在在哪一階段、
這階段要先裁哪些問題、動手前讀哪些文件。**階段推進／新裁決落地就更新本檔**，並把裁決
記回對應的 ideas 檔與 verdicts。

**常備規則（任何階段都有效）**：
1. 動任何設計之前先過 [verdicts A 表](ideas/verdicts.md)（別重想已裁決）與
   [call-format/keep](ideas/call-format/keep.md)（別打掉優點）。
2. 實作中被迫下的新裁決＝正式裁決：記回 ideas 對應檔 ＋ verdicts，M0 的 SPEC 立起來之後同步進 SPEC。
3. **每個階段照 [build-cycle](build-cycle/README.md) 跑**：先寫規劃 spec 交使用者點頭，
   再寫實作 plan 交點頭，才動手（動手階段交棒 feature-dev）。
4. 一階段的「先裁」沒裁完也可以動工——但**碰到那個決定的那一行就得停下來裁**，不准
   臨時湊合。

> **2026-08-28 使用者重排**：**inst 先、loop 是下一步**。原 M0（立法）縮成只管 inst 側、
> 吸收原 M1 的裁決（§22＋B1 現在裁、header 只立法不實作）；原 M0 的 loop 側條款與原
> M2 的機械件合併成新 M1。序列化拷問**未解禁**，仍是 M4 存貨。

| 階段 | 一句話 | 先裁的問題 | 動工前讀 |
|---|---|---|---|
| M0 ✅ | **inst 與序列化定案**：SPEC 殼＋inst 條款＋格式凍結（含 header 立法） | ~~§30、§22、B1~~ 已裁 | [SPEC](../../docs/SPEC.md) |
| M1 | **loop 側立法＋便宜機械件**：命名/版面/交接/git 條款收編、deliver、PC、修 bug、header 產生 | §27 三小裁決 | T5 specs、gotchas |
| M2 | exec_loop 落地分層 | **§25、§26**、`--loop 0`、節流判準 | machine-shape/loop、core-layering |
| M3 | 名冊補完：status/recover/check | §29 | layout-and-spec、T5 specs |
| M4 | 第二顆 CPU | 四項存貨（見文末閘門） | cpu-analogy、debts、prior-work |

## M0 inst 與序列化定案（**已完成 2026-08-28**，項目封存於 [build-cycle/archive/inst-spec](build-cycle/archive/inst-spec/spec.md)）

立起 `docs/SPEC.md`（唯一 normative；分區編號、MUST/SHOULD、每條附來源），收編 **inst
側**現況（批＝回合、一回合內沒有資料流 B3、嚴解析鬆執行、欄位表**搬家**自 format.md、
無上限及其代價），並**現在就裁** §22（凍結的矽：exec 永不認識 header、`$ref` 不擴到取
指令）與 B1 欄位 v1（version、批 id、來源標記、彙總狀態欄；建議 sidecar 檔）。header
**只立法、不實作**；零 C++。B／D／E 區（命名、交接、git）留佔位給 M1。
**結果**：`docs/SPEC.md` 已立（A／C／F 區條款＋B／D／E 佔位＋「已知未決」附錄四條）；
format.md 兩張表搬入 SPEC；五條裁決記入 [verdicts A 表](ideas/verdicts.md)。

## M1 loop 側立法＋便宜機械件

**立法**（原 M0 剩餘）：命名標準（含 `.bad` 正名）、`.aos/` 版面、交接協定三步、
footprint 宣告（§24）、`.gitignore` 政策（debts §2：`.runi`/`inst.tempd/`/`.bad` 不進
git；`.aos/turn` 進）收編進 SPEC B／D／E 區；`docs/aos-folder.md` 此時整份降為說明。
**機械件**（原 M2）：
- **`aos deliver`** ＋ C ABI `deliver`——規格已有（T5），照做。投遞檔名順手修 pid 不唯一。
- **PC：`.aos/turn`**——§27 三小裁決順手下：loop 持有、release 成功時遞增、進 git。
- **header 的產生**：彙整層寫 header sidecar（M0 立的法在此落地）。
- **修純 bug**（gotchas D 表）：全 `core/inst/src/` 補 `fsync`；彙整崩潰窗口（批 id 做
  去重兜底）；`.bad` 誰清。
**完成定義**：外部生產者不再手刻投遞協定；崩潰後不再可能出現零長度檔；SPEC 六區全部
有條款，三份真相收斂完成。
**讀**：[T5 subcommand-specs](experiments/t5-agent-loop/subcommand-specs.md)、[gotchas handoff 節](common/gotchas.md)、[debts](ideas/machine-shape/debts.md)、`core/inst/src/handoff.cpp`。

## M2 exec_loop 落地分層（最大的一次搬遷）

**先裁**（這階段的裁決密度最高）：① **§25 loop 只收「無法成為 inst 的東西」？**——寫
`exec_loop` 第一行前必須表態，它決定歷史／排程／輪詢是 C++ 還是注入的 inst；② **§26
控制面**走投遞協定（control inbox）還是 signal/pid 檔；③ `--loop 0` 語意（目前＝忙碌
輪詢）；④ 節流判準改「有進展才不睡」（吃 M0 立的彙總狀態欄）。
**動工**：`run_loop` 搬出 `core/inst` 成獨立 core 專案（拖著 `run_internal.hpp` 一起）；
`timeout_ms` 移出最內圈（已拍板）；decode 歸位（B4：resolve 屬 decode，不屬 execute）；
loop 讀 header 旗標分支、不再只認 `result == 3`；回合歷史（依 §25 的裁決決定形式）。
**完成定義**：`core/inst` 不再知道 loop；一批全失敗會退避而不是全速重試；Ctrl-C 之外
有「停在回合邊界」的辦法。
**讀**：[loop](ideas/machine-shape/loop.md) 全檔、[core-layering](ideas/core-layering.md)、[debts](ideas/machine-shape/debts.md)、`core/inst/src/run_loop.cpp`／`run_exec.cpp`。

## M3 名冊補完

**先裁**：§29 封閉判準（接受＝程式清單從 open question 變定理：`exec`／`loop`／
`deliver`／`status`／`recover`／`check`，到此封閉；`agent step`／`emit-context` 判 OS 層
→ 依 §25 做成 inst）。**動工**：`status`（T5 規格）、`recover`（T5 規格）、`check`
（新規格：對 SPEC 驗版面＋schema——三份真相收斂的機械手段）。版面 ownership table
（§28）與版面版本（B10 另一半）此時一起進 SPEC。
**讀**：[layout-and-spec](ideas/machine-shape/layout-and-spec.md)、T5 specs、[turn-based-folder/decided-and-open](ideas/turn-based-folder/decided-and-open.md)。

## M4 第二顆 CPU（閘門後）

被四項**存貨**（拷問停打時剩下、使用者未解禁）擋住，動這階段前先解：

1. **序列化格式**——使用者裁過「晚點再說」。屆時再約一輪拷問（存貨：數字精度、串流
   解析、inst.json 過大時嚴解析的攻擊面）。
2. **外層契約**（B5）——使用者還沒想好；唯一會反噬基石的題目，有草案才能打。
3. **LLM CPU 那顆 daemon 的形狀**——投遞什麼、怎麼組批、讀哪些文件當 context；十輪
   全在打 process CPU 這半邊，這邊連草圖都沒有。
4. **匯聚 lib-vs-inst**（keep 結尾的問題）——原語若真能承載任何東西，匯聚為什麼是注入式
   lib？一句話就能裁，裁了就是原語的邊界宣告。

隨後才輪到：記憶體模型（debts §1，至少一句話說明兩顆 CPU 寫入如何排序）、中斷／
doorbell（debts §3，依 §25 歸 loop）。
**讀**：[cpu-analogy](ideas/call-format/cpu-analogy.md)、[debts](ideas/machine-shape/debts.md)、[prior-work](ideas/prior-work.md)、[llm-cpu](ideas/llm-cpu.md)。

## 決策佇列（想事情的優先順序，跟動工分開）

1. **§30 ＋ §22 ＋ B1 欄位**——全在 M0 的 [inst-spec](build-cycle/inst-spec/spec.md)
   閘門 ① 一起裁（五個「先裁」列在該檔）。
2. **§27 三小裁決**——M1 動工時順手下。
3. **§25**——M2 前必裁；它同時回答 B6（排程歸屬）與中斷欠帳的歸屬。
4. **§26**——M2 前裁；建議傾向投遞協定（控制機器與下指令同構）。
5. **§29**——M3 前裁。
6. 可以一直拖著的：B5 外層契約、記憶體模型細節、LLM CPU 形狀、**序列化拷問**——都在
   M4 閘門後。
