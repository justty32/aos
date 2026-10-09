# compact 記憶整理包：把舊紀錄換成摘要，未完成項留下

← [modules](../README.md)

**node 就是一個工作資料夾**（aos 裡一個 agent 的家）。compact 看這個資料夾裡的記憶檔，太長時先把舊原文存進 `compact/archive/`，再換成一則摘要；最近 10 則和未完成（open）的項目原樣留下。

## 第一次跑（約 1 分鐘）

從 repo 根照抄：造一個示範 node、看計畫、實際整理。

```sh
N="$(mktemp -d)"; P="$(pwd)/proto7-2"
python3 "$P/modules/compact/examples/make_demo.py" "$N"
python3 "$P/modules/compact/aos7-compact" now "$N" --dry-run
python3 "$P/modules/compact/aos7-compact" now "$N"
```

預期看到這三行（`<node>`、`<job>` 每次不同；`now` 最後另印一行 JSON 給程式讀，可以不看）：

```text
已造好 <node>/notes/journal.jsonl：200 則舊紀錄＋20 則 open
notes/journal.jsonl：220 則，open 20，會摘掉 200 則（原因：大小超過 16384）
notes/journal.jsonl：220 則 → 21 則（摘掉 200、open 20 全留），102580 → 4013 bytes，原文在 compact/archive/<job>.jsonl（原因：大小超過 16384）
```

dry-run 和實跑印的是同一個原因：示範檔超過 16384 bytes，所以 `now` 自己就會整理。再跑一次 `now` 會說「不需要整理」。舊原文一字不缺在 `$N/compact/archive/`。

**到這裡就會用了。** 下面「接著試」可選，「進階」第一次可以不讀。

## 接著試：人手忘掉幾則

先 dry-run 看第 1 則（就是剛才那則摘要）的前 80 字，再真的忘掉；原文仍另存一份到 archive：

```sh
python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1 --dry-run
python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1
```

## 三個指令

- `now <node> [--dry-run] [--force]`：現在檢查一次，需要就整理。`--dry-run` 只看不寫；`--force` 不管檔大小硬整理（原因會印「強制整理（--force）」）。
- `forget <node> --file <路徑> --from A --to B [--dry-run]`：刪掉第 A～B 則（1 起算、含頭尾）；範圍含 open 項會拒絕，要加 `--include-open`。
- `watch`：讓 aos 每回合自動跑 `now`，見進階。

每個指令都有 `--help`。

## 四個概念

1. **node**：一個工作資料夾。
2. **記憶檔與「則」**：預設看 `notes/journal.jsonl`（一行一則）和 `wf/SESSION-LOG.md`（一個 `- ` 項目一則）。
3. **open 項**：還沒做完的（jsonl 有 `"open": true`，md 是 `- [ ]`），永遠不摘。
4. **archive**：被摘掉或忘掉的原文都原樣存在 `<node>/compact/archive/`，可逐字找回。

## 進階（第一次可以不讀）

### 設定與觸發

node 裡沒有 `compact.json` 就用這份預設；壞 JSON 或不合設定退出 2：

```json
{"files":["wf/SESSION-LOG.md","notes/journal.jsonl"],"max_bytes":16384,"keep_recent":10,"on_stage_change":true,"stage_similarity":0.2,"summary_max_chars":1200,"llm":null}
```

- `files`：要整理的記憶檔，不存在的略過。`keep_recent`：最後幾則原樣保留。`llm` 為 null 用本機摘要，給物件才經 llmcall 問模型（見下）。
- 觸發有三種，dry-run 與結果行都印出原因：檔超過 `max_bytes`（大小超過 N）、`--force`（強制整理）、段落切換。少於兩則可摘就不動。
- 段落切換：現役段取 files 第一個 md 的第一個 `## ` 到下一個 `## `；清空只記結段；下次出現新則，以去空白、小寫的字元 bigram Jaccard 比較新舊原文，低於 `stage_similarity`（0～1）才讓全部記憶檔檢查，不看大小。state 保存 stage_last／stage_ended／stage_due；dry-run 只預覽、不寫 state。SESSION-LOG 的現役段是進行中的工作，不摘要。

### 細規則

jsonl 每個 LF 分隔的非空行算一則；open 是物件 `open: true`／`status: "open"`，或字串值含 `- [ ]`；壞 JSON 行算一則但不摘要，原樣保留。md 每個第 0 欄 `- `／`* ` 項加縮排續行算一則；open 是第一行以 `- [ ]`／`* [ ]` 開頭；標題、段落、空行、表格是骨架，留在原位。舊摘要也算普通一則，可再摘要。

