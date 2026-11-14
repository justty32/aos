# 06 Claude 電表：需核結果與原型試跑（11-14 下午，head-comm 派）

← [llmk2-1114](../llmk2-1114.md)｜對應 [03 §6](03-計劃.md#6-成本與觀測) 的「需核」與 v1-c 的 Claude 那半｜原型在 repo 外 `~/code/llmk2-1114/meter/`（`rows_check.py`、`order_check.py`、`claude_meter.py`、輸出 `week-1107-1600.txt`），只讀 `~/.claude*/projects` 的 usage、model、cwd、timestamp、id 這幾欄，沒讀對話內容，也沒碰活樹。

## 結論

- **需核成立**：同一則回覆確實會寫成好幾列，而且**最後一列就是最終數字**。03 §6 的去重規則（以 `message.id` 為鍵、取 `output_tokens` 最大的那列）是對的；要是直接加總每列，大約會重算一倍。
- **原型能用**：掃完兩個帳號一週的紀錄（約 2,100 個檔、17 萬列）只要幾秒，就能出「本週各線 Claude token」表。
- **最意外的事**：這一週主帳號的 Claude 輸出 token 有 **約 62% 不在 aos**（`repo:simple_tools` 約 50%、`repo:arcagi` 約 12%）；aos 內最大的是 repo-aos 本人（約 14%），各 ok-* 線各自 1～4%。`.claude-alt` 帳號幾乎全在 arcagi 與 simple_tools。所以「Claude 週額度誰燒的」，答案大半在 aos 外面；部門配額只管 aos 的話，管不到大頭。

## 需核：一則回覆分幾列（主帳號全部紀錄，1,938 檔）

| 量 | 值 |
|---|---|
| 有 usage 的列 | 160,259 |
| 不同的 `message.id` | 85,529（每個都有 id，沒有壞行） |
| 一則一列 / 兩列 / 三列以上 | 24,219 / 52,315 / 8,995（最多 44 列） |
| 多列裡 usage 完全相同 | 51,732 |
| 多列裡 `output_tokens` 不同 | 9,578，**全部是最後一列最大** |
| 多列裡 input／cache 不同 | 0 |
| 同一 id 出現在兩個檔 | 82（都是同一個 session，像是續接時複製的），所以**去重要跨檔做**，不能只在單檔內 |

`.claude-alt`：144 檔、9,732 列、5,019 個 id，多列的 usage 全部相同，沒有跨檔重複。

對計劃的修正（施工時照做）：去重是「全域以 `message.id` 為鍵，取 `output_tokens` 最大的那列」；增量版要存「已見 id → 已計 usage」，新列比舊的大才補差額。跳過半截列的做法不變。

## 原型試跑：2026-11-07 16:00 ～ 11-14 13:28（Asia/Taipei），只量不管

單位是輸出 token（`out`）。`cache_read` 是量最大的一項，但它佔不佔週額度、占多少不知道，所以表裡照實列、不換算。歸戶規則：`~/repo/aos/wf/temp/<名>` 歸 `<名>`；`~/repo/aos` 歸 repo-aos；其他 `~/repo/<名>` 歸 `repo:<名>`；`~/code/<名>` 歸 `code:<名>`；其餘照路徑。子 agent（fable 等）算在派它的那個工作區。

主帳號（`claude`）：回覆 30,938 則，out 23,128,133。

| 歸戶 | 回覆 | out | 佔比 | out 最多的模型 |
|---|---|---|---|---|
| repo:simple_tools | 15,908 | 11,494,605 | 49.7% | opus-5-5 |
| repo-aos | 3,863 | 3,343,383 | 14.5% | opus-5-5 |
| repo:arcagi | 3,232 | 2,732,093 | 11.8% | opus-5-5 |
| ok-view | 813 | 831,015 | 3.6% | opus-5-5 |
| ok-release | 618 | 485,716 | 2.1% | opus-5-5 |
| ok-kf | 757 | 475,671 | 2.1% | opus-5-5 |
| ok-pilot | 720 | 431,871 | 1.9% | opus-5-5 |
| ok-astra | 649 | 430,364 | 1.9% | opus-5-5 |
| code:playground | 661 | 401,597 | 1.7% | opus-5-5 |
| ok-board | 350 | 362,304 | 1.6% | opus-5-5 |
| 其他 26 格（ok-limits、ok-kb、ok-misc、xiaosi、各部長…） | — | 合計約 2.1M | 約 9% | — |

`.claude-alt`：回覆 3,127 則，out 2,611,201；repo:arcagi 1,430,781（55%）、repo:simple_tools 1,064,085（41%）、tmp 116,335。

全表在 `~/code/llmk2-1114/meter/week-1107-1600.txt`。

## 原型看出的限制（施工時要處理）

1. **不是官方週百分比**：只是本機紀錄的 token 數。cache 讀寫怎麼算進額度不知道，要靠 03 §6 的 `calibrations.jsonl` 校正。
2. **窗要對齊重置時間**：這次手動用「上週六 16:00 起」（xiaosi 說今天 16:00 重置）。正式版的週窗起點要可以設定，不能寫死整點午夜。
3. **只看得到這台機器**：公司 WSL 那台的紀錄在另一台上，要各台各跑再合併，報表標 `coverage`。
4. **歸戶靠 cwd**：在 `~/repo/aos` 根目錄開的 session（含使用者自己開的）都歸 repo-aos，分不出是頂層 agent 還是使用者本人。
5. **aos 外的用量**：03 計劃的部門樹只有 aos 內的部門，但同一個 Claude 帳號的週額度大半燒在 aos 外。要不要把 aos 外的 repo 也列進電力卡（只顯示、不分配），是新的方向題，等施工前再問（照新規矩寄使用者專區）。
