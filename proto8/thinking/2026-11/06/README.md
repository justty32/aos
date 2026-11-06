# proto8 討論紀錄：2026-11-06

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-11-06 早 信件 body 與「可選的非同步呼叫協議」（body-protocol，fable 規劃）](body-protocol/README.md) | 使用者「body這塊，我一時之間也想不出來……你先再派個fable去幫我想想吧」（11-05 夜暫定：body 自由、遵從協議時 body＝inst、支援看 PATH「這好像不太好」、能寫檔就有權限、進度各自做）：**推薦**——信封照舊只管送達；一箱一函數、body＝那函數的 stdin JSON、回信＝stdout 或 `{"error": {"code", "msg"}}`（daemon ctl／llm kernel／判官現況就是這樣）；「body＝inst」只留成沙箱 worker 的特例信箱；看不懂 body 有 `reply_to` 就回錯誤信、信封壞照舊不回；進度先讀 `cur/<信名>/` 的窗；JSON-RPC 逐項對照全有、缺的兩樣（能力探詢、進度）用 `_tooldef.json` 與窗補；衝突 10 條（11-04「信裡不帶 inst」、N-16 決定 27、C-52 例外表、`ping` 保留字…）；**五題待使用者**；**沒改程式** |
