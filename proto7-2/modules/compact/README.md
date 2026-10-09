# compact 記憶整理包：把舊紀錄換成摘要，未完成項留下

← [modules](../README.md)｜摘要閘道：[llmcall](../../packs/llmcall/README.md)｜事件出口：[events](../events/README.md)

**先備份舊原文，再用一則摘要替換；最近的紀錄與 open 項不丟。核心零改動。**

| 項目 | 內容 |
|---|---|
| 分類 | 記憶整理模組，單 node |
| 接法 | A keep 任務 `aos7-compact watch`；C 工具 `now`、`forget` |
| 預設 | 關，不裝就不存在；裝後預設本機摘要 |
| 依賴 | Python 標準庫、核心 `aos7_fs`、工具包任務端函式；選配 llmcall／events |
| 程式 | `aos7-compact`（薄入口）、`aos7_compact.py`、examples/make_demo.py（本機示範）、examples/real_ai.sh／real_journal.jsonl（真 AI 準備） |
| 測試 | `python3 proto7-2/tests/run_all.py modules/compact/tests -v` |

## 第一次跑

從 repo 根照抄，先造資料，再看計畫、實際整理；資料留在暫存 node 供查看。

```sh
N="$(mktemp -d)"; P="$(pwd)/proto7-2"
python3 "$P/modules/compact/examples/make_demo.py" "$N"
python3 "$P/modules/compact/aos7-compact" now "$N" --dry-run
python3 "$P/modules/compact/aos7-compact" now "$N" --force
```

預期給人看的行（job、路徑每次不同；now 最後一行另有 JSON）：

```text
已造好 <node>/notes/journal.jsonl：200 則舊紀錄＋20 則 open
notes/journal.jsonl：220 則，open 20，會摘掉 200 則（原因：大小超過 16384）
notes/journal.jsonl：220 則 → 21 則（摘掉 200、open 20 全留），102580 → 4013 bytes，原文在 compact/archive/<job>.jsonl
```

## 接著試

先看摘要那一則，再人手忘掉；原文另存 archive 的 <job>-forget.jsonl：

```sh
python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1 --dry-run
python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1
```

同指令恢復 pending forget 後直接回報結果，不再刪一次；若接完別的 pending，退出 3，請重看 dry-run 再指定範圍。

## 三個指令

- `aos7-compact now <node> [--dry-run] [--force]`：檢查一次；dry-run 只印逐檔計畫，整個 node 不寫；force 忽略觸發條件。
- `aos7-compact forget <node> --file <相對路徑> --from A --to B [--dry-run] [--include-open]`：1 起算、含頭尾；dry-run 看每則前 80 字。範圍含 open 項就拒絕，明確加 include-open 才忘掉。
- `aos7-compact watch [--rounds N]`：每收到一次自己的 tock 就檢查；不指定 rounds 持續跑。tasks.json 項目：`{"name":"compact","mode":"keep","argv":["python3","<proto7-2>/modules/compact/aos7-compact","watch"]}`（路徑換成絕對路徑）。

退出碼：0 成功或不需要；2 用法／設定／範圍不合；3 摘要未拿到（保留 pending）或鎖忙；1 其他失敗。

## 五個概念

1. **記憶檔**：`compact.json` 的 files 指定要整理的檔，沒有的略過。
2. **則與 open 項**：jsonl 每個 LF 分隔的非空行算一則，md 每個第 0 欄 `- `／`* ` 項加縮排續行算一則；未完成項留下。
3. **最近 N 則**：最後 keep_recent 則原樣保留，再從較舊的非 open 項取摘要。
4. **觸發**：檔太大，或上一段工作清空了、而新開的一段跟上一段不像（相似度低於門檻）；人手 force 也可整理，少於兩則可摘就不動。
5. **摘要者**：llm 為 null 就用本機摘要，給物件才經 llmcall 問模型。

node 沒有 `compact.json` 時用這份預設；壞 JSON 或不合設定退出 2：

```json
{"files":["wf/SESSION-LOG.md","notes/journal.jsonl"],"max_bytes":16384,"keep_recent":10,"on_stage_change":true,"stage_similarity":0.2,"summary_max_chars":1200,"llm":null}
```

jsonl 的 open 是物件 `open: true`／`status: "open"`，或字串值含 `- [ ]`；壞 JSON 行算一則但不摘要，原樣保留。md 的 open 是第一行以 `- [ ]`／`* [ ]` 開頭，標題、段落、空行、表格是骨架，留在原位。舊摘要也算普通一則，可再摘要。現役段取 files 第一個 md 的第一個 `## ` 到下一個 `## `；清空只記結段；下次出現新則，以去空白、小寫的字元 bigram Jaccard 比較新舊原文，低於 stage_similarity（0～1，預設 0.2）才讓全部記憶檔檢查，不看大小。state 保存 stage_last／stage_ended／stage_due；dry-run 只預覽、不寫 state。

`ref://compact/<id>` ＝ `<node>/compact/archive/<id>.<原副檔名>`，存放原樣原文（逐字可接回）。jsonl 摘要帶 ref，md 行尾帶原文 ref；forget 不留則，log／事件帶 `<job>-forget` 的 ref。舊段在檔中連續（中間沒有標題等骨架、open、最近則）時，把摘要則換回 archive 即逐字還原；不連續時內容一字不缺，但位置不還原。SESSION-LOG 的現役段是進行中的工作，不摘要。細部契約與共同寫鎖見 [spec.md](spec.md)。

## 接 llmcall：第二次跑（fake 帳）

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

預期成功，30 則變 11 則，帳 inflight 回 0；fake 回本機摘要文字。10-09 實跑 used 245、available 9755、inflight 0。每次沿 pending 的 call_id 重跑，非 0 不拿半張回條替換原文；未成功的 pending 留待下次 now／watch 接續。


## 接真 AI（第三次跑）

先開自己的 LiteLLM，設定 `AOS7_LITELLM_URL`（例如 `http://localhost:4000/v1`）；需要驗證才設 `AOS7_LITELLM_KEY`。從 repo 根執行：

```sh
bash proto7-2/modules/compact/examples/real_ai.sh ./compact-evidence
```

腳本建暫存 node 與大額帳，整理 60 則開發紀錄、保留 5 則 open；預設 model `chatgpt-gpt-6-sol-high`，不設 max_tokens，一次只花 1 次呼叫，不進測試。輸出資料夾保留 journal 前後、log、llmcall receipt／raw 與 stdout，最後印路徑；暫存 node 也保留。自動驗證只用 fake／本機摘要／本地假 HTTP，沒有實打真 AI。
