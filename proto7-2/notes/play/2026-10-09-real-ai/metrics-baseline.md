# 效率基線：用 aos7-metrics 復算 R1（E1 隊）

← [R1 消耗報告](README.md)｜工具：[metrics 包](../../../modules/metrics/README.md)｜逐次數據：[evidence/calls.csv](evidence/calls.csv)

2026-10-09 E1 隊寫。本輪**只量、只排序，不實作優化**（下一輪目標候選 ①）。

## 怎麼重跑

R1 的 12 個暫存 root（`/tmp/aos7-author-llm.*`）已凍結一份到 `proto7-2/modules/metrics/baseline/r1/`（只留工具讀的檔，174 KB；冒煙那次由 evidence 的 status.json 重建）。從 repo 根：

```sh
python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/* --overhead 1644
```

同一份資料跑兩次輸出 bytes 相同（測試 `test_repeatable` 鎖住）。時間全取證據檔的 `at`，不看牆鐘。`--overhead 1644`＝冒煙那次「只回 OK」的整份 prompt，當作代理每次自帶的前置量（其中「只回 OK」本身約 20 token，所以是上界）。

## 基線四指標（12 圈，每圈 1 單 1 次呼叫）

| 指標 | 基線 | 範圍 | 說明 |
|---|---|---|---|
| 每單 token（實用 U） | 平均 2562 | 2499～2688 | 合計 30 739；預留 R 每單 1 000 000（U 的約 380 倍）；未結 0 |
| ├ 代理前置 | 1644（64%） | 固定 | LiteLLM／上游注入；astra 有 1408 cached，sol／luna 0 |
| ├ 自己的 prompt | 721（28%） | 固定 | 需求＋工具卡＋schema＋規則 |
| └ completion | 平均 197（8%） | 134～323 | 其中推理 0～184 |
| 並行呼叫數 | 每單 1；12 圈合計最大 **6** | — | R1 分兩批同時跑（14:35:19 五圈、14:35:47 六圈，不同 root），代理撐住 6 併發、無錯 |
| 收單→結案秒數 | 平均 **9.467** | 6.806～15.291 | 起點＝預留時戳；終點＝step 框架最後寫入 |
| ├ LLM（預留→結算） | 平均 5.336（56%） | 2.433～10.917 | HTTP 本身平均 5.314 |
| └ LLM 之後（結算→step 結束） | 平均 4.131（44%） | 3.337～4.449 | 幾乎全是等：publish、起 daemon、step 一步一回合；兩個工具真的執行各約 0.04 秒 |
| 重試次數 | **0** | — | 重問 0、step 重送 0、多派 attempt 0、adopt 0 |

依模型（三次平均，秒為收單→結案）：luna-nothink 2499 token／6.8 秒最省最快；luna 2558／7.5；astra 2504／9.2（有 cache）；sol 2600／10.2；sol-high 2566／10.8；astra-max 2688／15.3 最貴最慢。題目太簡單，六種都一次答對。

## 和 R1 報告的差異（都有解釋）

| 項目 | R1 報告 | metrics | 原因 |
|---|---|---|---|
| token 各欄 | calls.csv | 12／12 完全相同 | 同一份回條 |
| 合計 | 30 739＋冒煙 1649 | 32 388 | 相同 |
| 整圈時間（sol） | 「牆鐘約 12 秒」 | 11.486 秒 | R1 用 run.sh 牆鐘，含 register 前與 answer／close 後；這兩段 author 沒寫時戳，metrics 量不到（只到 step 結束） |
| 並行 | 未提 | 合計 6 | R1 多圈同時跑在不同 root；每單內仍是 1 |
| propose 秒數 | 2.5～11.0 | LLM 2.433～10.917 | R1 含 author 程序啟動；metrics 用預留→結算 |

## 優化項排序（只排不做）

排序依「可省的量 × 有多確定 ÷ 要改多少」。

| # | 項目 | 依據（基線） | 預期效果 | 改哪裡 |
|---|---|---|---|---|
| 1 | **代理前置 1644 token 拆掉或讓它被 cache** | 每次固定 64% token；只有 astra 吃到 cache | token 最多 −64%，零程式改動 | LiteLLM 設定（先查它注入了什麼；使用者的機器設定，要他點頭） |
| 2 | **LLM 之後的等待 4.1 秒** | 44% 時間是回合等待，工具真跑只 0.08 秒 | 每單 −2～3 秒 | 常駐 daemon、author 單的 interval_ms 縮短，或 step 結果出來就 wake 下一回合 |
| 3 | **依題難度選模型** | luna-nothink 6.8 秒 vs astra-max 15.3 秒，答案都對 | 簡單題 LLM 時間 −50～75%、token −3～7% | author `--llm` 預設模型；難題才升級 |
| 4 | **ref 折疊提示詞（自己的 721）** | 28% token，工具卡＋規則每次重送 | token −10～20%（做完 1 後比例變大） | P1 的 prompt.json `$ref` |
| 5 | **同版本不重問** | R1 重問 0，現在省 0；call_id 已按請求雜湊固定 | 學徒多題後才有效 | 先用 metrics 量 A5 的 reask 再定 |
| 6 | 候選並行 | 代理已證實撐 6 併發 | 只在被拒重問時縮時間，token 線性加 | 排後 |
| 7 | gotchas 降重問 | 0 重問，無資料 | 未知 | 等 A5 |
| 8 | reserve 1 000 000 → 8000 | R 是 U 的 380 倍 | 不省 token；帳 1 億時可同時預留從 100 筆變 12 500 筆 | author `--reserve` 預設（R1 報告已建議） |

## 量不到的（邊緣）

- author 的 register／answer／close 沒有時戳，「收單」只能從預留或 events 的 `author.request` 算起，「結案」只到 step 框架最後一次寫入。要精確，author 回條得帶 `at`（不在本隊領地）。
- 呼叫完成後 gateway 的 intent 記錄被 done 蓋掉，區間起點用 `raw.at − elapsed` 推回；adopt 的回覆沒有 elapsed，退回預留時戳。
- 只有一題、全過，重試指標全 0；A5、C2、S1 的真 AI 輪要用同一個指令量，才看得出重試與並行的差。
