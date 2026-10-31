← [入口](../2026-10-31-parts-round.md)｜涵蓋：題 B 結論｜上一份 [02-題A-parts](02-題A-parts.md)｜下一份 [04-匯流與衝突](04-匯流與衝突.md)

## 題 B 結論：不重切，維持「aos-round＋兩張表＋五薄格」，吸收草圖一點

判準＝使用者 10-31 的尺（[aos-round § 10-31](../2026-10-30-aos-round/08-10-31-使用者想法-控制流不拉-seq／if.md#10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理)）：一塊值不值得當「檔案系統公民」——(a) 會否被單獨抽換 (b) 需否跨棧 POSIX 串接 (c) 使用者／agent 會否單獨叫 (d) 演進要否被 git 單獨追。對照程式現狀（[01](01-契約核對.md)）逐塊重判：

| 塊 | (a) | (b) | (c) | (d) | 判 | 跟草圖 |
|---|---|---|---|---|---|---|
| endpoint/<名> | 強（fake／openai、`endpoint.txt` 切換） | 強 | 強 | 中 | 留格 | 同 |
| hook/* | 最強（使用者丟自己的程式） | 強 | 強 | 強 | 留格 | 同 |
| compact | 中強 | 中 | 中（已是 `hook/pre_think`） | 中 | 留格 | 同 |
| tools | 強 | 強 | 強 | 強 | 留格 | 同 |
| idle／think／act／more／finish | 弱（agent 不自帶表，10-30 方向題 1） | 弱（沒人 pipe） | **中**：一格一叫被 ask_round（`AOS_ASK_MAX_STEPS`）、aos-listen／aos-chat（「停在 think 那格」）、P-20 從 `state.txt` 接著做（`test_round_fsm` 兩案 crash 續跑）、38 案測試吃著 | 弱 | **留格** | 草圖判四項全弱→收進單體；重判三弱一中，那個「中」正是 fsm 當資料的紅利 |
| queue／history | 中（queue 佈局是協議 P-11～P-14、N-16） | 強（`aos-say`＝`aos-post send --ordered`、listen 看 stack，跨棧） | **強**：`ask_round` 用 `queue push／pop`、`demo/run.sh` 用 push；queue 397 行不是薄包 | 中 | **留格** | 草圖判「薄操作、收進單體」→不成立 |

### 兩個佐證

- ① 「aos-eca-turn 是重切預演」：**半成立**。它確實是單體、自己叫 aos-post——但代價是把 queue／history 格的邏輯（claim 順序、`current.txt`、壞信 `letter_warning`、history append）**重寫了一遍**（318 行對 queue 397＋history 139）。它證明「單體跑得起來」，不證明「queue／history 格可以收掉」；真收掉，round 與 eca-turn 就兩份重複（C-52 只寫在一處）。
- ② 「`--on-empty` 塌掉兩張 fsm 表」：**不足**。兩張表只差一行 `"10": "idle"`，aos-round 挑表就是那個開關；把 `AOS_ROUND_ON_EMPTY` 改成 argv `--on-empty` 跟重不重切無關、現在就能做（[eca 13](../2026-10-30-eca/13-實作時代定.md) 留的「不對稱、可翻案」）。表要不要留兩張是 9 行 JSON 的事，不是重切的理由。

### 代價（若重切）

- fsm 當資料的好處淡掉：「現在在哪」要單體自己落檔→重造一個 `state.txt`（C-56 不另造一套）；P-20 續跑要自己做；N-36 分岔（10-30 為 round 而改）失去主要使用者。
- trace：fsm 一格一行退場，單體得自己寫（aos-eca-turn 現在寫 `unit` 行）；aos-listen／aos-chat／`aos_ws.py` 兩種形狀都認、不壞，但「停在哪格」變不出來。
- 逐狀態抽換：價值低（10-30 方向題 1 已說「等真有需要再開槽」），損失小。
- 測試：`test_round_fsm` 13、`test_round_bin` 7 要重寫，`test_nia`、`test_human`、`test_ai_tools` 的 trace／state 斷言要改，約 30～40 案；proto8 全套 800 案的 4～5%。
- 跟使用者 10-30 決定相撞：「裡面的迴圈那塊可以用loop/fsm實作…整個框架則化作aos-round…一層薄殼」（[eca § 翻案](../2026-10-30-eca/11-10-31-使用者想法-turn-改名-把-tu.md#翻案round-化作-aos-round-薄殼10-30使用者澄清)），實作第 1～7 步剛做完（`771747e1`～`ef379dc7`）。列成 [衝突 3](04-匯流與衝突.md#衝突)。

### 結論

1. **不重切**。五格與 queue／history 都過得了 (c)；草圖的兩個佐證撐不起；10-31 使用者「暫時沒啥問題…先這樣」本來就是不動。
2. **吸收**：`AOS_ROUND_ON_EMPTY` 改 argv `aos-round --on-empty stop|idle`（與 aos-eca-turn 對稱；C-51 10-31 加註「再靈活一些，可以用上環境變數或argv指定」），round 槽從 parts.json 消失；兩張表照留。使用者 10-31 剛對這點說「都按照預設」但「之後可重訪」——放進實作計畫 A3、標「要他點頭」。
3. **日後何時重切**：寫成門檻，見 [方向題 2](05-方向題與實作計畫.md#方向性問題)。
