# 2026-10-10 學徒選單真 AI 冒煙（loop14 MN2）

← [試玩紀錄](../README.md)｜藍圖 [blueprint-scaffold1](../../blueprint-scaffold1.md) §2、§7 MN2｜選單 [examples/aos-tool](../../../packs/menu/examples/aos-tool/README.md)

**結論**：luna 一層一層交件，修了三輪問句與葉子工具之後，mailcount 題 3/3 三關（含 astra-high 審查）全過，每次 2 輪三關、13～14 次選單呼叫、約 4.2 萬 token；0 次死在格式。這只是證明走得通的冒煙，**不是** A／B 對照（MN3）。

## 怎麼跑

- 題目：AP5 的 [aos-tool-mailcount](../../../packs/author/examples/aos-tool-mailcount/request.json)（需求摘要 976 字，`build.py brief` 產生）。AP4 三題（gap／runs／audit）的需求超過 brief 1500 字上限，這輪沒跑。
- 學徒 `chatgpt-gpt-6-luna`、審查 `chatgpt-gpt-6-astra-high`（`--var review=`，走 `aos7-author propose --candidate`），三關最多 5 輪；每次新 node，grant holder `author`、amount 300 萬（審查每次預留 100 萬）。腳本 [evidence/run.sh](evidence/run.sh)。

## 三輪

| 輪 | 改了什麼之後跑 | 全過 | 選單呼叫 | 總 token | 報告 |
|---|---|---|---|---|---|
| 1 | 第一版 | 0/3 | 61 | 183,742 | [round1](evidence/round1.md) |
| 2 | 葉子工具收多行 JSON、摘要保留慣例說明、grant 加大、回法三行（限制「不要抄進格子」）、fixfile 拆兩層＋回上一層 | 1/3 | 35 | 98,198 | [round2](evidence/round2.md) |
| 3 | report 層明說「不用看已交檔內容、資訊已足夠」＋骨架；出口字改具體 | 3/3 | 40 | 127,027 | [round3](evidence/round3.md) |

- 第 1 輪三個失敗原因：①審查走 author 預留 100 萬 token，40 萬的帳拒絕（`模型那邊確定沒做成`），葉子工具又誤報成第 1 關；②luna 照舊回法 `下一行 格：內容；這格限制：max_bytes=8192` 把「```；這格限制…」抄進主程式尾巴，SyntaxError 在測試 import 時才炸，摘要被 traceback 截掉，它五輪都在改測試；③第 2 關答案訊息裡的慣例說明被前面的大 JSON 吃光。
- 第 2 輪兩次在 report 層選出口：選單刻意不重附已交檔內容，問句又寫「只寫已知事實」，它以為缺資訊。MN1 的教訓再一次：這層決定要的資訊放進這層，並明說足夠。
- 第 3 輪三次都是第 1 輪三關擋在第 2 關答案（郵局慣例），fix 選主程式、改一次就過；通過候選 [pass-v3-luna-1.txt](evidence/pass-v3-luna-1.txt)。
- 每步提示平均約 1,650 字（最大約 3,900，改主程式時附那一檔）；AP4 gap 第一輪單次提示 9,558 字、AP5 mailcount 5,767 字（`propose --prompt-out` 重建，量法見 decisions「loop14 MN2」）。

**花費**：三輪真 AI 合計 136 次選單呼叫＋4 次審查、408,967 token（全 chatgpt-gpt-6-luna／astra-high，走 LiteLLM）。
