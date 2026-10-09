# proto7-2 — 照使用者建議重做 daemon／tick 的第二次試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）｜上一次試做：[proto7-1](../proto7-1/README.md)

**proto7-1 之後的第二次試做：照使用者 10-04 的建議（[user-advice](../proto7/user-advice.md)）重做 daemon 與 tick。10-04 照 spec 做完基礎設施（Python 3.11+ 純標準庫）；kernel／agent 這次不做。**

## 入口

- **第一次用 → [QUICKSTART.md](QUICKSTART.md)**（一頁、三個指令起一個會收信回信的 AI node）。
- **沒跟上進度？先讀 [notes/catch-up.md](notes/catch-up.md)**（10-04 早 → 10-05 下午的追進度導讀：現在是什麼、怎麼來的、注意力該放哪；名詞表 [catch-up-glossary.md](notes/catch-up-glossary.md)）。
- **[spec.md](spec.md)**：核心 spec，只放規則，每條引 S- 條號或核心選項；條目上的 P2-／A2-／A3- 只是編號，由來寫在 problems。
- **[modules/README.md](modules/README.md)**：模組包總覽（每包做什麼、接法、預設、依賴、入口檔），各包的規則在各包 README；會停下等人的情況與恢復步驟在[診斷包](modules/diag/recovery.md)。
- **[notes/problems.md](notes/problems.md)**：照 spec 做的時候碰到的問題與各條的由來（沒有待你決定的），含 astra 第一輪 A2、第二輪 A3 的處理，與核心精簡刪掉的誤用保護、搬出核心的設計。
- [notes/changes-from-7-1.md](notes/changes-from-7-1.md)：跟 proto7-1 的對照表，最後是 W1～W12（程式照推薦做）。
- [notes/play/](notes/play/README.md)：astra 回歸與試玩紀錄（一輪一列）。
- [notes/reviews/2026-10-05/](notes/reviews/2026-10-05/README.md)：10-05 的 15 份 astra 審查／調查報告索引與交叉問題，等使用者挑要修哪些。
- **[notes/next-steps.md](notes/next-steps.md)**：接下來可以做的方向（10-05 報告引出的 loop7 修補候選、事件保存／LLM 作者／kernel 任務包的待決題、整理類、卡在使用者的），只列選項與預設建議。
- **[notes/core-slimming.md](notes/core-slimming.md)**：核心精簡方案——盤點、核心最小集、錯誤四分支、擴充點與模組包、kernel 任務包；已照頂層定案做完（kernel 任務包、aos7-pack 還沒做）。
- **退出碼與錯誤訊息全 aos 共用一套**（0 做到／1 做不到／2 你給的不對／3 不知道／4 交付但帳未清），見 [blueprint-errors](notes/blueprint-errors.md)。
- [notes/component-contracts.md](notes/component-contracts.md)：組件契約藍圖（Fable；各組件的職責／前置條件／保證／明確不管，錯誤四類 M 誤用／X 外部故障／B 組件 bug／G 契約缺口，A2/A3 試分類）。
- [notes/layer-interfaces.md](notes/layer-interfaces.md)：四層（daemon、tick-tock、kernel、agent）之間的交接點調查——誰寫誰讀、延遲、通用 vs 只為 agent／LLM、proto7-1 的 kernel／agent 接上來會怎樣、缺口清單。

## 一句話看改了什麼

node 改成登記、不再掃資料夾；tock 預設照固定 interval，提前 tock 變成可選；只剩 tasks.json 一個任務表（一次性任務是裡面 `mode: "once"` 的一項）；任務資料夾照名字重用，不再每回合新增；核心只留「上一次」，更前面的歷史交給可選的歷史 module。

10-04 核心精簡：核心 lib 4501→2791 行，restart／子 daemon／retry_lost／診斷／工具／稽核改成模組包。

10-09 下午新增（兩者都不動核心）：事件保存模組 [modules/events/](modules/events/README.md)（每 node 固定檔數存事件，藍圖 [blueprint-ev1](notes/blueprint-ev1.md)）、LLM 作者第一刀任務包 [packs/author/](packs/author/README.md)（假候選、不接真模型，藍圖 [blueprint-llm1](notes/blueprint-llm1.md)）。

10-09 第三段（仍不動核心）：LLM 單次呼叫閘道任務包 [packs/llmcall/](packs/llmcall/README.md)（假傳輸 `llm.fake`、不接真模型，藍圖 [blueprint-llm2](notes/blueprint-llm2.md)）；budget 改成部分結算（用多少扣多少）；author 加經事件必讀通道收單（`send`／`intake`）；事件保存兩條已知限制修掉。

