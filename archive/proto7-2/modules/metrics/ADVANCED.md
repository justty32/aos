# metrics 進階

← [README（第一次用看這裡）](README.md)

## 選項
- `--detail`：改印細節行，把 token 拆成 prompt（送出）、completion（回答）、推理、cached（命中快取），另列預留（呼叫前先替這次保留的 token 上限，例如 1000000，不是真的用掉）與未結（還沒算完帳的呼叫數，正常是 0）。
- `--overhead N`：只在 `--detail`／`--json` 有用。N＝每次呼叫被代理（例如 LiteLLM）自動塞進 prompt 的 token 數，給了就把 prompt 拆成「代理＋自己」。不知道就別給（預設 0），大多數人用不到。本 repo 代理量到的是 1644：`job proto7-2/modules/metrics/baseline/r1/litellm-smoke --detail` 看到的 prompt 數就是（那次只送空 prompt，所以 prompt 全是代理加的）；換了代理就照樣送一次空 prompt 再量。
  ```sh
  python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol --detail --overhead 1644
  # loop-gpt-6-sol：1 件、1 次呼叫｜每件 token 2590（prompt 2365＝代理 1644＋自己 721、completion 225、推理 91、cached 0；預留 1000000、未結 0）｜並行最多 1｜收到→做完 11.486 秒｜重試 0｜帳差 0（帳 2590－回條 2590）、缺口 0
  ```
- `--by model|holder|day|hour`（`--help` 寫作 `--by FIELD`）：按模型／呼叫者（request 的 holder）／日／時分組，每組列呼叫數、用掉的 token、超支（取代已封存的 `aos7-usage`）。文字模式自動帶 `--detail`，細節行下面每組一行；`--json` 每個 scope 與 total 多 `by:{field, groups:[{key, calls, used, overrun}]}`。model 取 request 的 `request.litellm.model`（舊檔形 `request.model`，再不然 endpoint）；日／時照證據 at 本身寫的時間（不轉時區），沒有時間記 `-`。
  ```sh
  python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol --by model
  # loop-gpt-6-sol：1 件、1 次呼叫｜…｜重試 0｜帳差 0（帳 2590－回條 2590）、缺口 0
  # 　　model chatgpt-gpt-6-sol：1 次呼叫、用 2590 token、超支 0
  ```
- 帳差（`--detail` 行尾、`--json` 的 `ledger:{used, receipts, diff, gaps, bad, unbooked, unbooked_used}`）：帳＝各 `budget/<b>/ledger.json` 的 used 加總；回條＝有帳的那些 budget 底下各呼叫 `receipt.json` 的 used 加總（只算真回條；沒帳的呼叫，例如直連代理的 smoke，不算進來）；帳差＝帳－回條，正常是 0；沒帳的呼叫數與它們的回條 token 記 unbooked、unbooked_used，行內寫「另 N 次呼叫沒帳、用 X token」。沒有帳檔（或帳檔沒有 used 欄）印「無帳」；帳檔在卻讀不了或 used 不是整數印「不明（N 個帳檔讀不了）」，bad＝N。缺口＝有請求沒 `receipt.json` 的呼叫數（只有 gateway done 也算，表示回條沒寫成）＋超支的呼叫數。只對照、不修帳。
- `--json`：給程式讀，印一行排序 JSON：`{v, overhead, scopes:[每個 PATH], total:合計}`；每個 scope 有 scope、flows（每件明細；每件的 `parts` 按併件前的原 logical 分項 `{calls, used}`，例如 `author/<rid>` 件裡的 `author-review/<rid>`）、calls、tokens、max_parallel、window_unknown、seconds{mean,max,open}、retries、unreadable、ledger（帳差，見上）；給 `--by` 才多 by。各欄算法見下面「給維護者」。

## 出錯與退出碼

