review_round 執行七步審視、降級與只記錄的成長建議。

用 `aos-exec proto8/lib/aos/review_round` 呼叫，stdin：

```json
{"case":"/abs/case","defs":"/abs/defs","ladder":"/abs/reviewer/ladder.json","ws":"/abs/ws","daemons":[]}
```

`ws` 省略時用 `$AOS_WS`；量測需要 `$AOS_STACK`。`ladder.json` 格式與預設值見 [reviewer](../../../templates/reviewer/README.md)。工具不直接叫 LLM；case 或比對器若使用腦，仍由 measure 執行。

stdout 是 `{"round":"<UTC timestamp>","review":"/abs/ws/reviews/<round>/review.json","action":"downgrade"}`；action 另有 `prescribe`、`none`。每輪保留原量測的 `tree` 與 `consistency`，七步的 `steps`、處方空陣列及完整定義副本。逐級試到第一次不過，副本恢復最後過門的一級；整個 case 都過且單位成本下降才換上。`promote_by: claude` 或正式定義正在用時，留下 `pending_promote`。後者的 daemon 清單由呼叫者在實際換上時再提供。

每份量測使用不同工具小格，保留各次工具呼叫紀錄；`spent` 加總每份量測回傳的所有重跑成本與整份 `check.cost`，避免只計中位數而漏掉重跑。單位成本以 `watch.metric` 指向的成本除以實際 `size_bytes`，大小為零時回 `MeasureBad`。

每輪先 feed 已開的窗，略過仍盯梢或本輪剛退回的目標。成功換上後以最近 `baseline_cases` 輪（含本輪）的 before 單位成本平均開窗。連續 retire_after_cases 輪沒出現、且同類別兄弟被叫過的 agent 定義才進 `suggest.retire`，specialize 記錄 repeated_child 與量測節點中位數超標的 context_too_big；不自動停用或刪除。歷史只讀 `reviews/*/review.json`，reviews 必須在 defs 之外，避免複製遞迴。

目前 measure 在 agent case 收尾時會移除受測 agent 的 stack，且未公開從量測根連到各次 run 帳本的邊；本工具依其回傳值計算 `spent`。日後用第二層 measure 量審視者時，翻帳還不能自動涵蓋這些內部量測成本，需另補 measure 的保帳介面。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s proto8/lib/aos/review_round/tests -v
```

第七步只記建議：同類別兄弟曾被叫過才建議退休，並附歷史 callers 與 defs refs；defs dup 結果列 differentiate。重複子定義透過相鄰不同 case 的樹比對，三軸取公開宣告。context_too_big 使用本輪 measure tree 每個節點的 `prompt_tokens_median`，嚴格大於 `max_prompt_tokens_median` 才建議；`null` 不產生建議，不自行翻原帳或從彙總 token 推算，也不合併子節點的中位數。

review.json 另保存 definition_signatures，供下輪確認 repeated_child 的工具軸未變（端點與記憶變動不會取消重複訊號）；舊 review 缺此快照時不猜測。

端到端驗收：`PYTHONPATH=proto8/lib python3 -m unittest discover -s proto8/lib/aos/review_round/tests -p test_round.py -k large_context`。真 daemon/kernel 執行四筆 prompt_tokens=14000 的 think、門檻 10000，驗證量測的節點中位數可產生 context_too_big 建議。
