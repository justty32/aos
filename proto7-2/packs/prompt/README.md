# prompt 包（把檔案拼成給 AI 的對話）

← [proto7-2](../../README.md)｜細部規則：[spec.md](spec.md)｜下游：[llmcall](../llmcall/README.md)

**一句話**：node＝一個 AI 的資料夾（裡面有它的 `wf/` 等檔，本例是 `$D`）。寫一份 `prompt.json` 說「這次要給 AI 看哪些檔」，`aos7-prompt render` 每回合照它現讀現拼，產出 llmcall 直接能送的請求；太長的段落自動收起來，要原文再 `expand`。

## 第一次跑（約 1 分鐘）

在 repo 根目錄照抄三行：

```sh
D=$(mktemp -d) && cp -r proto7-2/packs/prompt/examples/node/. "$D"
python3 proto7-2/packs/prompt/bin/aos7-prompt render "$D" "$D/prompts/inbox.json" --max-chars 300 --out "$D/req.json"
python3 proto7-2/packs/prompt/bin/aos7-prompt expand "$D" "$D/req.json"
```

- 第 2 行印一行回條：`"outcome": "rendered"`、`tokens_est`（收起來之後約多少 token）、`tokens_est_full`（不收約多少）、`folded`（收起來的段）。`$D/req.json` 就是要交給 `aos7-llmcall call --request` 的檔。
- 打開 `$D/req.json` 會看到長段變成 `ref://… 已折疊 N 字，預覽：` 加 200 字；原文存在 `$D/refs/`。
- 第 3 行把收起來的段全部換回原文印出來。

## 五個概念

| 概念 | 白話 |
|---|---|
| `prompt.json` | 一張清單：每則訊息寫 `role`（system／user／assistant）和 `content`。 |
| 讀檔寫法 | `content` 寫 `{"$opt": "file", "$val": "wf/AGENTS.md"}` 就是「渲染時讀這個檔」；`tail` 讀最後 `n` 行、`latest` 讀資料夾頂層檔名最大的 `n` 個 `.md`（信件檔名以時間開頭，所以就是最新 `n` 封）。 |
| 取值寫法 | `{"$ref": "a.json#/x"}` 拿別的 JSON 某處的值、`{"$fmt": {"$val": "你好 ${who}", "who": "小明"}}` 填空、`{"$env": "HOME"}` 讀環境變數；`{"$opt": "append", "$val": {"$ref": "prompts/b.json#/messages"}}` 把別份清單的訊息接進來。 |
| 折疊 `ref://` | 一段超過 `max_chars`（預設 6000 字）就把原文存進 `<node>/refs/`，對話裡只留編號＋前 200 字。 |
| token 估值 | 字數 ÷ 3，看每回合有沒有越長越大用的，不是帳。 |

路徑都從 node 算起（包括命令列的 prompt.json 與 `--out`；給絕對路徑也行）。內容可以是一段，也可以是陣列（多段，中間空一行）。

## 指令（兩個）

- `aos7-prompt render <node> <prompt.json> [--out 檔] [--max-chars N]`：拼出請求。有 `--out` 就寫檔、回條印在螢幕；沒有就把請求印在螢幕、回條印到 stderr。`--max-chars 0`＝不收。
- `aos7-prompt expand <node> <ref://編號 或 請求檔>`：印原文。

退出碼：0 成功；2 prompt.json 寫錯（看回條的 `why`）；3 有檔讀不到或繞圈（`$ref` 指回自己）。**失敗時只印一行失敗回條，不輸出請求、`--out` 的檔不動**，不會拼出半份。

## 範例（`examples/node/`）

一個最小的 node：`wf/AGENTS.md`（入口）、`wf/SESSION-LOG.md`（只列 open）、`wf/inbox/`（六封信）。三份 prompt 在 `prompts/`：

1. `entry.json`：AGENTS 入口＋一句問題。
2. `session.json`：入口＋SESSION-LOG 尾 20 行，user 那句用 `$fmt` 填 `note`。
3. `inbox.json`：接上範例 2，再加最新 5 封信。

## 給維護者

程式 `aos7_prompt.py`（只 import `lib/aos_directives*.py` 與 `aos7_fs`，不改它們）、`bin/aos7-prompt`。不呼叫模型、不碰 llmcall／budget。測試：

```sh
python3 proto7-2/tests/run_all.py packs/prompt/tests -v
```

`test_prompt.py` 逐條對 spec；`test_prompt_rounds.py` 模擬 300 回合（SESSION-LOG 只列 open、信讀完搬走），斷言 token 估值曲線平，並有「只加不刪就會變大」的對照組。
