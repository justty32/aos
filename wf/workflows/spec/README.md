# aos spec：入口

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜構想（只留脈絡）在 [../ideas/README.md](../ideas/README.md)

## 這是什麼

這一疊是 aos 新實作的**規定**。ideas 那 13 章講的是「為什麼」，這裡只講「要做成什麼樣」：檔案長什麼樣、指令怎麼走、壞了怎麼看得見。新實作照這疊寫程式，不用回頭翻 ideas。

三句話版本：一個資料夾就是一塊地，地裡的 `.aos/` 是機器的地盤；`aos exec` 讓一塊地走一格，`aos run` 反覆走到沒新事可做；daemon 替每塊登記的地起一支 run 看著。LLM 不是指令，是另一塊地，要用就投請求給它。

## 怎麼讀

- 第一次讀：[01 名詞表](01-terms.md) → [02 版面](02-layout.md) → [05 接力棒](05-series-format.md) → [06 走一格](06-exec-and-run.md) → [07 呼叫與投遞](07-call-and-delivery.md)。讀完就知道整台機器怎麼轉。
- 要寫編譯器：03、04、05。要寫 daemon：08。要接 LLM：09。要做 agent：10、11。要做指令面：12。要寫測試：14。
- 每檔最後兩段固定：「待使用者拍板」（那檔裡還沒被使用者批過的條款）與「現況對照」（今天的程式碼差在哪）。

## 條款怎麼編、怎麼標

- 編號 `S-NN-MM`：第 NN 份檔的第 MM 條。例：`S-05-03`＝05 接力棒那份的第 3 條。
- 三個規定用詞：**必須**（不照做就不是 aos；每條必須在 [14](14-conformance.md) 對一個可測的檢查）、**建議**（照做較好，不照做也合規）、**禁止**（做了就不是 aos）。
- 每條句尾標來源，只有三種：
  - 〔裁決 YYYY-MM-DD〕：使用者拍板。含 2026-09-05 上午那 8 條、當天下午裁決單上答的 40 條，與 2026-09-04 那批 13 條（M-01 整批升格）。
  - 〔預設 2026-09-05，X-NN〕：照 ideas 待決定總表「我建議的預設」寫，使用者還沒批。X-NN 是待決定編號。
  - 〔主編補〕：ideas 沒講，主編為了讓 spec 閉合而補的。
- 矛盾時的優先序：使用者裁決（2026-09-05 兩批）＞ ideas 各章〔裁決〕 ＞ 建議預設 ＞ 主編補。
- 舊講法「子的固定產出資料夾」不再出現；一律是「父指定的結果落點」（I-01）。

## 目錄

| 檔 | 一句話 |
|---|---|
| [01-terms.md](01-terms.md) | 名詞表：正文只用這些詞 |
| [02-layout.md](02-layout.md) | `.aos/` 裡有什麼、誰寫誰讀、進不進 git、版本欄 |
| [02b-layout-rules.md](02b-layout-rules.md) | 設定檔、子地怎麼開、記憶就是地、版本不合、地 id、tmpfs |
| [03-source-and-compile.md](03-source-and-compile.md) | 原稿 json 格式、編譯器怎麼拆平、吐出什麼、拒絕什麼 |
| [04-inst-format.md](04-inst-format.md) | 一筆指令的欄位、嚴格解析寬鬆執行、執行結果檔 |
| [05-series-format.md](05-series-format.md) | 接力棒 `series.json`：串、游標、成敗、在等、去重 |
| [05b-series-lifetimes.md](05b-series-lifetimes.md) | 暫存器替換、兩種壽命、多寫者 |
| [06-exec-and-run.md](06-exec-and-run.md) | 一格的精確順序、鎖、一格有界、子地、原稿 |
| [06b-run-rules.md](06b-run-rules.md) | run 三種走法、通用停法（含「在等」）、預算、停止原因檔、崩了怎麼接 |
| [07-call-and-delivery.md](07-call-and-delivery.md) | 開子地（同步／脫節）、呼叫記錄、三態與狀態檔、投遞協定 |
| [07b-result-path.md](07b-result-path.md) | 結果落點的規矩：原點、合法範圍、原子發布、用量檔、`message` 不可信 |
| [08-daemon.md](08-daemon.md) | 登記表格式、`aos daemon`、每地一支子行程、控制收件匣 |
| [08b-daemon-reconcile.md](08b-daemon-reconcile.md) | 對帳、巡邏與清理、一次全停、`aos mv` |
| [09-llm-world.md](09-llm-world.md) | LLM 世界：請求格式、處理單元表、帳簿、`aos llm` |
| [09b-llm-queue.md](09b-llm-queue.md) | LLM 世界的一輪、排隊、請求狀態、重啟、保留期 |
| [10-agent.md](10-agent.md) | agent 資料夾的形狀、限制參數、每圈 prompt、停法 |
| [10b-agent-loop.md](10b-agent-loop.md) | agent 的圈：一份能過 schema 的模板骨架 |
| [11-tools-and-contacts.md](11-tools-and-contacts.md) | 工具登記表、通訊錄、子命令 |
| [11b-tool-envelope.md](11b-tool-envelope.md) | 給模型看的一行、錯誤封套、一次往返幾格 |
| [12-cli.md](12-cli.md) | 子命令全表、退出碼、控制介面 |
| [12b-roster-and-canon.md](12b-roster-and-canon.md) | 三層名字、`init`／`reset`／`migrate`、核心名冊、正本與版本欄、回寫鐵律 |
| [13-doorman-l1.md](13-doorman-l1.md) | 門房第一級：只看不擋 |
| [14-conformance.md](14-conformance.md) | 每條「必須」對一個可測的檢查：怎麼跑＋測不到的「必須」清單（表本身在 [data/conformance.json](data/conformance.json)） |
| [schemas/](schemas/) | 每種 json 一份 JSON Schema，schema 是正本 |

寫 spec 那天的材料（使用者拍板原文、83 條邊緣狀況與主編的取捨、舊資產盤點）在 [notes/](notes/README.md)；能跑的 Python 原型在 repo 根目錄 `proto/`，它撞到的事在 `proto/FINDINGS.md`。

## 條款來源與主編裁決（已下放）

> 2026-09-25 整理：本檔原本 13.5 KB，超過 8 KB。照「導航表超 8 KB 就往下一層放」，四節主編帳（條款來源表、主編裁的矛盾、條款統計與審稿卡點、整疊層級的八題）按標題逐字搬進 [`clause-sources/`](clause-sources/01-條款來源表.md)；本檔只留入口、讀法、編號規則、目錄與現況對照。

| # | 檔 | 段落 | 大小 |
|---|---|---|---|
| 1 | [01-條款來源表.md](clause-sources/01-條款來源表.md) | 條款來源表；主編裁的矛盾（13 條） | 5.2 KB |
| 2 | [02-條款統計與審稿卡點.md](clause-sources/02-條款統計與審稿卡點.md) | 條款統計與審稿卡點；整疊層級的八題：2026-09-05 全部拍板 | 3.1 KB |

## 現況對照

今天的程式碼（`core/exec`、`core/loop`、`core/agent`…）沒有接力棒、沒有呼叫記錄、沒有 daemon 登記表、LLM 是同步等 HTTP；agent 住在 `.aos/agents/` 裡。這疊 spec 是新實作的起點，不是對現有程式的描述。
