# aos 接下來要做什麼

← [文件索引](README.md)｜[aos 是什麼](overview.md)｜模型來源 [`wf/workflows/ideas/`](../wf/workflows/ideas/README.md)

這份只回答**順序**：既然回合制模型已經定了方向，接下來該先做哪一塊、哪些事要先問
使用者、哪些明確不做。**模型本身不在這裡定義**——它在
[回合制資料夾](../wf/workflows/ideas/turn-based-folder.md) 與
[全域 LLM CPU](../wf/workflows/ideas/llm-cpu.md)，本檔與那兩份衝突時以它們為準。

各階段標了狀態：**已定**（使用者拍過板）、**建議**（本檔的主張，可被推翻）、
**待拍板**（不能由我偷偷補成答案）。

---

## 一、一句話的方向

> aos 的本體是「**資料夾 + 回合 + inst**」。LLM、tool 這些都不是新機制，是疊在上面
> 的子命令。

所以主線**不是**繼續把 llmkit 移植完，而是**先把回合原語做出來**。移植出來的那兩個
小專案要等模型立起來之後，才知道它們該長什麼形狀。

這條路線會改寫 [overview.md](overview.md) 的「一句話」：aos 現在寫成「一組 POSIX
小工具的集合」，T1 落地後它會變成「一個資料夾的回合制執行器，外加一組 POSIX 小
工具」。**overview 要等 T1 真的能跑再改**，不要先改文件。

## 二、現況盤點

### `core/inst` — 可用，而且它就是回合原語缺的那一半

`aos inst [file]` 目前的語意是：讀完整份 JSON（單筆物件或陣列）、**全部驗證通過才
開始執行**、依序 blocking 跑完。這正好就是一回合要的東西——「一批指令，要嘛整批合
法，要嘛一筆都不跑」。

關鍵的好消息：**folder 模式可以完全在 CLI 層做完**。凍結範圍是
`inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep`／`wait`／`capi*`；
[`core/inst/src/run.cpp`](../core/inst/src/run.cpp) 不在凍結名單裡
（見 [code map](../wf/workflows/common/code-map.md)）。T1 不需要解凍任何東西。

### `core/tooljson` — 底下對，介面錯

有用的是 spec 載入、schema 驗證與 exec 配方的 **argv 展開**——那一步**正是「把一個
tool call 翻譯成一筆 instruction」**，是模型真正需要的東西。

錯的是 `Body::run(args_json)` 這個形狀：它假設工具由 tooljson 自己跑起來。在回合模型
裡 tooljson **不該執行任何東西**，它應該**產出 instruction** 交給 inst。目前
`ExecBody::run()` 還回一句「尚未實作」，等於這條錯路還沒鋪下去——這是運氣好。

### `core/llms` — 底下對，介面錯（同一個病）

有用的是 transport 那一層：curl、endpoint preset、串流、capability 三態。這些是實測
過會動的水電。

錯的是 `Bot::ask()` 這個形狀：**同步問一句、回一個 `Reply`、對話狀態留在記憶體裡**。
模型要的是反過來的東西——**一次 LLM 回合的產出是「下一回合的 instruction」，狀態留在
資料夾裡**。一支 `aos llm inst <folder>` 跑完就結束，記憶體什麼都不留。

### 一句話的診斷

> 兩個小專案都把自己寫成「**函式庫，等別人呼叫**」；模型要的是「**一顆 CPU，被 inst
> `exec` 起來，讀自己的 instruction 檔，寫下一回合**」。

