# metrics 效率量測包

← [modules](../README.md)｜R1 基線與優化項排序：[metrics-baseline](../../notes/play/2026-10-09-real-ai/metrics-baseline.md)

| 項目 | 內容 |
|---|---|
| 接法 | C 工具（job） |
| 預設 | 開（工具） |
| 依賴 | Python 3.11+ 標準庫 |
| 程式 | `aos7-metrics`；`aos7_metrics.py`：scan(path, overhead=0)、line(scope_dict, overhead)、main(argv=None) |
| 測試 | `python3 proto7-2/tests/run_all.py modules/metrics/tests -v` |

## 契約卡
- **職責**：遞迴純讀 JSON 證據，按 logical 分單，量四個效率指標。
- **前置條件**：PATH 是資料夾；時間來自證據 at，以 fromisoformat 解析、本地時區比較。
- **保證**：唯讀、不建檔、不取鎖、不用牆鐘或 mtime；壞 JSON／讀不到列入相對路徑 unreadable 並跳過整檔；JSONL 壞行（含半行）只跳過該行並列入 unreadable，巢狀非物件視為空物件；可重跑。成功含 unreadable 退出 0，用法／PATH 錯誤退出 2。
- **明確不管**：不碰 llmcall／author／events 程式，不 import aos 模組；不是帳的彙總，也不推補遺失證據。

## 四個指標
只看輸出那一行就夠；下面的 receipt、gateway、intent、settle 等是別包的證據檔名（llmcall／budget／step），給要核對算法的人。
- **token**：receipt.used（缺 receipt 用 gateway done.used）、request.reserve、未結呼叫數與其預留；usage 拆 prompt／completion／reasoning／cached。`--overhead N` 另算代理前置總量及自己的 prompt；缺欄為 0。
- **並行呼叫數**：區間 [start,end)，start 依 intent.at、raw.at−elapsed、reserve.at；end 依 done.at、raw.at，僅 intent 則無限；同刻先結束再開始，無 start 計 window_unknown。
- **收單→結案秒數**：最早收單 event／呼叫開始／預留至最晚 done／settle／closed frame／results；author 須 receipt.closed=true，未結為 null，四捨五入 3 位。
- **重試次數**：reask=max(呼叫數−1,0)＋resends 值總和＋extra_tries=Σmax(tries−1,0)＋adopted 次數。

## 五個概念
1. 單＝一件 AI 工作（例如 author 的一張需求 `author/<rid>`）；沒標的呼叫自成一單 `call:<call_id>`。
2. 呼叫＝問模型一次（llmcall 的一個 call 資料夾）；同一呼叫只算一次。
3. 區間＝呼叫開始至完成；未完成持續在飛，無起點無法判並行。
4. 四指標＝token、並行、耗時、重試；每單與 scope 都有彙總。
5. scope＝每個 PATH；多 PATH 合計相加單數，並行重新算所有呼叫的峰值。

## 第一次跑
從 repo 根直接照抄；`--json` 改印一行排序 JSON，`--overhead` 是非負整數，預設 0。
```sh
python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol --overhead 1644
python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/* --overhead 1644
```
以下為兩條指令的實跑輸出。`baseline/r1/` 是 R1（2026-10-09 真 AI 12 圈）暫存 node 的凍結副本，只留本工具讀的檔；litellm-smoke 由 evidence 的 status.json 重建。
```text
loop-gpt-6-sol：1 單、1 次呼叫｜每單 token 2590（prompt 2365＝代理 1644＋自己 721、completion 225、推理 91、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 11.486 秒｜重試 0
litellm-smoke：1 單、1 次呼叫｜每單 token 1649（prompt 1644＝代理 1644＋自己 0、completion 5、推理 0、cached 1408；預留 1000000、未結 0）｜並行最多 1｜收單→結案 1.67 秒｜重試 0
loop-gpt-6-astra：1 單、1 次呼叫｜每單 token 2504（prompt 2365＝代理 1644＋自己 721、completion 139、推理 0、cached 1408；預留 1000000、未結 0）｜並行最多 1｜收單→結案 8.739 秒｜重試 0
loop-gpt-6-astra-max：1 單、1 次呼叫｜每單 token 2688（prompt 2365＝代理 1644＋自己 721、completion 323、推理 184、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 15.291 秒｜重試 0
loop-gpt-6-astra-r2：1 單、1 次呼叫｜每單 token 2505（prompt 2365＝代理 1644＋自己 721、completion 140、推理 0、cached 1408；預留 1000000、未結 0）｜並行最多 1｜收單→結案 9.167 秒｜重試 0
loop-gpt-6-astra-r3：1 單、1 次呼叫｜每單 token 2502（prompt 2365＝代理 1644＋自己 721、completion 137、推理 0、cached 1408；預留 1000000、未結 0）｜並行最多 1｜收單→結案 9.637 秒｜重試 0
loop-gpt-6-luna：1 單、1 次呼叫｜每單 token 2551（prompt 2365＝代理 1644＋自己 721、completion 186、推理 35、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 6.918 秒｜重試 0
loop-gpt-6-luna-nothink：1 單、1 次呼叫｜每單 token 2499（prompt 2365＝代理 1644＋自己 721、completion 134、推理 0、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 6.806 秒｜重試 0
loop-gpt-6-luna-r2：1 單、1 次呼叫｜每單 token 2558（prompt 2365＝代理 1644＋自己 721、completion 193、推理 45、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 7.328 秒｜重試 0
loop-gpt-6-luna-r3：1 單、1 次呼叫｜每單 token 2566（prompt 2365＝代理 1644＋自己 721、completion 201、推理 54、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 8.232 秒｜重試 0
loop-gpt-6-sol：1 單、1 次呼叫｜每單 token 2590（prompt 2365＝代理 1644＋自己 721、completion 225、推理 91、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 11.486 秒｜重試 0
loop-gpt-6-sol-high：1 單、1 次呼叫｜每單 token 2566（prompt 2365＝代理 1644＋自己 721、completion 201、推理 62、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 10.799 秒｜重試 0
loop-gpt-6-sol-r2：1 單、1 次呼叫｜每單 token 2627（prompt 2365＝代理 1644＋自己 721、completion 262、推理 125、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 10.157 秒｜重試 0
loop-gpt-6-sol-r3：1 單、1 次呼叫｜每單 token 2583（prompt 2365＝代理 1644＋自己 721、completion 218、推理 79、cached 0；預留 1000000、未結 0）｜並行最多 1｜收單→結案 9.043 秒｜重試 0
合計：13 單、13 次呼叫｜每單 token 2491（prompt 30024＝代理 21372＋自己 8652、completion 2364、推理 675、cached 5632；預留 13000000、未結 0）｜並行最多 6｜收單→結案 平均 8.867 秒、最長 15.291 秒｜重試 0
```