`ref://compact/<id>` ＝ `<node>/compact/archive/<id>.<原副檔名>`。jsonl 摘要帶 ref，md 行尾帶原文 ref；forget 不留則，log／事件帶 `<job>-forget` 的 ref。舊段在檔中連續（中間沒有骨架、open、最近則）時，把摘要則換回 archive 即逐字還原；不連續時內容一字不缺，但位置不還原。細部契約與共同寫鎖見 [spec.md](spec.md)。

### 退出碼與中斷

0 成功或不需要；2 用法／設定／範圍不合；3 摘要未拿到（保留 pending）或鎖忙；1 其他失敗。整理中斷會留 pending，下次 `now`／`watch` 先接完；forget 同指令重跑會回報上次結果，不再刪一次，若接完的是別的 pending 則退出 3，請重看 dry-run 再指定範圍。

### 常駐：watch

`watch [--rounds N]` 是 aos keep 任務：每收到一次自己的 tock 就跑一次 `now`；不給 rounds 持續跑。tasks.json 項目：`{"name":"compact","mode":"keep","argv":["python3","<proto7-2>/modules/compact/aos7-compact","watch"]}`（路徑換成絕對路徑）。

### 模組資料

| 項目 | 內容 |
|---|---|
| 分類 | 記憶整理模組，單 node |
| 接法 | A keep 任務 `watch`；C 工具 `now`、`forget` |
| 預設 | 關，不裝就不存在；裝後預設本機摘要 |
| 依賴 | Python 標準庫、核心 `aos7_fs`、工具包任務端函式；選配 [llmcall](../../packs/llmcall/README.md)／[events](../events/README.md) |
| 程式 | `aos7-compact`、`aos7_compact.py`、examples/（本機示範、真 AI 準備） |
| 測試 | `python3 proto7-2/tests/run_all.py modules/compact/tests -v` |

### 用 AI 摘要：先用假帳試（llmcall fake）

仍從 repo 根照抄；帳任務在子 shell 收掉，時鐘固定第 5 回合，外層 timeout 防啟動失敗一直等。

```sh
P="$(pwd)/proto7-2"
COMPACT_LLM="$(mktemp -d /tmp/aos7-compact-llm.XXXXXX)"
export COMPACT_LLM
python3 - <<'PY'
import json, os
from pathlib import Path
n = Path(os.environ['COMPACT_LLM'])
for d in ('.aos', 'budget/llm', 'notes'): (n / d).mkdir(parents=True)
(n / '.aos/round.json').write_text('{"round":5,"open":false}')
grant = dict(v=1, grant='compact-demo', budget='llm', holder='compact', resource='llm.tokens', gateway='llm.fake', amount=10000, clock='completed_tock', until=1000, delegate=False)
grant['from'] = 0
(n / 'budget/llm/grant.json').write_text(json.dumps(grant))
(n / 'compact.json').write_text(json.dumps({'llm': dict(budget='budget/llm', holder='compact', reserve=4000, gateway='fake', model='chatgpt-gpt-6-sol-high', deadline=600, patience=5)}))
(n / 'notes/journal.jsonl').write_text(''.join(json.dumps({'text': f'完成紀錄 {i}'}, ensure_ascii=False) + '\n' for i in range(30)))
PY
(
  cd "$COMPACT_LLM"
  python3 "$P/packs/budget/bin/aos7-budget" init budget/llm
  python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm &
  COMPACT_LEDGER_PID=$!
  trap 'kill "$COMPACT_LEDGER_PID" 2>/dev/null || true; wait "$COMPACT_LEDGER_PID" 2>/dev/null || true' EXIT
  timeout 15 python3 "$P/modules/compact/aos7-compact" now "$COMPACT_LLM" --force
  python3 "$P/packs/budget/bin/aos7-budget" status budget/llm
)
```

預期成功，30 則變 11 則，帳 inflight 回 0；fake 回本機摘要文字。每次沿 pending 的 call_id 重跑，非 0 不拿半張回條替換原文；未成功的 pending 留待下次 now／watch 接續。

### 用真 AI 摘要

先開自己的 LiteLLM，設定 `AOS7_LITELLM_URL`（例如 `http://localhost:4000/v1`）；需要驗證才設 `AOS7_LITELLM_KEY`。從 repo 根執行：

```sh
bash proto7-2/modules/compact/examples/real_ai.sh ./compact-evidence
```

腳本建暫存 node 與大額帳，整理 60 則開發紀錄、保留 5 則 open；預設 model `chatgpt-gpt-6-sol-high`，不設 max_tokens，一次只花 1 次呼叫，不進測試。輸出資料夾保留 journal 前後、log、llmcall receipt／raw 與 stdout，最後印路徑；暫存 node 也保留。
