# roadmap — 邊實作邊解決拷問出的問題

← [WORKFLOWS](../WORKFLOWS.md)｜裁決總表 ideas/verdicts

**這個工作流做什麼**：十輪拷問停打後的實作進度表。**動工前查這裡**：現在在哪一階段、
這階段要先裁哪些問題、動手前讀哪些文件。**階段推進／新裁決落地就更新本檔**，並把裁決
記回對應的 ideas 檔與 verdicts。

## 現況（2026-09-30）：主線是 proto6

程式在 `proto6/src/`、plan 在 `proto6/plan/`。**分工（09-30 晚使用者定）**：先用 **Python 把整條 POC 做通，POC 由 AI 團隊寫**，使用者看結果、做裁定；**C++11 改寫放到最後**，他想親手寫的部分留到那時。這取代 09-29「程式由他親手寫、我們只規劃」的分工（更早 09-05「spec 出一部分就做原型、不寫 plan」也不再適用：proto6 有 plan）。plan 還沒依新分工改，是下一件事。
**成熟元件直接複製**：inst.json、aos-exec、`$ref` 從 proto5 原樣複製進 `proto6/src/py`，不重寫；它們的既有規則不列待問（見 [dispatch/lessons](dispatch/lessons.md) 第 8 條）。
**review**〔使用者方向 2026-09-30 晚〕：aos-exec／inst.json 成熟、他不 review；**從 tick 起他要 review**，之後程式**以好讀為先**，附導讀（從哪讀起、每檔一句、plan 步驟對應函式、AI 自做的判斷）。

下面的 M0～M5 屬 `core/` 舊線：`roadmap-run` 分支做完 M2 後於 2026-08-29 凍結、M3／M4 作廢，教訓在 [salvage](../salvage/README.md)。只當歷史。

**常備規則（任何階段都有效）**：
1. 動任何設計之前先過 verdicts A 表（別重想已裁決）與
   call-format/keep（別打掉優點）。
2. 實作中被迫下的新裁決＝正式裁決：記回 ideas 對應檔 ＋ verdicts，M0 之後同步進 SPEC。
3. 一階段的「先裁」沒裁完也可以動工——但**碰到那個決定的那一行就得停下來裁**，不准
   臨時湊合。

## 階段總覽（依序，M2 可與 M1 並行）

| 階段 | 一句話 | 先裁的問題 | 動工前讀 |
|---|---|---|---|
| M0 | 立法：建 normative SPEC | §30（做了就等於裁了） | verdicts A 表全部 |
| M1 | 批 header | §22、B1 欄位 v1 | machine-shape/instruction |
| M2 | 便宜機械件：deliver、PC、修 bug | §27 三小裁決 | T5 specs、gotchas |
| M3 | exec_loop 落地分層 | **§25、§26**、`--loop 0`、節流判準 | machine-shape/loop、core-layering |
| M4 | 名冊補完：status/recover/check | §29 | layout-and-spec、T5 specs |
| M5 | 第二顆 CPU | 四項存貨（見文末閘門） | cpu-analogy、debts、prior-work |

## M0 立法（先做；純抄錄，半天級）

建一份 normative SPEC（建議 `docs/SPEC.md`，編號條款、MUST/SHOULD），其他一切（parser
／docs／prompt）從它派生。第一批條款**全是抄已裁決**，不需要想新東西：批＝回合、
**一回合內沒有資料流**（B3，零成本、最高槓桿）、嚴解析鬆執行、`<名字>.<副檔名>.<狀況>`
命名、footprint 宣告（instruction §24：inst 應當只動哪裡、越界算什麼）、`.gitignore`
政策（debts §2：`.runi`/`inst.tempd/`/`.bad` 不進 git；`.aos/turn` 進）。
**完成定義**：`core/inst/docs/format.md` 與 `docs/aos-folder.md` 開頭聲明「normative 在
SPEC，本檔是說明」。三份真相從此有主從。
**讀**：verdicts A 表、instruction §18/§24、debts。

## M1 批 header（最大的單一設計決定）

