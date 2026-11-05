← [回入口 01-保證佈局入口.md](../01-保證佈局入口.md)｜段落：一、aos 保證的（不是慣例，是底）、二、佈局（每檔一句）｜上一份：—｜下一份：[02-三-入口-loop-fsm](02-三-入口-loop-fsm.md)

## 一、aos 保證的（不是慣例，是底）

aos 保證的底——六個環境變數（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`；§ 19）、`aos-exec [FLAGS...] XXX [args...]`（§ 15；旗標有 `--ws`、`--stack`（11-03）與 `--dotenv-override`）、aos-exec 只做那幾件事、WS 不存在或入口缺／壞時退 1、找入口的規則與 `#/` 尋址——已升成規範，見 NORMS：**P-01＝[N-57](../../NORMS/10-基礎設施-定義與工作區/01-N-57.md)、P-02＝N-58、P-03＝N-59、P-04＝N-60**；N-61（找入口與種類判斷）、N-62（`#/`）沒有對應的 P 號。這裡不重複正文，條號 P-01～P-04 只留給別處的引用。慣例（P-05 起）建立在這個底上。

## 二、佈局（每檔一句）

混合寫法（§ 10 使用者「好主意」）：狀態表一律寫在 `fsm.json`；一行講完的格內嵌單子；有真邏輯的格 `exec` 寫子資料夾名。fsm 停在哪格記在 stack 的 `stage.txt`（使用者 11-04 題 10「fsm改名，嘗試用同義詞」，[four-elements 07](../../../thinking/2026-11/04/four-elements/07-實作步驟.md) 步 3；fsm.json 的 `start`／`states` 不改），不寫 trace（N-39）。程式已照這張做完（見第十節）。〔11-04 加註：下面這棵樹是 agent-bob（舊協議：工作區題目資料夾，P-11），11-04 隨 proto8/tests 刪了，「已照這張做完」說的是當時；現行標準範本是走 queue 的 [demo/agent-fsm](../../../demo/README.md#agent-fsm)（`_entry`＝JSON `["aos-loop", "loop.json"]`、四格 idle／think／wait／act 都是單子叫範本裡的 python，P-27、P-08 的 11-04 晚加註）；樹照留，條文改不改由使用者定〕

```
agent-bob/                 一個 agent＝一個資料夾程式（§ 1）
  _entry                    入口（預設 $AOS_ENTRY），兩行：#!/bin/sh、exec aos-loop loop.json（§ 4、P-05）
  loop.json                {"exec": "fsm.json", "max": 20}：每次 aos-exec fsm.json（跑一次 fsm）、最多幾次（P-06；exec 也可以直接放單子）
  fsm.json                 整張狀態表（P-07、P-27）：_entry＝["aos-fsm", {"$env": "AOS_CF"}]（所以它本身就是 aos-exec 的入口）；
                           idle→"idle"（資料夾）、think→單子（直接寫在那格的 exec）、act→"act"（資料夾）
  idle/_entry               格：new/ 有題→0 往下走；沒題→10 請 loop 停（P-19）
  brain.py                 think 格的身體（單子 python3 brain.py，stdout 導到 $AOS_STACK/plan.txt、逾時 120 秒）：
                           取一題、從 new/ 搬到 cur/ 認領（P-12）、題名寫 stack 的 current.txt、問腦（假腦或 OpenAI 相容端點，P-23；11-04 晚起問腦＝寄信給 llm kernel），答案印 stdout
  act/_entry                格：把 plan.txt 當題目交給 tools/cathy，拿她的答案寫 $AOS_WS/out/、題目從 cur/ 搬 done/（P-24、P-32）
  act/tools/cathy/         act 的工具＝另一隻完整 agent，同一套範本（_entry、loop.json、fsm.json、idle/、brain.py、act/）；
                           act 裡寫 aos-exec tools/cathy（P-33）
  act/tools/cathy/act/tools/stamp/   cathy 的 act 的工具：stdin 前面加一行時間戳印出來、自己 stack 裡 runs.txt 計次

workspace/                 ＝$AOS_WS，使用者的（§ 2）
  new/<題名>               題目：純文字、一題一檔（拍板點 2）
  cur/<題名>               認領了、正在做的題目（think 從 new/ 搬來；Maildir 的 cur）
  out/<題名>               答案：跟題目同名
  done/<題名>              做完的題目從 cur/ 搬來這
  .stack/                  預設 $AOS_STACK（§ 2）＝bob 的 stack：stage.txt、current.txt、plan.txt（P-16）
  .stack/tools/cathy/      cathy 的小格＝她的 stack（P-32）：stage.txt、current.txt、plan.txt
  .stack/tools/cathy/ws/   cathy 的工作區（bob 備好題目、拿答案的地方）：new/ cur/ out/ done/
  .stack/tools/cathy/tools/stamp/runs.txt  stamp 的小格（P-17）
```

stack 樹就是呼叫樹：`.stack/tools/cathy/tools/stamp/` 一眼看出「bob 叫了 cathy、cathy 叫了 stamp」（P-38、P-17）。
