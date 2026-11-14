# proto8 討論紀錄：2026-11

← [thinking](../README.md)

規矩見 [thinking/README](../README.md)。這個月的每天一份，一列一句：定了什麼、還有什麼未決。

| 日期 | 份數 | 一句話 |
|---|---|---|
| [2026-11-01](01/README.md) | 1 | 試驗場 bob；環境變數只在必要時用（五題已裁、格旋鈕改 argv／檔） |
| [2026-11-02](02/README.md) | 8 | cathy、工具小格 `.stack/tools/`、daemon 掛 bob、`AOS_DAEMON_STACK`、exec 像繼承、窗有變動才寫、常駐 bob（11-04 封存）、窗名就叫 `ctl.json`／`state.json` |
| [2026-11-03](03/README.md) | 7 | procs 合一（含 sleep／wake）、ctl 改下指令、stack 不放工作區、trace 拿掉、eca 接 aos 工具、aos-post 重新定位；aos-agent 介面細節未規劃、topdown 量測待使用者 |
| [2026-11-04](04/README.md) | 9 | eca 開場白檔可指定、loop／fsm agent、aos-post 信箱要不要改成一個資料夾（裁不換）、測試全刪、思考是 aos 函數（問腦＝寄信給 llm kernel、非同步、aos-llm／aos-tools 當基礎工具；待使用者看）；基礎積木邊緣實測（修 6 處、工具失敗原因要不要給外部 agent 待使用者） |
| [2026-11-05](05/README.md) | 16 | 三扇門與結束碼統一（stdio-unify）；無痛遷移旅程（portable-flow）：sleep／wake 開放、存的路徑相對管我的 daemon、image 模型、不存副本、四步啟動；WSL 實測搬家互踩；衝突 3、方向題 5 待使用者；kernel 與 daemon（kernel-daemon）：kernel＝管 proc 是否可執行、daemon＝最基礎 kernel、繼承式／0 號兩模式、問腦改掛 daemon 的 `max: 1` loop、llm kernel 自己一台 daemon（`AOS_LLM_KERNEL`＝stack）；衝突 2 待使用者；llm 邊緣實測（edge-llm）：修 3 處、題 1 待使用者；aos-agent／判官邊緣實測（edge-agent）：修 10 處、題 2 待使用者；daemon 一帶邊緣實測（edge-daemon）：修 6 處、題 2 待使用者；午後第二輪邊緣實測（edge-round2）修 daemon 當機復原與 reason 等、題 1 待使用者；給 agent 的 aos 知識＋層級式記憶工具 `memory`（agent-knowledge）：`knowledge/aos` 根＋九節、`read`／`ls`／`find` 鎖在 `AOS_MEMORY` 下、Haiku／luna 9／9、五題待使用者；小念頭做成工具 thought（small-thought，三題已裁）；架構大重構規劃（arch-refactor）：甲代封存、proto8 按角色分夾、impls 一次建、code map 改生成，S0～S11、七題待使用者；知識庫增刪改與多庫規劃（knowledge-write，K7）：`memory_write` 三 op＋aos-lock 鎖資料夾、多庫＝捷徑資料夾，四題＋衝突 1 待使用者；不靠 pid 找東西（no-pid）：只有 daemon 碰 pid、寄信不回＝呼叫失敗、監管樹；遠期一個 agent 一個帳號；為何用 JSON、argv 的兩面（json-argv）：JSON 預設不定死、aos 函數 ↔ tool 呼叫無痛互轉、argv＝method、旗標照 argparse 映射 stdin JSON；信封與 body、暫停時間（fs-image）原文待聊 |
| [2026-11-06](06/README.md) | 12 | 信件 body 與可選的非同步呼叫協議（body-protocol，fable 規劃）：一箱一函數、body＝那函數的 stdin JSON、回信＝stdout 或 `{"error"}`、「body＝inst」只留沙箱特例、看不懂 body 有 `reply_to` 就回錯誤信、進度先讀信資料夾的窗；衝突 10 條；11-06 使用者裁四題照推薦、題 5 照 apply-ideas 排程、提點「不要與 aos-post 耦合太深」；昨晚想法怎麼用到現況（apply-ideas，fable 規劃）：六樣都不插進 S 步、只有 tick 改 deadline 跟 S9 同人緊接、信封／body 與暫停時間只差條文＋P6、aos-serve 排大重構後；D1 與 tick 五題下午已裁（tick 改成 daemon 自帶 `tick`、沒 tick 退牆鐘），新題 N1、N2 也照推薦裁了 |
| [2026-11-07](07/README.md) | 12 | 把 arknights 敘事庫歸納進 aos 知識庫體系（arknights-kb，長線，進行中）：確定性為優化目標、gpt 腦實跑、挖不足再優化 |
| [2026-11-08](08/README.md) | 6 | 家機 codex 開著沙箱連 LiteLLM（codex-sandbox）：帶 `network_access=true` 即可，使用者裁 A、派工指令已改 |
| [2026-11-09](09/README.md) | 5 | `_tick` 改名大改（clock／turn 待裁）與熱寫檔拉出 json 的盤點與實測（clock-and-hot-writes），只盤點、5 題待裁 |
| [2026-11-10](10/README.md) | 16 | 大修前先修（prefix-fixes）：問題清單 207 列分桶、直接修 61 列切五條施工線、A＋B 待裁 2 題 |
| [2026-11-11](11/README.md) | 16 | 工具 `agents_children` 改名 `subagent`、舊名不留（subagent-rename）；包名 `children` 等相關名字待使用者裁；agent 能改自己的 system 文字（self-system：`aos-agent system`＋`self_system`，fsm 取代、eca 附加） |
| [2026-11-12](12/README.md) | 34 | eca 不給 aos 基礎檔案工具（claude 用內建、codex `workspace-write`）；knowledge 工具拆除、出廠內容留作普通 json＋`_index`、`index_view`；json 工具 `json_*`／`jsonx_*`／`json_multi_*`（`#/` 照標準）；`_metainfo` 只是約定（裡外都讀、外面贏、壞了不擋）；Q01～Q16 清帳；錯誤行不帶絕對路徑；一條工具登記壞掉不拖垮全部（P-41 改）；kernel 條文改寫與小修、通用 kernel 框架圖紙（沒施工、待看）；eca slash 指令經畫面與 say／chat 都同步；外部 MCP 五步做完（fsm 那條沒做）；auto save 只實測；wf/ 往 aos 走只記原話；ops-notes 與兩隻 Codex 搬進 aos 盤點完（ops-notes-to-aos） |
| [2026-11-13](13/README.md) | 1 | 公司 WSL 改住 `~/aos-home`（一隻 opus eca）、repo 用 `~/repo/aos`；遊樂場與舊 repo 刪掉 |
| [2026-11-14](14/README.md) | 2 | proc 新心智模型發想（proc-mental-model，純發想、不定稿）；aos 頭腦風暴輪（人是外部計算單元、粗化細化、宣告 vs 私有看法；只發想、舊 D 題不裁） |