10-09 晚（上一輪 r3，仍不動核心）：一次備好 node 的 [`aos7-up`](modules/up/README.md)（含收信回信的 brain）與它用到的模組包 [wfnode](modules/wfnode/README.md)、[skills](modules/skills/README.md)、[routines](modules/routines/README.md)、[compact](modules/compact/README.md)、[mail](modules/mail/README.md)、[metrics](modules/metrics/README.md)，任務包 [prompt](packs/prompt/README.md)；A5 真 AI 學徒寫的 usage、llmdiag（r4 回頭審後分別併進 metrics `job --by`、`aos7-diag --llm`，原程式搬到 [archive/usage](archive/usage/README.md)、[archive/llmdiag](archive/llmdiag/README.md)，原處留轉址 stub）；各包統一錯誤路徑（退出碼 0～4，[tests/error_path.json](tests/error_path.json)）。每包一列見 [INDEX](INDEX.md)。

10-09 深夜（r4／r5，仍不動核心）：brain 一封信可跨多步（進度信、沒進展停下問你、被殺接回不重問）、卡住信白話化、用語統一（「練習用的 AI」、進度叫「步」）；kernel 任務包 [packs/kernel/](packs/kernel/README.md)（`aos7-kernel run／status`，第一條規則 supervise-brain：腦卡住先寄信、再 kill 那個 run，藍圖 [blueprint-kernel1](notes/blueprint-kernel1.md)）。

## 怎麼跑

```sh
P=proto7-2/bin                      # 用 proto7-2 的 bin/（程式名跟 proto7-1 一樣是 aos7-*，見下）
mkdir -p /tmp/sp/team/.aos
echo '{"tasks":[{"name":"hello","argv":["sh","-c","echo hi $AOS7_RUN"]}]}' > /tmp/sp/team/.aos/tasks.json
python3 $P/aos7-ctl daemon /tmp/sp register team    # 登記（daemon 還沒起也行，起來才處理）
python3 $P/aos7-daemon /tmp/sp &                    # 只跑 .aosd/nodes.json 登記的 node
cat /tmp/sp/.aosd/status.json /tmp/sp/team/.aos/last-round.json
python3 $P/aos7-ctl daemon /tmp/sp stop --kill
```

**程式名沿用 `aos7-*`**（`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`，加搬來的 `aos-exec`）。proto7-2 的程式彼此呼叫時一律用自己 `bin/` 的絕對路徑，任務的 `PATH` 前面也加的是 proto7-2 的 `bin/`，所以不會跟 proto7-1 混；人手在 shell 裡用時，把 `proto7-2/bin` 放在 `PATH` 最前面（或像上面直接寫路徑）。

## 測試

在 repo 根跑：

```sh
python3 proto7-2/tests/run_all.py            # 全套：tests/core/、modules/*/tests/、modules/tests/、packs/*/tests/
python3 proto7-2/tests/run_all.py -k restart # 只跑名字含 restart 的
python3 proto7-2/tests/run_all.py modules/subd/tests   # 只跑某個資料夾（相對 proto7-2/）
```

測試分佈、慣例（類別標記、先收程序再刪空間）與每個測試檔測什麼，見 [tests/README.md](tests/README.md)。

## 防再胖：新功能預設進模組

核心（`lib/aos7_*.py`）有行數預算：**總行 ≤ 2800、實際程式（去空行、註解、docstring）≤ 2200**，之後收到 2000；`tests/core/test_budget.py` 量（不算 `lib/aos_*.py` 搬來的 inst 執行器、模組包、測試）。**10-09 起只印不擋**（loop7 D7：開發階段不設上限，整理階段再收、`ENFORCE` 改回 True）：loop7 後總行 2952、實際程式 2305，10-09 下午 L1 後 3004、2353，超過時逐檔表印到 stderr、測試照過。新功能**預設進模組**（`modules/<包>/`：任務、argv 包裝程式、工具三種接法，加上核心給的 `x` 透傳、事實欄位與 log.on、stop-guard.json 三個小出口）。要進核心，三件事都要答得出來：

1. 引得到哪條 S- 條（[核心 spec](../proto7/spec/core.md)）或核心選項；
2. 為什麼不能用任務、包裝程式、工具三個接面做到；
3. 它是通用的，不是只為 agent／LLM（[設計原則](../proto7/notes/principles.md)第 5 條）。

新保護先答「防的是哪一類」（[組件契約藍圖](notes/component-contracts.md)的 M 誤用／X 外部故障／B 組件 bug）：誤用的不做；外部故障只能走錯誤四分支，不加新分支。要加預算，在 [problems](notes/problems.md) 寫一行理由並經使用者同意。

## 結構

資料夾結構表（每個位置是什麼）與「來源（複製進來，不 import 外部路徑）」見 [INDEX.md](INDEX.md)。
