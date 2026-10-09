# prompt 包（把檔案拼成給 AI 的對話）

← [proto7-2](../../README.md)｜下游：[llmcall](../llmcall/README.md)

**一句話**：你寫一張清單 `prompt.json`，說「這次要給 AI 看哪些檔」；`aos7-prompt render` 照清單現讀現拼，產出一份請求檔，交給 llmcall 送出。太長的檔會自動收起來（只留編號和開頭 200 字），省 token；要看原文用 `aos7-prompt expand`。

## 第一次跑（約 1 分鐘）

在 repo 根目錄照抄三行：

```sh
D=$(mktemp -d) && cp -r proto7-2/packs/prompt/examples/node/. "$D"
python3 proto7-2/packs/prompt/bin/aos7-prompt render "$D" "$D/prompts/first.json" --out "$D/req.json"
python3 proto7-2/packs/prompt/bin/aos7-prompt expand "$D" "$D/req.json"
```

做了什麼：第 1 行把範例資料夾複製到暫存目錄 `$D`。範例清單 `first.json` 要 AI 摘要一份約 7800 字的週報 `docs/weekly.md`。

**你應該看到**：

- 第 2 行印一行回條，只要看兩件事：`"outcome": "rendered"`＝成功；`"tokens_est": 106` 對 `"tokens_est_full": 2606`＝送給 AI 的量（token，AI 算長度的單位，約 3 個字一個）從 2606 降到 106——週報被收起來，省了九成多。其他欄位不用管。
- 打開 `$D/req.json`：週報那段變成 `ref://<一長串編號> 已折疊 7785 字，預覽：` 加開頭 200 字。原文存在 `$D/refs/`。
- 第 3 行把收起來的段換回原文，印出完整的請求（很長，捲一下就看到週報全文）。最外層的 `litellm`／`model` 是送 AI 用的信封格式，交給 llmcall 處理，你不用懂；要換模型就在清單頂層加 `"model": "名字"`。

（短檔不會收：一段超過 6000 字才收。所以清單裡都是短檔時，兩個數字會差不多，這是正常的。）

## 要學的只有三個概念

| 概念 | 白話 |
|---|---|
| node | 給一個 AI 用的資料夾（上面的 `$D`）。清單裡、命令列上的相對路徑都從它算起。 |
| `prompt.json` | 清單：一串訊息，每則寫 `role`（`system`／`user`／`assistant`）和 `content`（一段字，或多段的陣列）。 |
| 讀檔 | `content` 裡寫 `{"$opt": "file", "$val": "docs/weekly.md"}`＝「拼的時候把這個檔讀進來」。 |

「收起來（`ref://`）」不是新東西要學：它自動發生，要原文就跑 `expand`。

## 自己寫第一份清單

照 `examples/node/prompts/first.json` 改檔名就好。檔名從 node 算起：例如在 `$D` 放 `你的檔.md`，清單存成 `$D/prompts/mine.json`，就跑 `render "$D" "$D/prompts/mine.json"`。

```json
{
 "messages": [
  {"role": "system", "content": "你是幫忙讀文件的助理，回答要短。"},
  {"role": "user", "content": ["請摘要這份檔：", {"$opt": "file", "$val": "你的檔.md"}]}
 ]
}
```

## 指令（兩個）

- `aos7-prompt render <node> <prompt.json> [--out 檔]`：拼出請求。有 `--out` 就寫檔、回條印在螢幕；沒有就把請求印在螢幕。
- `aos7-prompt expand <node> <請求檔 或 ref://編號>`：印原文。

失敗時印一行 `"outcome"` 不是 `rendered` 的回條，`why` 說哪裡錯；不會拼出半份、`--out` 的檔不動。`aos7-prompt render --help` 看全部選項。

---

**第一次用到這裡就夠了。** 以下是進階，需要時再看。

## 進階

**更多讀法**（寫在 `content` 裡）：

- `{"$opt": "tail", "$val": "檔", "n": 20}`：只讀最後 20 行。
- `{"$opt": "latest", "$val": "資料夾", "n": 5}`：讀資料夾頂層檔名最大的 5 個 `.md`（檔名以時間開頭時＝最新 5 封）。
- `{"$opt": "append", "$val": {"$ref": "prompts/b.json#/messages"}}`：放在 `messages` 裡，把別份清單的訊息接進來。
- `{"$ref": "a.json#/x"}` 拿別的 JSON 某處的值；`{"$fmt": {"$val": "你好 ${who}", "who": "小明"}}` 填空；`{"$env": "HOME"}` 讀環境變數。

**收起來的門檻**：預設一段超過 6000 字收；`--max-chars N` 或清單頂層 `"max_chars": N` 改，`0`＝不收。

**回條其他欄位**：`chars`／`chars_full` 是字數；token 估值＝字數 ÷ 3，用來看每回合有沒有越拼越大，不是帳。`folded` 是收起來的編號。

**退出碼**：0 成功；2 清單寫錯；3 有檔讀不到或繞圈（`$ref` 指回自己）。

**另外三份範例**（`examples/node/prompts/`）：node 裡的 `wf/`（`AGENTS.md` 入口、`SESSION-LOG.md`、`wf/inbox/` 信）是 [wfnode](../../modules/wfnode/README.md) 裝出來的資料夾樣子，本包只讀它、不管它的規矩。

1. `entry.json`：讀 AGENTS 入口＋一句問題。
2. `session.json`：入口＋SESSION-LOG 尾 20 行，user 那句用 `$fmt` 填 `note`。
3. `inbox.json`：接上範例 2，再加最新 5 封信。

細部規則：[spec.md](spec.md)。

## 給維護者

程式 `aos7_prompt.py`（只 import `lib/aos_directives*.py` 與 `aos7_fs`，不改它們）、`bin/aos7-prompt`。不呼叫模型、不碰 llmcall／budget。測試：

```sh
python3 proto7-2/tests/run_all.py packs/prompt/tests -v
```

`test_prompt.py` 逐條對 spec；`test_prompt_rounds.py` 模擬 300 回合（SESSION-LOG 只列 open、信讀完搬走），斷言 token 估值曲線平，並有「只加不刪就會變大」的對照組。
