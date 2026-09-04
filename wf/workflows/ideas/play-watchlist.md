# play-watchlist：概念主幹已齊，玩的時候看這四條橋

← [nested-eval-sugar](nested-eval-sugar.md)｜[ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

2026-09-03 使用者問「idea 到這邊，該有的 concept 都差不多有概論了，還缺啥嗎？」——AI 回答
**主幹已齊，剩下的四條缺口全在「兩層之間那座橋」上**（`.aos` 內的機器層 vs 資料夾樹的行程
層，見 [nested-eval-sugar](nested-eval-sugar.md)）。**使用者已裁先玩不裁**（見文末），本檔是
玩的時候順手核對的觀察清單，**全為 AI 觀察（非裁決，可否決）**。

## 使用者提問（2026-09-03）

> 我覺得idea到這邊，我們該有的concept都差不多有概論了，你覺得呢？還缺啥嗎？

## AI 觀察：四條橋上的缺口（非裁決，可否決）

### 1. 父層怎麼拿到子資料夾的結果

`aos run <子資料夾>` 是**呼叫**（等它跑完才往下走）還是**派工**（丟出去自己繼續）？拿到的是
一個 `out/` 檔、一個回傳碼，還是整個資料夾的終態？這正是
[nested-eval §e](nested-eval.md#e-三個邊界)「回傳 vs 傳訊」那條邊界，**未裁**；答案決定資料夾
能不能當函數用（call）還是只能當 actor 用（send）。玩時留意：手上這次呼叫，實際上等的是誰。

[exec-run-async](exec-run-async.md) 提出：**結果＝固定路徑的檔**（AI 提議，未裁）。

### 2. 子資料夾看不看得到父層

能不能讀 `../`？**能**＝資料夾有作用域，跟父層共享一部分世界；**不能**＝每個資料夾密封，要
什麼都得靠 `deliver` 明確送進去。這也是「閉包」在這套模型裡有沒有落點的問題——
operative 拿到的環境（[nested-eval-car §d](nested-eval-car.md#d-operative-拿得到環境在-aos-就是資料夾本身)）
是不是只到父層這一格為止。這也是隔離題，見 cpu-to-os-gaps.json 的 G03（隔離歸 OS）；看不看得到是作用域概念，要不要擋是隔離實作。

[land-rules](land-rules.md)：**使用者定義預設封閉，掛載或 symlink 才開洞（未明說裁決）。**

### 3. 失敗

子資料夾跑壞、`inst` 失敗、或等太久，父層怎麼知道、怎麼處置？**完全沒討論過**。lisp 靠
condition／handler，OS 靠 exit code／signal；[os-metrics-and-resources](os-metrics-and-resources.md)
定的可預測性指標繞不開這題——沒有失敗語意，「最壞情況要有界」就無從量起。

### 4. 資料夾壽命

暫態跑到穩態之後，留著還是刪？誰動手刪？lisp 靠 GC 回收沒人再指的 cons cell，OS 靠行程結束
回收資源；**目前的模型只講了「生」（`G06` 行程誕生）沒講「死」**。

[exec-run-async-time](exec-run-async-time.md) 又多一個壽命角度：父時鐘死了，脫節子世界若繼續走，
就會變成**孤兒時鐘**；這既是 async 的好處，也是回收風險。

[daemon-clocks](daemon-clocks.md) 接著記集中登記與關機一次全停；使用者傾向父死子續走，由
daemon 重啟後對帳。

[land-rules](land-rules.md)：**使用者定義死＝刪資料夾；daemon 同查 pid＋路徑（未明說裁決）。**

## 現況與模型對不上：今天的 agent 住錯位置

今天跑起來的 agent 住在 `.aos/agents/` 內（inst 層），但照 2026-09-03 拍板的新模型，agent 應該
是一個**獨立的資料夾**（operative），要呼叫 LLM 是在它自己的 `.aos` 內下 `aos llm`。這處落差
玩的時候大概會直接撞到，先記著，不必現在改。

## 6. 誰讓脫節子世界的時鐘走

父層 fork 一個 `aos run <child>`，還是把子世界交給 daemon 接手？兩種都能讓父 tick 不等，
但壽命、重啟與誰負責收尾不同。來源見 [exec-run-async-time](exec-run-async-time.md)。

[daemon-clocks](daemon-clocks.md)：**使用者傾向全由 daemon 管，fork 先不考慮**。

## 不是缺，是已裁先玩

排程、資源計量、權限**不是漏掉沒想到**，是 2026-09-03 已經明白裁定「先停下設計、去用現有的
東西玩」——見 [os-metrics-and-resources §九](os-metrics-and-resources.md#九停下腳步先去用現有的東西玩使用者裁決2026-09-03)。

## 相關

- [nested-eval-sugar](nested-eval-sugar.md)——本檔的上游：兩層互不相關的裁決、唯一的橋是
  `aos run <子資料夾>` 這一行
- [nested-eval-car](nested-eval-car.md)、[nested-eval](nested-eval.md)——資料夾＝operative、
  回傳 vs 傳訊等邊界的源頭
- [os-metrics-and-resources](os-metrics-and-resources.md)——先玩再回來選「OS 的第一塊」的裁決
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G06`（行程誕生，只講了生）
