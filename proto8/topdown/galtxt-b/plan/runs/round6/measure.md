# 第 6 輪：director 換階、writer 抽 trim 的真腦前後量測

← [round6 §7](../../round6.md) 第 2、3 項｜[handoff-B](../../handoff-B.md)「未做」第 1 項｜原始數字：[measure/summary.json](measure/summary.json)（每次一列：各維、違規、token、工具呼叫），每次的 answer／score／measure／check 在 `measure/<組>/<題>/<次>/`

**做法**（10-25，opus 實作者）：真腦 `chatgpt-gpt-6-luna-low`，`train/set` 四題各 1 次，加上第一題（主角先_梅花章）多跑 2 次（同一題共 3 次，用來量確定性），每組 6 次，各自一個工作區、並行跑。全部結束碼 0，每次都一稿就過、`degraded` 都是空的。三組：

- **前**：A 段基準 [round4/round0](../round4/round0/)，那時 director 還是腦（直接沿用、沒有重跑）。
- **director 後**：用現在的樹，但設 `GALTXT_OFF_TRIM=1`（等於還沒抽 trim）。
- **trim 後**：用現在的樹（writer 有 trim 工具，system.txt 第 8 條叫它用）。

## 一表

| 組 | 次數 | 總分平均（σ） | 第一題 3 次 | deterministic_score（score／text） | 根 token／次 | 其中 director／writer | 秒／次 | 問腦／次 | lint 違規（有違規的次數） | 叫 trim | lint 參數錯 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 前（director 是腦） | 6 | 4.33（0.52） | 4、5、4 | 0.711／0.346 | 20327 | 3472／13257 | 19.3 | 4.5 | 4/6（第一題是 narration_max、exclaim） | — | 沒記錄 |
| director 後（不給 trim） | 6 | 4.83（0.41） | 5、5、5 | 1.0／0.570 | 19402 | 0／15843 | 14.6 | 4 | 1/6（narration_max） | 0/6 | 3/6 次 |
| trim 後 | 6 | **5.00（0）** | 5、5、5 | 1.0／0.546 | 20204 | 0／16612 | 15.3 | 4 | **0/6** | **6/6**（6/6 原樣交；**6/6 changes 是空的**） | 0/6 次 |

語意分（critic 0～3）三組每次都是 2，分數的差別全部來自 lint 的語域分（T1）。「lint 參數錯」指 writer 第一次叫 lint 時沒給 `brief_path`，工具回 ArgumentsBad，只好再叫一次。真腦共花 **237,638 token**（director 後 116,414＋trim 後 121,224）。

## 驗收

| 項 | 判準 | 實測 | 過否 |
|---|---|---|---|
| director 後 vs 前 | `val_delta ≥ −0.58` | +0.50 | 過 |
| | 根 token −15% 以上 | −4.6%（20327→19402） | **沒過** |
| | director 的 deterministic_score 1.0 | 純程式，同輸入一定同輸出 | 過（照構造） |
| trim 後 | `narration_max`／`exclaim` 違規 0 | 0/6 | 過 |
| | deterministic_score.score ≥ 0.9 | 1.0 | 過 |
| | token 不增 | +4.1%（19402→20204，每次多約 800） | **沒過** |

## 結論

1. **director 換階本身有效，但被 writer 多花的抵掉了。** director 從每次 3472 token 降到 0（大約是根的 −17%），分數也沒掉（+0.5）。但 writer 每次多花了 2586：6 次裡有 3 次第一次叫 lint 漏給 `brief_path`、只好再叫一次；另外這一組幾乎每次都自檢兩回。結果根 token 只少了 4.6%。也就是說，token 這條驗收沒過的原因在 writer 叫工具的穩定度，不在 director。
2. **trim 這輪看不出有什麼貢獻。** 腦 6/6 都有叫 trim、也都原樣交出它回的稿，所以照規矩**不做 `freeze_order`**（觸發條件是腦不常叫或確定性 < 0.9，兩個都沒發生）。問題是 trim 6 次都沒改到任何字，因為稿子交到 trim 之前已經被 lint 自檢修乾淨了。違規歸零、確定性 1.0 在不給 trim 的那組（director 後）就差不多做到了（違規 1/6、確定性 1.0）。trim 唯一看得到的影響是每次多一次工具來回，約 +800 token。
3. 跟前相比，確定性從 0.71 升到 1.0，主要是 lint 自檢跟（可能）固定的 beat 表一起造成的。樣本只有 n＝3，前後三組沒辦法把這兩個因素拆開。
4. 建議（沒有做）：如果要把 trim 留著當保險，就做 `freeze_order`：act 交稿前一律過 trim，並且不再把 trim 給腦看。這樣違規歸零的保證還在，每次又能省回那約 800 token。另外，lint 的參數錯（漏給 `brief_path`）比 trim 更值得處理：可以讓 act 在缺參數時自動補上 `cur/<n>.json#/brief`，或把 lint 也做成 freeze_order。量這兩件事各需要 6 次、約 12 萬 token，這次的份額（26 萬）不夠。
