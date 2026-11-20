家機暫存樹實測 llm kernel 的 sol 那包加 `"session_key": "litellm_session_id"` 前後：不加每輪快取 0，加了從第 2 輪起每輪約 99% 命中。

← [2026-11-21](README.md)｜進度 `prompt-cost-cache`｜前情：[aos-home 瀏覽筆記 第 10 則](../20/aos-home-瀏覽筆記-1120.md)｜鍵的說明：[kernel_llm docs/01](../../../py/tools/aos/kernel_llm/docs/01-用法.md)

## 做法

線 `top-1121-skey`，11-21 清晨家機。照 `templates/start-api` 抄兩棵暫存樹（`~/.aos/scratch/top-1121-skey/a-nokey`、`b-key`），兩棵都把 `agents/ann/llm.json` 換成 `{"model": "sol"}`；只有 `b-key` 的 `llm/kernel.json` 在 `sol` 那包多寫 `"session_key": "litellm_session_id"`。各起一棵、對同一隻 ann 連問 4 句「Reply with one word: ok」，數字讀 ann 的 `observed.jsonl`。LiteLLM 用使用者起著的那台（1.87.5，埠 4000，模型 `chatgpt-gpt-6.1-sol`），沒改它的設定。真模型共叫 8 次。`~/aos-home`、`proto8/` 的程式與範本都沒動。

## 數字

| 輪 | 不加：prompt_tokens | 不加：cached_tokens | 加了：prompt_tokens | 加了：cached_tokens | 加了的命中率 |
|---|---|---|---|---|---|
| 1 | 12,553 | 0 | 12,553 | 0 | 0%（第一次，本來就沒得中） |
| 2 | 12,570 | 0 | 12,570 | 12,416 | 98.8% |
| 3 | 12,587 | 0 | 12,587 | 12,416 | 98.6% |
| 4 | 12,604 | 0 | 12,604 | 12,416 | 98.5% |
| 4 輪合計沒中快取的 | 50,314 | | 13,066 | | 少 74% |

送出去的請求兩邊一樣大（`request.json` 約 52 KB，其中 `tools` 50.8 KB）。加了只是讓上游把重複的那一大段當快取算，不會讓請求變小。

## 結論

- 加 `"session_key": "litellm_session_id"` 有效：同一隻 agent 第 2 輪起幾乎整段提示都命中快取。昨晚 `~/aos-home` 看到的 `cached_tokens` 0，原因就是沒寫這個鍵。
- 不加的那組 4 輪都是 0（11-14 公司機那次不加還有 18%／31%，是碰巧中；這次一次都沒中）。

## 已排除的其他原因（不加時 0 不是因為這些）

- 工具說明順序不穩：`b-key` 4 輪的 `tools` 逐項相同，`a-nokey` 第 4 輪跟 `b-key` 第 4 輪的 `tools` 也相同。
- system 裡有會變的東西（時間戳之類）：4 輪的第一則 system 訊息逐字相同。
- 前面的對話被改寫：第 1 輪的 `messages` 是第 4 輪的開頭，逐項相同，每輪只在後面接。
- 上游的快取門檻：一萬二千多 token 遠超過門檻，加了就中，所以不是門檻。
- LiteLLM 沒把欄位轉給上游：加了就中，代表 1.87.5 有把 `litellm_session_id` 當成上游的 session id 送出去。

另外看到的：加了之後命中的量停在 12,416，沒有隨對話變長往上長（每輪新增的那十幾 token 沒進快取）。原因沒查，對這次的結論沒影響。agent 自己 stack 的 `think/request.json` 裡看不到這個鍵是正常的，鍵是 llm kernel 交給端點函數時才加的（docs/01 有寫）。

## 建議改哪一行（要不要改由使用者定，這條線沒改）

`proto8/templates/kernel/llm-kernel/kernel.json` 與 `proto8/templates/start-api/llm/kernel.json`（後者是前者的逐字抄本，`templates/tests/test_start.py` 會比對，兩份要一起改）的 `sol` 那包：

```json
"sol":         {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6.1-sol", "fixed": {"temperature": 0.2}, "session_key": "litellm_session_id", "cost": "high", "context": 272000,
```

同一個 chatgpt 後端的 `luna`、`terra` 照理也一樣，這次沒量。`~/aos-home/llm/kernel.json` 是活樹，要改也是使用者或頂層的事。