失敗的是**介面與狀態放哪裡**，不是底下的水電。所以是改造，不是全部丟掉——見
[決策 D4](#d4)。

---

## 三、主線階段

每階段獨立驗收，前一階段沒綠不進下一階段。

### T1 — `aos inst <folder>`：回合原語　【建議先做】

`argv[1]` 是資料夾時，改讀該資料夾的 instruction 檔，語意是「**消費一回合**」：

```text
完整讀入 → 立刻取走（見 T2）→ 以該資料夾為基準執行 → 結束
```

- 只動 `run.cpp`，不碰凍結層，不開新小專案。
- 沒有迴圈、沒有 daemon、沒有 `.aos/next/`。跑一次就是一回合。
- 沒有 instruction 檔時：安靜結束、退出碼 0（「停留在目前回合」不是錯誤）。

**驗收**：同一個資料夾連跑兩次 `aos inst <folder>`，第一次執行、第二次無事可做。
instruction 檔在執行**之前**就已經不在原位。

### T2 — 取件與投遞協定：`rename` 兩邊各一次　【建議】

回合模型的「立刻刪除」用 `rename()` 實作，一次解決兩個開放問題：

| 問題 | 做法 |
|---|---|
| 讀到寫了一半的 JSON | **生產者**寫暫存檔 → `rename` 進位置。`rename` 是原子的，讀到的一定是完整檔 |
| 原子取件 + crash 後查得到 | **消費者**把 instruction 檔 `rename` 到 `<...>/running/<turn-id>`，再執行 |

對回合語意來說，`rename` 走了就等於刪了——「先刪再跑」不變。但它順手保留了現場：
crash 之後那份 `running/` 還在，**要不要恢復是之後的決定，不是現在要做的功能**。
第一版只要求「留著、不自動重跑」。

**驗收**：在取件前、取件後執行前、執行中三個點殺掉 process，資料夾都只會呈現
「完整的舊狀態」或「完整的新狀態」，不會出現半份 JSON，也不會自動重放已經發生的
副作用。

### T3 — `.aos/next/` 彙整與發布：接出下一回合　【建議】

本回合結束後掃 `.aos/next/`，彙整成下一份 instruction 批次並發布。

- 合併順序要**確定性**（建議：檔名字典序）。
- 發布同樣走 temp + `rename`。
- 已經有一份新的 instruction 檔在位置上時**不覆蓋**（附加或延後，[待拍板](#d2)）。
- 壞掉的 next 檔：**隔離到一旁並繼續**，不要整批停住（建議）。

**驗收**：一個資料夾能自己接兩回合——第一回合的指令寫 `.aos/next/`，第二次呼叫
`aos inst <folder>` 就跑到了下一回合的內容。

### T4 — 迴圈：先不要寫 daemon　【建議】

模型說 daemon「只是反覆觸發同一個原語」。既然如此，**第一個 daemon 就用 shell**：

```bash
while true; do aos inst ./myfolder; sleep 1; done
```

這不是偷懶，是驗證：如果這樣就夠用，`core/daemon` 就還不該存在；如果不夠用，**不夠
在哪裡**會變成 `core/daemon` 的規格書（信號處理？多資料夾？狀態回報？重啟恢復？）。
先跑一週 shell loop，再決定要不要寫。

**驗收**：寫下「shell loop 撐不住的具體場景」清單。清單是空的就不做 daemon。

### T5 — 第一顆抽象 CPU：`aos llm inst <folder>`

到這裡才碰 llms／tooljson。形狀已經定了：它是**被 inst `exec` 起來的一支普通程式**。

```text
.aos 的一筆 instruction: ["aos","llm","inst","."]
        ↓ （對 inst 而言只是普通 POSIX 指令）
讀該資料夾的 LLM instruction 檔（對話、system、可用工具）
        ↓
呼叫一次模型
        ↓
把模型要的 tool call 用 tooljson 展開成 instruction
        ↓
寫進 .aos/next/ → 下一回合由 inst 執行
        ↓
結束，記憶體不留任何東西
```

這一步同時把兩個小專案矯正回來：`llms` 從「同步 ask」變成「turn producer」，
`tooljson` 從「自己 run」變成「emitter」。

**驗收**：一個資料夾裡，模型要求呼叫一個工具 → 工具在**下一回合**由 inst 真的跑起來
→ 結果回到資料夾 → 再下一回合模型看得到它。全程沒有任何常駐 process。

---

## 四、要使用者拍板的決策

以下每一題都會擋住某個階段。**我不會自己選**；下面的「建議」只是我的主張。

### D1 — `.aos` 的版面（擋 T1）

**建議：`.aos/inst/<processor>.json` 目錄式。** 也就是 process CPU 讀
`.aos/inst/proc.json`，LLM CPU 讀 `.aos/inst/llm.json`。

理由：① 使用者說的是「`.aos/inst`」（沒有副檔名），本來就讀得通「inst 是個目錄」；
② [llm-cpu](../wf/workflows/ideas/llm-cpu.md) 更早也寫過 `.aos/inst/llm.json`；
③ 加第二顆 CPU 時**不用改任何既有路徑**。今天選它的成本是零，之後才改的成本是所有
已存在的資料夾都要搬。

替代案是 `.aos/inst.json` + `.aos/llm_inst.json` 並列——更貼近「一個檔就是一個檔」，
但每加一顆 CPU 就多一條頂層路徑。

### D2 — 一回合＝一整批，還是一筆？<a id="d2"></a>（擋 T1／T3）

**建議：一整批。** `inst` 現在就是批次語意，而且有「整批驗證過才開跑」這個保證；改成
一次一筆等於丟掉它。附帶影響：T3 的「已有 instruction 檔時不覆蓋」在批次語意下最單純
的答案是**延後發布到下一輪**，不是合併兩批。

### D3 — 阻塞還是非阻塞？<a id="d3"></a>（擋 T4／T5）

**建議：T1–T5 全部 blocking，不做非阻塞。** 理由是
[inst-execution](../wf/workflows/ideas/inst-execution.md) 那條開放問題——「daemon 何時
算本回合執行完畢」——只要引入非阻塞就沒有單純答案。長 LLM 呼叫會卡住該資料夾的回合，
**這是可接受的**：那個資料夾本來就在等它。真的痛了再回來開這題。

### D4 — llms／tooljson 是原地改造還是重長一次？<a id="d4"></a>（擋 T5）

**建議：原地改造，保留兩層、砍掉一層。** 保留 llms 的 transport／串流／preset 與
tooljson 的 spec 驗證／argv 展開（都有實測價值），砍掉 `Bot::ask` 與 `Body::run` 這層
介面，換成 turn producer／emitter。全部重長會把已經驗過的 curl 與 schema 一起丟掉。

### D5 — `stderr` merge 這題還算不算數？<a id="d5"></a>（擋 T5，可延後）

[WAIT_USER](../wf/WAIT_USER.md) 上卡著「tooljson 的 exec 引擎自己寫還是動
`core/inst`」。回合模型把這題**改寫了一半**：tooljson 不再需要自己的 exec 引擎（那是
inst 的事），所以「誰擁有 exec」不用選了。但**沒有整個消滅**——tooljson 的 exec 配方
要求 `stderr.mode: "merge"`（兩條流真的共用一條管子），而 `inst` 的重導向走檔案路徑、
對 stdout 與 stderr 各開一次 `O_TRUNC`。這題現在變成「**`inst` 要不要長出 stderr merge
欄位**」，而那會動到凍結的 `exec.cpp`。

**建議：延後到 T5 真的踩到再問。** 在那之前 WAIT_USER 那條改記成「已被 T5 取代，等
T5 再重問」，不要當成 S2 的前置條件卡著。

---

## 五、三條鐵律

從 [`../agent-machine`](../../agent-machine/START-HERE.md) 借的——**只借這三條**，不借
它整套 Task tree／Receipt／中央 store：

1. **先寫下意圖，再造成外部作用；證據不完整就停住，不自動重跑。** 回合模型的「先取走
   再執行」已經是這條的一半；缺的是「停住不自動重跑」要寫進 T2 的驗收。
2. **可攜的語意，和「這台機器上正在跑什麼」，要分開放。** `.aos` 若之後要進 git，
   `running/`、PID、鎖這類東西**一定不能**跟著進去，否則 clone 到別台機器會以為舊
   process 還活著。T2 建立 `running/` 的同時就要把它 gitignore 掉。
3. **原型的檔名、JSON 欄位、目錄名都不是 ABI。** T1–T3 的版面可以改；真的要凍結是
   之後另外一次決定。

## 六、明確不做的事

寫在這裡免得被當成漏做：

- **不做中央 store、scheduler、Task tree、Receipt、crash recovery 的完整矩陣。**
  那是 `../agent-machine/full/` 的重量級設計；aos 目前的模型刻意輕。
- **不做全域 LLM daemon 與跨資料夾排程。** 那要等「一個資料夾跑得動」之後才有意義，
  而且它的前提（非阻塞）在 [D3](#d3) 被建議推遲了。
- **不做 Git checkpoint、FUSE、VFS。**
- **不繼續 llmkit 移植的 S2／S5**（見 [`reference/PORTING.md`](../reference/PORTING.md)）。
  S2 的前置決策已被 [D5](#d5) 改寫，S5 的收尾
  對象（`core/llms`／`core/tooljson` 的 docs）會在 T5 被改形狀——現在寫等於白寫。
  **`reference/` 仍然不要刪**：T5 改造時還要拿 llmkit 原文對照。
- **不先改 `docs/overview.md`。** 等 T1 能跑再改。

## 七、和既有紀錄的關係

| 檔案 | 關係 |
|---|---|
| [`wf/workflows/ideas/`](../wf/workflows/ideas/README.md) | **模型真源**。本檔只排順序，不定義模型 |
| [`wf/SESSION-LOG.md`](../wf/SESSION-LOG.md) | open 活狀態。llms／tooljson 是失敗作那條，落地方式就是本檔的 T5 |
| [`wf/WAIT_USER.md`](../wf/WAIT_USER.md) | S2 的決策已被 [D5](#d5) 改寫 |
| [`reference/PORTING.md`](../reference/PORTING.md) | S1／S3／S4 已落地的部分仍然有效；S2／S5 停用，改由 T5 決定 |

## 八、參考來源借了什麼

- [`../agent-machine`](../../agent-machine/START-HERE.md)：借的是**第五節那三條鐵律**與
  「先提交意圖 → 造成作用 → 驗證證據 → 才算完成」的次序感。**沒借**它的
  Function／Task／Receipt 詞彙與中央 store 架構——那套是為了 exactly-once 與 crash
  recovery 付的代價，aos 現在不付。
- [`../freepy`](../../freepy/README.md)：借的是 `llmkit`／`tooljson` 的**格式與錯誤
  契約**（已經在 `reference/llmkit/` 有原文）。**沒借** `agentloop` 的 Round／Handle
  ／Controller——那是「常駐在記憶體裡的 loop」，正好是第二節診斷出來的那個病。
