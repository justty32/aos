# 2026-11-04 aos-agent：統一的 agent 介面（eca＋loop／fsm agent 同一套子命令；fable 規劃，11-04 晚第二版）

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜使用者原文：11-03 兩段、11-04 三段在 [11-03 aos-agent](../../03/aos-agent.md)，11-04 的五段回覆與原則逐字在 [06 檔末](06-衝突與方向題.md#使用者回覆11-04逐字)（這裡不重抄）｜對照的兩邊：[10-30 eca](../../../2026-10/30/eca/README.md)（[18 單隻 add／rm](../../../2026-10/30/eca/18-11-03-單隻-add-rm.md)）、[11-04 loop-fsm-agent](../loop-fsm-agent/README.md)（[02 跟 eca 對照](../loop-fsm-agent/02-跟-eca-對照.md) 是本規劃的底；`demo/agent-fsm` 11-04 已實作）｜零件：[extras/eca](../../../../extras/eca/README.md)、[extras/human](../../../../extras/human/README.md)、[lib/aos/aos_ws.py](../../../../lib/aos/aos_ws.py)、[bin aos-daemon-ctl](../../../../bin/README.md#aos-daemon-ctl)、[11-03 procs](../../03/procs/README.md)、[11-03 stack-where](../../03/stack-where.md)｜條文：[C-51、C-52、C-53、C-54、C-56、C-68、C-69、C-73](../../../../docs/CONCEPTS/01-設計理念.md)、[N-57、N-63、N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[P-42、P-43](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**規劃第二版、未實作**；第二版四題使用者 11-04 晚已裁（N-63 加例外、add 不驗、daemon 表多一欄 `exec`、不留 `--stack`，[06/02](06-衝突與方向題/02-新題-11-04-晚.md#使用者裁定11-04-晚選項原文)）；`tools`／`llm` 的衝突 3、方向題 3 也裁了（改副本不改定義、llm 入口是 aos 資料夾函數＋可宣告介面、`aos-llm` 改定義）；只剩方向題 4 副本跟不跟定義（[06/03](06-衝突與方向題/03-新題-tools-llm.md#方向題-4副本要不要跟著定義變)，沒裁照建議「不跟＋reset」做）。05 已寫到可直接實作（含 11-04 四元素審查順手改的 `--timeout-s`、`WaitFailed`、N-63 反向重寫，與使用者「一起修」的 3 件必修一步）。本檔只記決定、fable 照原則定的結論（可翻案）、要使用者看的（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。第一版（11-04 下午，09334f1d）的種類認法、`.aos/agent.json`、`occupy`／`release`、「名字還是話」已照使用者 11-04 的三段回覆作廢，舊題留在 [06/01](06-衝突與方向題/01-舊題-11-04-已答作廢.md)。

## 決定（使用者，11-03～11-04 晚；原文見上）

- aos-agent 是通用介面，對接 eca 與 aos 自己的 loop／fsm agent；agent＝daemon 管的一支 proc；aos_ws、aos-say／listen、aos-eca 的事全併進來，**舊指令測試全綠就直接刪**。
- 找 agent＝`AOS_DAEMON`（11-04 晚從 `AOS_DAEMON_STACK` 改名）→ 表上名字 → 那列的 stack；`.aos/agent.json` 擴充**不做**。
- 對象旗標 **`--target 名字`**，沒給吃 **`AOS_AGENT`**；**`aos-agent rm 名字`**；**`aos-agent add --name bob ../agents/bob`**；`status`＝`state` 別名；新增 **`aos-agent chat`**（Ctrl-C 退出）；`source using-aos-agent.sh` 之後直接 `say --target bob "…"`。
- **`add` 只吃指定介面、內部實現無所謂（eca／fsm 都可以）、不靠特定檔案判斷是哪種**；之後跟使用者說介面長怎樣（本版 [03](03-種類與契約.md)）。
- 11-04 晚追加「aos-agent tools/llm」→ 加兩個子命令（看／改工具箱、看／換腦），做成選配子介面；「改副本。改定義那塊用aos-tools」「一個入口小程式。並且要是aos資料夾函數。可以設計宣告介面。」「aos-agent llm改正在跑著的，aos-llm改定義」（[03/01](03-種類與契約/01-tools-llm-與兩個範本要改什麼.md)、[03/02](03-種類與契約/02-子介面規格.md)）。
- 11-04 晚兩段原則：**stack 是 proc 自己的地盤、放啥都行；對外介面四類（命令列參數、吃／設的環境變數、stdin／out／err／結束碼、信箱內容格式）**；**讀寫 agent stack 裡的檔沒問題，像 class 宣稱自己遵守某個 interface（golang interface）**。

## 一句話

**`aos-agent` 是一支給人用的指令（Python，`extras/agent/bin/aos-agent`），每個子命令只管一隻 agent；對象＝`--target 名字`（沒給看 `AOS_AGENT`），底下只做兩件事：叫 `aos-daemon-ctl`（掛、拔、起、停、暫停、找 stack）與動那隻 stack 裡 P-42 的三樣（queue、history、ctl／state）。** 一個資料夾能被 `add`，只看它有沒有在 `interfaces.json` 裡**宣告遵守 `aos-agent` 介面**——介面＝「是資料夾程式、只吃 aos 的環境變數、常駐有窗、`queue/` 收 user message、`history.jsonl` 寫回答、錯在 stderr 一行」六條＋選配子介面 `screen`、`llm`（各是定義裡一個自己宣告介面的資料夾程式）、`tools`（登記檔在哪）；`tools`／`llm` 改的是正在跑那隻 stack 裡的副本，改定義用 `aos-tools`／`aos-llm`；裡面是 eca、fsm 或別的都一樣，aos-agent 不看、不猜（[03](03-種類與契約.md)）。子命令＝`add／rm`、`start／stop`、`pause／resume`、`ls`、`state`（＝`status`）、`where`、`say`、`listen`、`chat`、`open／close／watch`、`tools`、`llm`（[01](01-子命令.md)）。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-子命令](01-子命令.md) | 子命令總表（11-04 晚版）、旗標（`--target`、`--daemon`；沒有 `--stack`）；錯誤代號在 [01/01](01-子命令/01-錯誤代號.md) |
| [02-找-agent](02-找-agent.md) | 找 agent 一條路、哪個 daemon、`using-aos-agent.sh`、chat 怎麼運作 |
| [03-種類與契約](03-種類與契約.md) | 介面 `aos-agent` 六條＋子介面 `screen`；`interfaces.json` 怎麼宣告、沒做到怎麼報；[03/01](03-種類與契約/01-tools-llm-與兩個範本要改什麼.md)＝子介面總覽、副本怎麼運作、eca 與 agent-fsm 各要改什麼；[03/02](03-種類與契約/02-子介面規格.md)＝`aos-agent/screen`、`aos-agent/llm`、`tools` 副本規則、`aos-llm` |
| [04-過渡與邊緣](04-過渡與邊緣.md) | 舊指令退場（刪）、失敗與邊緣表、等實作確認 |
| [05-實作步驟](05-實作步驟.md) | 步驟 0～7（給實作者照做；步 6、7 在 [05/02](05-實作步驟/02-步6～7.md)）；步 0 的範圍、測試清單 15 案、要加註的條文在 [05/01](05-實作步驟/01-步0範圍與測試清單.md) |
| [06-衝突與方向題](06-衝突與方向題.md) | 使用者 11-04 五段回覆（逐字）；新題（衝突 2 條、方向題 2 題）在 [06/02](06-衝突與方向題/02-新題-11-04-晚.md)；tools／llm 新題在 [06/03](06-衝突與方向題/03-新題-tools-llm.md)；舊題在 [06/01](06-衝突與方向題/01-舊題-11-04-已答作廢.md) |
