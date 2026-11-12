# 2026-11-04 aos-agent：統一的 agent 介面（eca＋loop／fsm agent 同一套子命令；fable 規劃，11-04 晚第二版）

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜使用者原文：11-03 兩段、11-04 三段在 [11-03 aos-agent](../../03/aos-agent.md)，11-04 的回覆與原則逐字在 [06](06-衝突與方向題.md)｜對照：[10-30 eca](../../../2026-10/30/eca/README.md)、[11-04 loop-fsm-agent](../loop-fsm-agent/README.md)｜條文：[C-51、C-52、C-53、C-54、C-56、C-68、C-69、C-73](../../../../docs/CONCEPTS/01-設計理念.md)、[N-57、N-63、N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[P-42、P-43](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**11-04 已實作**（實作時改的設計在 [05/03](05-實作步驟/03-實作時改的設計.md)）；`llm` 子介面 11-04 晚改成設定檔宣告（[think-as-function](../think-as-function/README.md)）。fable 照原則定的細節可翻案。

## 決定（使用者，11-03～11-04 晚；原文見上）

- aos-agent 是通用介面，對接 eca 與 aos 自己的 loop／fsm agent；agent＝daemon 管的一支 proc；aos_ws、aos-say／listen、aos-eca 的事全併進來，**舊指令測試全綠就直接刪**。
- 找 agent＝`AOS_DAEMON`（從 `AOS_DAEMON_STACK` 改名）→ 表上名字 → 那列的 stack；`.aos/agent.json` 擴充**不做**。
- 對象旗標 **`--target 名字`**，沒給吃 **`AOS_AGENT`**；**`aos-agent rm 名字`**；**`aos-agent add --name bob ../agents/bob`**；`status`＝`state` 別名；**`aos-agent chat`**（Ctrl-C 退出）；`source using-aos-agent.sh` 之後直接 `say --target bob "…"`。
- **`add` 只吃指定介面、內部實現無所謂（eca／fsm 都可以）、不靠特定檔案判斷是哪種**（介面見 [03](03-種類與契約.md)）。
- 「aos-agent tools/llm」→ 兩個子命令（看／改工具箱、看／換腦），做成選配子介面；「改副本。改定義那塊用aos-tools」「一個入口小程式。並且要是aos資料夾函數。可以設計宣告介面。」「aos-agent llm改正在跑著的，aos-llm改定義」（[03/01](03-種類與契約/01-tools-llm-與兩個範本要改什麼.md)、[03/02](03-種類與契約/02-子介面規格.md)）；副本不跟定義、給 `reset`。
- 兩段原則：**stack 是 proc 自己的地盤、放啥都行；對外介面四類（命令列參數、吃／設的環境變數、stdin／out／err／結束碼、信箱內容格式）**；**讀寫 agent stack 裡的檔沒問題，像 class 宣稱自己遵守某個 interface（golang interface）**。

## 一句話

**`aos-agent` 是一支給人用的指令（Python，`extras/agent/bin/aos-agent`），每個子命令只管一隻 agent；對象＝`--target 名字`（沒給看 `AOS_AGENT`），底下只做兩件事：叫 `aos-daemon-ctl`（掛、拔、起、停、暫停、找 stack）與動那隻 stack 裡 P-42 的三樣（queue、history、ctl／state）。** 一個資料夾能被 `add`，只看它有沒有在 `interfaces.json` 裡**宣告遵守 `aos-agent` 介面**——介面＝「是資料夾程式、只吃 aos 的環境變數、常駐有窗、`queue/` 收 user message、`history.jsonl` 寫回答、錯在 stderr 一行」六條＋選配子介面 `screen`（定義裡一個自己宣告介面的資料夾程式）、`tools`、`llm`（設定檔在哪）；`tools`／`llm` 改的是正在跑那隻 stack 裡的副本；裡面是 eca、fsm 或別的都一樣，aos-agent 不看、不猜（[03](03-種類與契約.md)）。子命令＝`add／rm`、`start／stop`、`pause／resume`、`ls`、`state`（＝`status`）、`where`、`say`、`listen`、`chat`、`open／close／watch`、`tools`、`llm`（[01](01-子命令.md)）。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-子命令](01-子命令.md) | 子命令總表、旗標（`--target`、`--daemon`；沒有 `--stack`）；錯誤代號在 [01/01](01-子命令/01-錯誤代號.md) |
| [02-找-agent](02-找-agent.md) | 找 agent 一條路、哪個 daemon、`using-aos-agent.sh`、chat 怎麼運作 |
| [03-種類與契約](03-種類與契約.md) | 介面 `aos-agent` 六條＋選配子介面；`interfaces.json` 怎麼宣告；[03/01](03-種類與契約/01-tools-llm-與兩個範本要改什麼.md)＝子介面總覽、副本怎麼運作；[03/02](03-種類與契約/02-子介面規格.md)＝`aos-agent/screen`、`tools` 副本規則 |
| [04-過渡與邊緣](04-過渡與邊緣.md) | 舊指令退場、失敗與邊緣表 |
| [05-實作步驟](05-實作步驟.md) | 實作了什麼（步 0～7 各一句；[05/01](05-實作步驟/01-步0範圍與測試清單.md)、[05/02](05-實作步驟/02-步6～7.md)）；實作時改的設計在 [05/03](05-實作步驟/03-實作時改的設計.md) |
| [06-衝突與方向題](06-衝突與方向題.md) | 使用者 11-04 的回覆與原則（逐字）；衝突與方向題的裁定在 [06/02](06-衝突與方向題/02-新題-11-04-晚.md)、[06/03](06-衝突與方向題/03-新題-tools-llm.md) |
