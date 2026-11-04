# proto8 討論紀錄：2026-10-21

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-21 aos-exec 收旗標、支援 .env](ideas/README.md) | aos-exec 收旗標，放 XXX 前面（像 env／nice／sudo），位置參數 WS 拿掉（「放前面吧。舊的寫法也要改」）、旗標 `--ws`；§ 4 `.env`：cd 到 AOS_CD、設好 AOS_* 後讀那裡的 `.env`，預設 旗標 ＞ 原本的環境變數 ＞ `.env` ＞ 預設（加 `--dotenv-override` 才 `.env` 蓋原本的，10-22）、只展開 `${名字}`、字串轉向＝全新的一跳；入口在讀完 `.env` 後挑；沒 `argv` 的 JSON 物件＝資料夾、一路往下、`AOS_CO`；aos-loop 旗標放前面、旗標＞設定檔＞預設；設定檔是唯一的位置參數、`$path` 字串拼接；細節頂層代定、可翻案 |
| [2026-10-21 計畫：loop／daemon／fsm／agent](plan/README.md) | 使用者出門前「aos-daemon和aos-fsm，乃至於agent也可以開始做了」；fable 照當天的調子排的計畫與代定 L／D／F／T（使用者確認「都沒問題」），loop、daemon、fsm、tick 四段已做；agent＝慣例＋demo、沒有程式；未決：tasks 要不要做、通用 kernel |
