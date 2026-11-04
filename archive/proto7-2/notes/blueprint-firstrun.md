← [續推計畫](plan-2026-10-09-next.md)｜[代定清單](decisions-2026-10-09.md)｜新手結果 [newbie](play/2026-10-09-newbie/README.md)｜分線 [blueprint-firstrun-teams.json](blueprint-firstrun-teams.json)

# 整體第一次體驗：一個指令起一個會做事的 node

## 1. 病根與藥

U 隊十個包全不過，病根一樣：**第一次跑就得親手碰 daemon、回合、帳、預留／結算、ack、退出碼**，而且十個包各教一次。藥不是再改十份 README，是**加一個共用入口 `aos7-up`，把這些全部藏到預設值後面**：新人只要認得「node、心跳、工作簿、信、技能」五個詞、會打三個指令，就能看到一個 node 跑起來、收信、問 AI、回信、記進度。各包 README 照舊給進階用，但開頭改成同一種「三行頭」。

## 2. ELI5 圖（5 框）

```text
 你 ──ask '一句話'──▶ ┌信箱┐ ──信──▶ ┌─ node：AI 住的資料夾 ─────────────┐
 你 ◀──回信／status── └────┘ ◀─回信─ │ 工作簿 wf/（停在哪、下一步，做完就刪）│
                                      │ 技能 skills/（一本一個資料夾）        │
       ┌心跳┐ 每秒叫醒 node 一次 ───▶ │ 醒來：看信→翻簿→挑技能→問 AI→回信    │
       └────┘（aos7-up 起的，Ctrl-C 停）└──────────────────────────────────────┘
```

五歲版：aos7-up 蓋一間房讓一個 AI 住，房子有心跳，每秒把它叫醒一次；它醒來看信箱、翻自己的工作簿、挑一本技能、去問大模型、回信、把「停在哪」寫回簿子。帳、回合、預留、ack 都在牆裡，看不見也不用管。

## 3. 新人要學的 5 個詞、3 個指令

| 詞 | 一句白話 |
|---|---|
| node | 一個 AI 住的資料夾（`<房子>/<名字>`，上一層就是房子） |
| 心跳 | `aos7-up` 起的背景程式，每秒叫醒 node 一次（daemon／tick／回合都在這裡） |
| 工作簿 | node 的 `wf/`：停在哪、下一步；做完就刪；太厚會自動整理（compact） |
| 信 | 要 node 做事就寄信；它醒來看信、辦完回信（mail＋events 都在這裡） |
| 技能 | node 的 `skills/` 抽屜，一本一個資料夾，AI 自己挑（skills） |

```sh
aos7-up /tmp/aos/bob                       # 1. 起一個叫 bob 的 node，前景跑、印心跳；Ctrl-C 停
aos7-up ask /tmp/aos/bob '把 README 的第一段改白話'   # 2. 另開一個 shell：寄信給 bob，等它回信並印出
aos7-up status /tmp/aos/bob                # 3. 一眼看：心跳、未讀信、工作簿 open 幾項、技能幾本、AI 用量
```

第一次跑預期（約 2 分鐘）：第 1 行印 `node /tmp/aos/bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI（要真的加 --model）`，之後每秒一行 `回合 N`（有事才多印 `收到 1 封信 → 問 AI → 已回信`）；第 2 行印 bob 的回信全文；第 3 行印 5 行狀態。沒有 JSON、沒有退出碼表、沒有帳。

## 4. 接口草案（`modules/up/`，新模組，核心零改動）

