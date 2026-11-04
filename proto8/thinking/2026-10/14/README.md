# proto8 討論紀錄：2026-10-14

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-14 JSON 統一入口](json-entry/README.md) | 使用者想把函數統一入口的參數統一成 JSON：stdin＝參數、stdout／stderr＝結果、exit＝輔助，aos 的 stdio 是 JSON 串流；state／ctl＝內部狀態外顯；IPC 用改名、建資料夾、檔案鎖，窗擴成一族（N-14～N-17）；argv 空出來、旗標鏡射設定 key（D-1～D-6）；aos-fsm 從 agent 抽成通用（表只明寫、不做繼承、可嵌套）；實作分兩級（N-18）、窗必填（N-19）、巢狀重跑不保證冪等（N-20）；N-12 跑完＝stdout 吐出結果＋行程結束；各段見入口的分檔表 |
