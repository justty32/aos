# 2026-11-04 aos-agent：統一的 agent 介面（eca＋loop／fsm agent 同一套子命令；fable 初步規劃）

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜使用者原文全在 [11-03 aos-agent](../../03/aos-agent.md)（11-03 兩段、11-04 三段，這裡不重抄）｜對照的兩邊：[10-30 eca](../../../2026-10/30/eca/README.md)（[02 兩塊比較](../../../2026-10/30/eca/02-A-兩塊比較-aos-agent-vs-外部-c.md)、[18 單隻 add／rm](../../../2026-10/30/eca/18-11-03-單隻-add-rm.md)）、[11-04 loop-fsm-agent](../loop-fsm-agent/README.md)（[02 跟 eca 對照](../loop-fsm-agent/02-跟-eca-對照.md) 是本規劃的底）｜零件：[extras/eca](../../../../extras/eca/README.md)（aos-eca）、[extras/human](../../../../extras/human/README.md)（aos-say／aos-listen、aos_human）、[lib/aos/aos_ws.py](../../../../lib/aos/aos_ws.py)、[bin aos-daemon-ctl](../../../../bin/README.md#aos-daemon-ctl)、[11-03 procs](../../03/procs/README.md)（名詞表、§ 8 sleeping／wake）、[11-03 stack-where](../../03/stack-where.md)｜條文：[C-52、C-53、C-54、C-56、C-69](../../../../docs/CONCEPTS/01-設計理念.md)、[C-65](../../../../docs/CONCEPTS/03-基礎設施.md)、[N-57、N-63](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-42](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**初步規劃、未裁、未實作**。本檔只記決定、fable 照原則定的結論（可翻案）、要使用者看的衝突與方向題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。loop／fsm agent 另一個 agent 正在實作成 `demo/agent-fsm/`，沒做完——本規劃以 [loop-fsm-agent 規劃](../loop-fsm-agent/01-設計.md) 為準，靠實作才知道的地方標「**等實作確認**」。

## 使用者原文

全在 [11-03 aos-agent](../../03/aos-agent.md)。本規劃照用的幾句（逐字）：「這會是通用的agent介面，可以對接上eca, aos體系的loop fsm agent」；「aos_ws,aos-say/listen,aos-ai這些之後都會整合進aos-agent」；「綜合eca和這個的特性，弄出統一的aos-agent介面」；「agent本身就是一支aos proc，由daemon管理(對，先暫時忽略直接aos-exec出來的那些)，所以我們要找agent，那就是透過環境變數AOS_DAEMON，然後藉此找到agent這個aos proc的stack」；「aos-say會去找當前資料夾下有沒有.aos/，有的話去找agent.json。這就是agent佔據資料夾的證據，如果有其他agent想要佔據資料夾，那就是看這個。當然，agent通常是不需要佔據資料夾的」；11-04「aos-agent介面感覺可以開始做初步規劃了，讓fable去吧，好了先跟我說說會有啥」。

另外照用的既有決定：11-02 晚「三個對應：open/close, start/stop, add/remove」、11-03「統一成add/rm吧」、「我預期aos-eca xxx這條指令，就是針對單個eca」、「不應該有定義(template)這東西」（add 的 XXX 就是 agent 本身）、「status和state兩個指令都可以」、「能不能改成用英文，就用我們先前的名詞表」、11-02 晚「不要封存」、11-03「那其實.stack根本不需要放到ws那邊」、10-15「少用sh」、11-03「kind這東西沒用吧，刪掉」（daemon 不收 `--kind`）。

## 決定

- 11-03／11-04（使用者，見 03 那份）：aos-agent 是通用介面；agent＝daemon 管的一支 proc；找 agent＝`AOS_DAEMON_STACK` → 表上名字 → 那列的 stack；`.aos/agent.json` 是可選的佔資料夾擴充；aos_ws、aos-say／listen 併進來。
- 11-04：初步規劃交 fable（本檔）。衝突與方向題見 [06](06-衝突與方向題.md)，等使用者裁。

## 一句話

**`aos-agent` 是一支給人用的指令（Python，`extras/agent/bin/aos-agent`），每個子命令只管一隻 agent，底下只做兩件事：叫 `aos-daemon-ctl`（掛、拔、起、停、暫停、找 stack）與動那隻 stack 裡 P-42 的三樣（queue、history、ctl／state）。** 子命令＝`add／rm`、`start／stop`、`pause／resume`、`open／close`、`ls`、`state`（＝`status`）、`where`、`say`、`listen`、`watch`、`occupy／release`（[01](01-子命令.md)）。找 agent 只有兩條路：給名字＝查 daemon 表；不給名字＝看當前資料夾的 `.aos/agent.json`（[02](02-找-agent.md)）。一隻 agent 的「種類」（eca／fsm，以後更多）從它的定義資料夾形狀認、不用旗標；種類只負責四件事——認、掛之前驗、停／拔前收尾、多印幾行狀態與畫面——其他子命令對所有種類一樣（[03](03-種類與契約.md)）。aos-say／aos-listen／aos-eca 的事全部搬進來，舊指令怎麼退場見 [04](04-過渡與邊緣.md)、方向題 3。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-子命令](01-子命令.md) | 子命令總表：各做什麼、從哪支整合來、哪些直接轉給 aos-daemon-ctl、旗標與錯誤代號 |
| [02-找-agent](02-找-agent.md) | 找 agent 的兩條路；`.aos/agent.json` 格式與規則；佔資料夾的衝突怎麼判；哪個 daemon |
| [03-種類與契約](03-種類與契約.md) | 種類怎麼認（eca／fsm／以後）；種類要提供什麼（介面契約）；eca 與 fsm 不一樣的地方怎麼統一或保留 |
| [04-過渡與邊緣](04-過渡與邊緣.md) | 舊指令（aos-say／listen、aos-eca、aos_ws）怎麼過渡；失敗與邊緣狀況表；等實作確認清單 |
| [05-實作步驟](05-實作步驟.md) | 步驟表（每步含驗證）、測試清單、要加註的條文 |
| [06-衝突與方向題](06-衝突與方向題.md) | 要使用者看的：衝突 1 條、方向題 3 題（各附背景、例子、建議） |