**`aos7-up <node> [--model M] [-d]`**：冪等，重跑只補缺的。做七件事：①`wfnode init`（工作簿）；②建 `budget/llm` grant（預設 1000 萬 token、holder `brain`、入口照 `--model` 選 `llm.fake`／`llm.litellm`）＋ keep 任務 `budget-llm`（帳）；③`skills/` 連進 library 三本＋`index`；④裝 keep 任務 `brain`（見下）、`compact watch`、`routines`（表裡預設一列：每 300 秒 `wfnode check`）；⑤`inbox/` 由 wfnode 模板來，另建你的信箱 `<房子>/you/`；⑥`aos7-ctl register`＋起 daemon（前景；`-d` 背景，`aos7-up stop <node>` 收，算進階）；⑦印三行。所有設定落 `<node>/.aos/up.json`，進階者改檔。
**`aos7-up ask <node> '一句話' [--wait 秒]`**：`mail send you <node> REQUEST`，輪詢 `you/inbox` 等終局回信（預設 60 秒），印回信正文；逾時印「還沒回，`status` 再看」退出 0。
**`aos7-up status <node>`**：五行：心跳（活／死、回合 N）、信（未讀 n、待回 m）、工作簿（open k 項＋最後一行 state）、技能（n 本）、AI（模型、呼叫次數、token；讀 budget status）。
**`aos7-up brain <node>`**（內部，keep 任務，新人不看）：每回合 `mail read`，每封新 REQUEST：`prompt render`（模板 `modules/up/prompts/brain.json`：AGENTS.md、SESSION-LOG、NEXT-SESSION、skills 索引、這封信）→`skills pick`（可略）→`llmcall call`（call_id＝信 id）→回信 `mail done … DONE '<一句結論>' <正文檔>`→`wfnode state '<AI 給的一行>'`。同信重跑接續本地證據（llmcall 既有）；AI 回不來就回 BLOCKED，不卡回合。

藏起來的預設（代定）：回合 1 秒；帳 1000 萬 token 軟上限；`--model` 給名字即走本機 LiteLLM（`AOS7_LITELLM_URL`，預設 `http://localhost:4000/v1`）；compact 門檻沿 C2；信名、終局沿 X1／F4／F5；全部可在 `up.json` 改，但 QUICKSTART 不提。

## 5. 文件：一頁 QUICKSTART＋各包共同「三行頭」

- `proto7-2/QUICKSTART.md`（≤3 KiB）：§2 圖、§3 五詞三指令、預期輸出、「想多做一件事→去哪個包」一張 8 列表（改 AI 要讀什麼→prompt；信箱進階→mail；定時→routines；量用量→metrics…）。`proto7-2/README.md` 入口只加一行指過去。
- 各包 README 開頭統一三行，之後才是現在的內容，並在三行後加一句「第一次可以停在這裡」：
  1. **這是什麼**（一句，不含代號）；2. **一行跑起來**（`aos7-up` 起好的 node 上再加一個指令，不另起 daemon／帳）；3. **看到什麼**（一行預期輸出）。
  模板放 `modules/README-head.md`；等八個回改隊都進 main 後由 RH 隊一次套上，不跟回改隊撞檔。

## 6. 驗收

| 面 | 條 | 量法 |
|---|---|---|
| 人類 | H1 Haiku 與 luna 只讀 QUICKSTART 從零跑通三指令 ≤10 分鐘（組長估法同 U 隊） | U2 隊報告 |
| 人類 | H2 新概念 ≤5、對外指令 ≤3、五條平均 ≥7（兩位取差） | 同上 |
| 人類 | H3 兩位答「ELI5 之後不複雜」 | 同上 |
| 系統 | S1 `aos7-up` 重跑三次結果同；daemon SIGKILL 後再 `up` 接回，信與帳不丟 | modules/up/tests |
| 系統 | S2 `ask` 假 AI 一圈 ≤3 回合回信；`--model` 真 AI 一圈過且帳有紀錄 | 同上＋examples/real.sh |
| 系統 | S3 wfnode check 0 BROKEN；10 封信後 SESSION-LOG 只剩 open | 同上 |
| 系統 | S4 每包 README 三行頭 wf-lint 過、第二行在 `aos7-up` 的 node 上實跑過 | RH 隊 |

## 7. 不做

不改 lib/；不改十個包的程式與 README（回改隊領地）；不碰 A5 學徒與 llmcall 小修的檔；不做多 node 團隊、不做真 AI 預設開（錢）；kernel／agent 正式層另案，brain 只是把現有包串起來的最薄一條。

## 8. 代定（頂層核，記進代定清單）

- D1 入口名 `aos7-up`，放 `modules/up/`（不進 bin/ 核心）；前景跑為預設，Ctrl-C 收乾淨。
- D2 預設假 AI；真 AI 只靠 `--model`，不讀全域設定自動開。
- D3 帳、回合、預留、ack、退出碼在 QUICKSTART 零出現；各包 README 三行頭也不出現。
- D4 brain 一回合最多處理一封信，先進先出；失敗回 BLOCKED 不重試（重試留下一輪）。
- D5 `you` 當人的信箱名，固定。