出錯時 stderr 印一行 `aos7-metrics: <發生什麼>。<怎麼辦>`（例：`aos7-metrics: 不是資料夾：x.json。PATH 要給資料夾，例：aos7-metrics job …`）；本包沒有錯誤 JSON。退出碼意義全 aos 共用，見 [blueprint-errors §2](../../notes/blueprint-errors.md#2-統一退出碼表全-aos-共用只有五個)。本包只用兩個：

- **0** 量好了。有檔讀不了也算 0，行尾報「N 個檔讀不了已跳過」——量尺不該因一個壞檔整支失敗（[blueprint-errors §4](../../notes/blueprint-errors.md#4-不確定怎麼表達) 的唯一豁免）。
- **2** 你給的不對：參數錯、`--overhead` 負數、PATH 不是資料夾；什麼都沒讀。

## 給維護者
程式：`aos7-metrics`（入口）；`aos7_metrics.py`：scan(path, overhead=0)、plain(scope_dict)、line(scope_dict, overhead)、by(field, rows)、ledger(used, receipts, gaps)、main(argv=None)。R1 基線與優化項排序：[metrics-baseline](../../notes/play/2026-10-09-real-ai/metrics-baseline.md)。`baseline/r1/` 只留本工具讀的檔；litellm-smoke 由 evidence 的 status.json 重建。

### 契約卡
- **職責**：遞迴純讀 JSON 證據，按 logical 分單，量四個效率指標。
- **前置條件**：PATH 是資料夾；時間來自證據 at，以 fromisoformat 解析、本地時區比較。
- **保證**：唯讀、不建檔、不取鎖、不用牆鐘或 mtime；壞 JSON／讀不到列入相對路徑 unreadable 並跳過整檔；JSONL 壞行（含半行）只跳過該行並列入 unreadable，巢狀非物件視為空物件；可重跑。成功含 unreadable 退出 0，用法／PATH 錯誤退出 2。
- **明確不管**：不碰 llmcall／author／events 程式，不 import aos 模組；帳差只對照、不修帳，也不推補遺失證據。

### 四個指標算法
下面的 receipt、gateway、intent、settle 等是別包的證據檔名（llmcall／budget／step），給要核對算法的人。
- **token**：receipt.used（缺 receipt 用 gateway done.used）、request.reserve、未結呼叫數與其預留；usage 拆 prompt／completion／reasoning／cached。`--overhead N` 另算代理前置總量及自己的 prompt；缺欄為 0。
- **並行呼叫數**：區間 [start,end)，start 依 intent.at、raw.at−elapsed、reserve.at；end 依 done.at、raw.at，僅 intent 則無限；同刻先結束再開始，無 start 計 window_unknown。
- **收單→結案秒數**：最早收單 event／呼叫開始／預留至最晚 done／settle／closed frame／results；author 須 receipt.closed=true，未結為 null，四捨五入 3 位。
- **重試次數**：reask=Σmax(同一 slot 的呼叫數−1,0)＋resends 值總和＋extra_tries=Σmax(tries−1,0)＋adopted 次數。slot 是原 request.logical（沒標的照舊用 `call:<call_id>`），brain 則是 call id 本身，所以同信多回合不算重試；author 主單／審查／學習各自算 n−1，再加總到同件。

### 名詞對照（只跟 `--json`／`--detail`、程式有關）
單＝件（`flow`，按 request 的 logical 分，brain 每封信一件，`author-review/<rid>`／`author-learn/<rid>` 併進 `author/<rid>`，沒標的呼叫自成 `call:<call_id>`）；重問（reask）按 slot 算，brain 同信多回合不算重試。brain 信件鍵依 aos7_up_brain.call_id/cid_of：截斷形 call id 取前 47 字，其他在去尾後的第 1 回合 call id 也在時才去掉尾端 `-s數字`（信 id 本身以 `-s數字` 結尾不會拆件），再取前 47 字；前 47 字相同的兩封信會被併成一件（已知限制）。呼叫＝llmcall 的一個 call 資料夾；區間＝呼叫開始至完成，用來算並行；scope＝每個 PATH，多 PATH 合計相加件數，並行重新算所有呼叫的峰值。
