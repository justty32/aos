# proto8 討論紀錄：2026-11

← [thinking](../README.md)

規矩見 [thinking/README](../README.md)。這個月的每天一份，一列一句：定了什麼、還有什麼未決。

| 日期 | 份數 | 一句話 |
|---|---|---|
| [2026-11-01](01/README.md) | 1 | 試驗場 bob；環境變數只在必要時用（五題已裁、格旋鈕改 argv／檔） |
| [2026-11-02](02/README.md) | 8 | cathy、工具小格 `.stack/tools/`、daemon 掛 bob、`AOS_DAEMON_STACK`、exec 像繼承、窗有變動才寫、常駐 bob（11-04 封存）、窗名就叫 `ctl.json`／`state.json` |
| [2026-11-03](03/README.md) | 7 | procs 合一（含 sleep／wake）、ctl 改下指令、stack 不放工作區、trace 拿掉、eca 接 aos 工具、aos-post 重新定位；aos-agent 介面細節未規劃、topdown 量測待使用者 |
| [2026-11-05](05/README.md) | 10 | 三扇門與結束碼統一（stdio-unify）；無痛遷移旅程（portable-flow）：sleep／wake 開放、存的路徑相對管我的 daemon、image 模型、不存副本、四步啟動；WSL 實測搬家互踩；衝突 3、方向題 5 待使用者；kernel 與 daemon（kernel-daemon）：kernel＝管 proc 是否可執行、daemon＝最基礎 kernel、繼承式／0 號兩模式、問腦改掛 daemon 的 `max: 1` loop、llm kernel 自己一台 daemon（`AOS_LLM_KERNEL`＝stack）；衝突 2 待使用者；llm 邊緣實測（edge-llm）：修 3 處、題 1 待使用者；aos-agent／判官邊緣實測（edge-agent）：修 10 處、題 2 待使用者；daemon 一帶邊緣實測（edge-daemon）：修 6 處、題 2 待使用者；午後第二輪邊緣實測（edge-round2）修 daemon 當機復原與 reason 等、題 1 待使用者；給 agent 的 aos 知識＋層級式記憶工具 `memory`（agent-knowledge）：`knowledge/aos` 根＋九節、`read`／`ls`／`find` 鎖在 `AOS_MEMORY` 下、Haiku／luna 9／9、五題待使用者；小念頭做成工具 thought（small-thought，三題待使用者）|
| [2026-11-04](04/README.md) | 6 | eca 開場白檔可指定、loop／fsm agent、aos-post 信箱要不要改成一個資料夾（裁不換）、測試全刪、思考是 aos 函數（問腦＝寄信給 llm kernel、非同步、aos-llm／aos-tools 當基礎工具；待使用者看）；基礎積木邊緣實測（修 6 處、工具失敗原因要不要給外部 agent 待使用者） |