**先裁**：① §22 凍結的矽？——直接決定 header 由**彙整層／loop** 解析還是 exec 解析
（建議：exec 永不認識 header，維持矽凍結；也就同時裁掉「$ref 取指令」進最內圈的路）。
② B1 欄位 v1：`version`、批 id、來源（祝福標記）、彙總狀態欄位置；manifest（§23）可留
v2。**動工**：format 加 header、彙整層產 header、條款進 SPEC。
**完成定義**：ISA 版本有地方放；loop 有旗標暫存器可讀（欄位存在即可，寫入可到 M3）；
批 id 讓去重成為可能。
**讀**：instruction 全檔、format-gaps、keep（argv 陣列、未知 key 拒絕**別動**）、`core/inst/docs/format.md`。

## M2 便宜機械件（不需要大裁決，可與 M1 並行）

- **`aos deliver`** ＋ C ABI `deliver`——規格已有（T5），照做。投遞檔名順手修 pid 不唯一。
- **PC：`.aos/turn`**——§27 三小裁決順手下：loop 持有、release 成功時遞增、進 git。
- **修純 bug**（gotchas D 表）：全 `core/inst/src/` 補 `fsync`；彙整崩潰窗口（發布與刪
  投遞的順序，M1 的批 id 可做去重兜底）；`.bad` 入命名標準＋誰清。
**完成定義**：外部生產者不再手刻投遞協定；崩潰後不再可能出現零長度檔。
**讀**：[T5 subcommand-specs](experiments/t5-agent-loop/subcommand-specs.md)、[gotchas handoff 節](common/gotchas.md)、`core/inst/src/handoff.cpp`。

## M3 exec_loop 落地分層（最大的一次搬遷）

**先裁**（這階段的裁決密度最高）：① **§25 loop 只收「無法成為 inst 的東西」？**——寫
`exec_loop` 第一行前必須表態，它決定歷史／排程／輪詢是 C++ 還是注入的 inst；② **§26
控制面**走投遞協定（control inbox）還是 signal/pid 檔；③ `--loop 0` 語意（目前＝忙碌
輪詢）；④ 節流判準改「有進展才不睡」（吃 M1 彙總狀態）。
**動工**：`run_loop` 搬出 `core/inst` 成獨立 core 專案（拖著 `run_internal.hpp` 一起）；
`timeout_ms` 移出最內圈（已拍板）；decode 歸位（B4：resolve 屬 decode，不屬 execute）；
loop 讀 header 旗標分支、不再只認 `result == 3`；回合歷史（依 §25 的裁決決定形式）。
**完成定義**：`core/inst` 不再知道 loop；一批全失敗會退避而不是全速重試；Ctrl-C 之外
有「停在回合邊界」的辦法。
**讀**：loop 全檔、core-layering、debts、`core/inst/src/run_loop.cpp`／`run_exec.cpp`。

## M4 名冊補完

**先裁**：§29 封閉判準（接受＝程式清單從 open question 變定理：`exec`／`loop`／
`deliver`／`status`／`recover`／`check`，到此封閉；`agent step`／`emit-context` 判 OS 層
→ 依 §25 做成 inst）。**動工**：`status`（T5 規格）、`recover`（T5 規格）、`check`
（新規格：對 SPEC 驗版面＋schema——三份真相收斂的機械手段）。版面 ownership table
（§28）與版面版本（B10 另一半）此時一起進 SPEC。
**讀**：layout-and-spec、T5 specs、turn-based-folder/decided-and-open。

## M5 第二顆 CPU（閘門後）

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
**讀**：cpu-analogy、debts、prior-work、llm-cpu。

## 決策佇列（想事情的優先順序，跟動工分開）

1. **§30**——用「做 M0」的方式下裁，不用另外想。
2. **§22 ＋ B1 欄位**——最大的單一決定，其他一切都繞著 header 轉。
3. **§25**——M3 前必裁；它同時回答 B6（排程歸屬）與中斷欠帳的歸屬。
4. **§26**——M3 前裁；建議傾向投遞協定（控制機器與下指令同構）。
5. **§29**——M4 前裁。
6. 可以一直拖著的：B5 外層契約、記憶體模型細節、LLM CPU 形狀——都在 M5 閘門後。
