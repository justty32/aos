← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 記憶與紀錄的子命令：`context`、`compact`、`events`、`history --archive`、`notes`

（09-24 工具大開發時代第一波第 4 隊）家一律 `--target DIR`（省略＝目前資料夾），不是 agent 家＝`NotAnAgent`；用法錯退 2；失敗 stderr `aos-agent: <代號>: …` 退 1（同 [cli.md §1](cli.md)）。
都**不要** `AOS_KERNEL_HOME`、都不叫模型。只有 `compact`（不是 `--dry-run`）會寫檔，而且持 tick 鎖。

```
aos-agent context  [--target DIR] [--by-round] [--json]
aos-agent compact  [--target DIR] [--keep-rounds N] [--max-tokens X] [--dry-run] [--json]
aos-agent compact  [--target DIR] --prune-archive 天數
aos-agent events   [--target DIR] [--last N] [--usage] [--json]
aos-agent history  [--target DIR] --archive [SHA] [--grep 字] [--json]
aos-agent notes    [--target DIR] ls [--json] ｜ notes show KEY
aos-agent init     [--target DIR] --template NAME [--force]     # 旗標先留著；第 1 隊的 init_from_template() 合進來才能用
```

## `context`：送給模型的東西多大

唯讀、不拿鎖。跟 `talk` 的 `/context`（[cli-talk-repl.md](cli-talk-repl.md)）是**同一個函式**（`aos_agent_context.lines`），印的一樣：

```
model  default（池 llm）
system 33 字，約 29 token
history 14 則，4028 字，約 1184 token，4 輪（user 4／assistant 7／tool 3）
tools  8 個，5267 字，約 1326 token：read, write, edit, bash, grep, find, ls, date
合計約 9328 字、約 2539 token，每次問模型整份送出（token 是粗估；記憶要縮用 aos-agent compact）
上一次問模型，端點回報 prompt 3169 token（log/usage.jsonl 2026-09-24 18:29:06）
最近 3 則：
  …
```

- 字數：人格全文；記憶每則的 `content`＋工具呼叫的 `arguments`；工具表是拿掉 `_` 開頭 key 後的 JSON。
- **token 是粗估**：ASCII 每 4 字 1 個、其他字（中文）每字 1 個，逐段取整加總。端點的真數字多一截（格式、工具 schema 的包裝；09-24 真跑 deepseek 約是粗估的 1.2～1.3 倍），所以有 `log/usage.jsonl` 就多印最後一次的真數字。
- 輪：一段連續的 `user` 開一輪（[compact.md §2](../agent/compact.md)）。
- `--by-round`：每輪一行 `輪 則範圍 字數 token 工具數 開頭那句  最胖：<工具> N 字（第 i 則）`。
- `--json`：`{"model", "pool", "system": {chars, tokens}, "history": {count, chars, tokens, roles, rounds}, "tools": {count, chars, tokens, names}, "total", "last_usage"}`，加 `--by-round` 多一格 `rounds`。

## `compact`：機械壓縮記憶

規則、恢復、自動、申請都在 [agent/compact.md](../agent/compact.md)。這裡只講命令列：

- `--keep-rounds N`（0 以上）、`--max-tokens X`（100 以上）：沒給就照 `info.json` 的 `compact`，再沒有＝3 輪、上限 32000（`compact` 寫 `false` 或 `max_tokens: 0`＝沒上限）。封存的輪變成每段最多 8 KB 的機械摘要（[compact.md §2](../agent/compact.md)）。
- 成功印：`compacted：記憶 14 則、約 1184 token → 13 則、約 238 token；原文 <archive 路徑>`＋一行各輪怎麼處理；沒得縮印 `nothing to compact：…`；還超過上限多一行「還超過 --max-tokens X…」。都退 0。
- `--dry-run`：同樣的輸出開頭是「（dry-run，沒寫）」，**不寫任何檔、不建鎖檔**。
- 鎖被佔＝stderr `aos-agent: busy: 另一個 tick 正在跑（pid N），…`、**退 101**、不動檔（dry-run 也一樣）。
- 不是 idle、`batch` 不是 `null`、`intake` 做到一半＝`NotIdle` 退 1、不動檔；記憶縮完 `tool_calls` 對不上＝`HistoryInvalid` 退 1、不動檔。
- `--json`：結果物件（`before`、`after`、`rounds`、`over`、`sha`、`archive`…，不含新記憶本身）。
- `--prune-archive 天數`：刪 archive 裡超過天數、**而且現在的記憶沒有提到檔名**的；不跟別的選項一起給。

## `events`：事件與用量

- 印 `log/events.jsonl`（連輪換掉的 `events.1.jsonl`… 一起，舊的在前）最後 N 則（預設 20，`0`＝全部），同 `ev`＋`id` 只印一次（格式與「至少一次」在 [agent/events.md](../agent/events.md)）。一則一行：`時間  ev  id  其他欄位 k=v`。
- `--usage`：改印 `log/usage.jsonl`：`時間  批 id  代號→真名  prompt P  completion C  total T  N ms`。
- `--json`：那幾則原樣的陣列。

## `history --archive`：看壓縮前的原文

唯讀、不拿鎖。`--archive` 現在是唯一的看法、要給（沒給＝用法錯；對話記憶用 `listen --last N` 或 talk 的 `/history`）。

- 什麼都不帶：一份一行 `<sha>  <時間>  <則數> 則  <bytes> bytes`，舊的在前。
- `SHA`（開頭幾個字就行）：印那一份，一則一行 `第 i 則  <role>: …`（則數跟說明行裡寫的一樣從 1 數）。對到多份＝`NotUnique`、沒有＝`NotFound`。
- `--grep 字`：不分大小寫找 `content`、工具參數、工具名，一筆一行 `<sha> 第 i 則  <那一則的短行>`；可跟 `SHA` 一起用只找那一份。

## `notes`：長期筆記（人看）

模型用 `note` 工具寫（[tools/notes/](../../tools/notes/notes.json)：`add`／`find`／`get`／`rm`，存成 `wf-table/1` 的 `notes.json`，只有這個 agent 寫、flock 防同批並行）；人用這裡看：

- `notes ls`：一行一筆 `key  [tags]  時間  前 60 字`；`--json` 印整張 `rows`。`notes show KEY`：全文，沒有＝`NotFound`。
- 筆記檔在哪（工具與人同一條規則）：工具包的 `tools/notes/config.json` 的 `file`（相對＝agent 家；寫 `/work/<名>/…` 就照 `access.json` 換成主機路徑）；沒寫＝家裡有 `access.json`（工具關牢）時是牢裡的 `/work/notes/notes.json`（要先 `aos-agent access set notes <資料夾> --rw`，沒掛＝工具回 `ConfigInvalid` 並說怎麼掛），沒有 `access.json` 時是家裡的 `notes/notes.json`。
- 同包的 `recall`（找記憶與 `archive/` 的原文）、`context`（記憶幾則、約幾 token）只讀記憶資料夾：`AOS_MEM_DIR`＞`config.json` 的 `mem`＞關牢時 `/work/mem`（`aos-team init` 給 `notes: true` 的成員內建唯讀掛自己家的 `prompts/`；自己生的家要 `aos-agent access set mem <家>/prompts --ro`）＞不關牢時家裡的 `prompts/`。token 粗估跟 `aos-agent context` 同一套算法。
- 工具另外認環境變數 `AOS_NOTES_FILE`（最優先）；人這邊看不到工具的環境，所以團隊模板請用 `config.json` 的 `file`，不要用環境變數。
