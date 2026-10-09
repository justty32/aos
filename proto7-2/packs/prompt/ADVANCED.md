# prompt 進階

← [README（第一次用看這裡）](README.md)｜細部規則：[spec.md](spec.md)

## 指令（兩個）

- `aos7-prompt render <node> <prompt.json> [--out 檔] [--max-chars N]`：拼出請求。有 `--out` 就寫檔、回條印在 stdout；沒有就把請求印在 stdout、回條印在 stderr。
- `aos7-prompt expand <node> <請求檔 或 ref://編號>`：印原文。

## 更多讀法（寫在 `content` 裡）

- `{"$opt": "tail", "$val": "檔", "n": 20}`：只讀最後 20 行。
- `{"$opt": "latest", "$val": "資料夾", "n": 5}`：讀資料夾頂層檔名最大的 5 個 `.md`（檔名以時間開頭時＝最新 5 封）。
- `{"$opt": "append", "$val": {"$ref": "prompts/b.json#/messages"}}`：放在 `messages` 裡，把別份清單的訊息接進來。
- `{"$ref": "a.json#/x"}` 拿別的 JSON 某處的值；`{"$fmt": {"$val": "你好 ${who}", "who": "小明"}}` 填空；`{"$env": "HOME"}` 讀環境變數。

## 收起來的門檻與 refs/

預設一段超過 6000 字收；`--max-chars N` 或清單頂層 `"max_chars": N` 改，`0`＝不收。原文存 `<node>/refs/<sha>.json`，內容定址、相同不重寫、只增不清。`refs/` 可整夾刪：只影響舊請求的 `expand`（會退 3 說原文不見了），重新 render 就補回。

## 回條

成功一行 JSON，`outcome` 是 `rendered`。`chars`／`chars_full` 是收起來後／不收的字數；token 估值＝字數 ÷ 3（`tokens_est`／`tokens_est_full`），用來看每回合有沒有越拼越大，不是帳。`folded` 是收起來的編號，`out` 是 `--out` 的檔或 `null`。

## 出錯時

stderr 兩行：第一行 JSON 回條 `{"v":1,"outcome":"bad"|"unknown","code":…,"why":…}` 給程式讀；第二行給人看，格式 `aos7-prompt: <發生什麼>。<怎麼辦>`。命令列用法錯（缺參數、未知選項）只有人話一行。任何失敗都不輸出請求、不動 `--out` 的檔。

退出碼意義全 aos 共用，見 [blueprint-errors §2](../../notes/blueprint-errors.md#2-統一退出碼表全-aos-共用只有五個)。本包用到三個：

- **0** 拼好或展開好。
- **2** 你給的不對（`outcome: bad`）：清單形狀、選項、指示詞寫錯，node 不是資料夾，命令列用法錯。
- **3** 不確定（`outcome: unknown`，人話以 `不確定：` 開頭）：檔讀不到、不是 UTF-8、`$ref`／`append` 繞回自己、環境變數不在、ref 原文不見或對不上、寫檔失敗。哪個代號歸哪碼見 [spec §6](spec.md#6-退出碼)。

## 範例清單（`examples/node/prompts/`）

node 裡的 `wf/`（`AGENTS.md` 入口、`SESSION-LOG.md`、`wf/inbox/` 信）是 [wfnode](../../modules/wfnode/README.md) 裝出來的資料夾樣子，本包只讀它、不管它的規矩。

1. `entry.json`：讀 AGENTS 入口＋一句問題。
2. `session.json`：入口＋SESSION-LOG 尾 20 行，user 那句用 `$fmt` 填 `note`。
3. `inbox.json`：接上範例 2，再加最新 5 封信。

## 契約卡

- **職責**：照 `prompt.json` 現讀現拼出 llmcall 吃的請求；超過門檻的段收成 `ref://`，`expand` 換回原文。
- **前置條件**：node 是已存在的資料夾；相對路徑從 node 算。
- **保證**：先解完讀完才寫；失敗不輸出半份、`--out` 不動；`expand(render(P, m)) == render(P, 0)`（原文本身不含收起來的標頭時）；`refs/` 內容定址、可重跑。
- **副作用**：只寫 `<node>/refs/<sha>.json`（有段被收時）與 `--out` 的檔。不鎖、不起程序、不連網。
- **明確不管**：不送請求、不呼叫模型、不碰 llmcall／budget；token 估值不準（只看趨勢）。

## 給維護者

程式 `aos7_prompt.py`（只 import `lib/aos_directives*.py` 與 `aos7_fs`，不改它們）、`bin/aos7-prompt`。測試：

```sh
python3 proto7-2/tests/run_all.py packs/prompt/tests -v
```

`test_prompt.py` 逐條對 spec（含錯誤路徑的兩行格式）；`test_prompt_rounds.py` 模擬 300 回合（SESSION-LOG 只列 open、信讀完搬走），斷言 token 估值曲線平，並有「只加不刪就會變大」的對照組。
