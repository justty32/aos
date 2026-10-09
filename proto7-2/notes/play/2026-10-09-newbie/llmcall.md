# 新手試用：llmcall（真傳輸 examples/litellm）

← [總表](README.md)｜受測：`proto7-2/packs/llmcall/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/llmcall-haiku.md](raw/llmcall-haiku.md)、[raw/llmcall-luna.md](raw/llmcall-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 17 | ≤10 | 否 |
| 對外指令 | 5（call／status／adopt＋aos7-budget init／ledger（另有 budget status、run.sh）） | ≤3 | 否 |
| 新概念（兩位取多） | 15 | ≤5 | 否 |
| 分數（兩位取差） | 5.2 | ≥7 | 否 |
| **總判** | **不過**（分鐘、指令、概念、分數） | | |

跑通情況：兩位都跑通：fake 回條 answered、真 LiteLLM 回 OK（約 1650 tokens）並結算。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 6 | 9 |
| 容易理解 | 4 | 7 |
| 複雜的藏起來 | 5 | 9 |
| 外層簡單但全面 | 6 | 8 |
| 要背的少 | 5 | 7 |
| 平均 | 5.2 | 8.0 |

## 卡點（新手視角，依嚴重度）

1. `run.sh ./evidence` 寫相對路徑、又要求從 repo 根跑，證據會落進 repo（Haiku 改絕對路徑）
2. examples/litellm/ 沒 README，不知道 req 用哪個 model、run.sh 做了什麼、證據每個檔是什麼（Haiku）
3. bound: soft、overrun、intent 無回覆＝unknown、adopt 規則都只寫在 spec（Haiku）
4. status 輸出一大段巢狀 JSON，找不到「成功」在哪一行（Haiku）
5. 退出碼 3（未完整交付）和 4（已交付帳未清）失敗時該怎麼辦，README 沒說（Haiku）

## ELI5

這是幫你問大模型一句話、同時記帳的小工具。先開一本預算帳寫上最多能用多少 token；用 call 送出問題，它先預留額度、把回答存檔、照實際用量扣帳，最後給你一張收據。同一個編號再問不會重送，只把舊收據給你。

## ELI5 之後還複雜嗎

是（兩位都說是）。成功路徑照抄就通，但 Haiku 數到 15 個新詞（reserve、settle、receipt、intent、adopt、patience…），失敗時不懂就不會處理。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] run.sh 範例改成輸出到暫存目錄（或明寫 ./evidence 會落在 repo 根）
- [ ] examples/litellm/ 加三行說明：用哪個 model、做了什麼、成功看哪個檔哪個欄位
- [ ] status 給一行摘要（answered／used／billing）在大段 JSON 之前
- [ ] 退出碼 3、4 各寫一句「這時你該做什麼」
- [ ] 新手詞表壓到 ≤5，其他詞移到進階
