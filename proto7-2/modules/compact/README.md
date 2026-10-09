# compact 記憶整理包：把舊紀錄換成摘要，未完成項留下

← [modules](../README.md)｜摘要閘道：[llmcall](../../packs/llmcall/README.md)｜事件出口：[events](../events/README.md)

**先備份舊原文，再用一則摘要替換；最近的紀錄與 open 項不丟。核心零改動。**

| 項目 | 內容 |
|---|---|
| 分類 | 記憶整理模組，單 node |
| 接法 | A keep 任務 `aos7-compact watch`；C 工具 `now`、`forget` |
| 預設 | 關，不裝就不存在；裝後預設本機摘要 |
| 依賴 | Python 標準庫、核心 `aos7_fs`、工具包任務端函式；選配 llmcall／events |
| 程式 | `aos7-compact`（薄入口）、`aos7_compact.py`、examples/make_demo.py（造示範資料） |
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
notes/journal.jsonl：220 則 → 21 則（摘掉 200、open 20 全留），102580 → 3964 bytes，原文在 compact/archive/<job>.jsonl
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
4. **觸發**：大小超限、現役段由有項目變空、或人手 force 才整理，少於兩則可摘就不動。
5. **摘要者**：llm 為 null 就用本機摘要，給物件才經 llmcall 問模型。

node 沒有 `compact.json` 時用這份預設；壞 JSON 或不合設定退出 2：

```json
{"files":["wf/SESSION-LOG.md","notes/journal.jsonl"],"max_bytes":16384,"keep_recent":10,"on_stage_change":true,"summary_max_chars":1200,"llm":null}
```

jsonl 的 open 是物件 `open: true`／`status: "open"`，或字串值含 `- [ ]`；壞 JSON 行算一則但不摘要，原樣保留。md 的 open 是第一行以 `- [ ]`／`* [ ]` 開頭，標題、段落、空行、表格是骨架，留在原位。舊摘要也算普通一則，可再摘要。現役段取 files 第一個 md 的第一個 `## ` 到下一個 `## `；前次 ≥1 則、這次 0 則時，全部記憶檔都檢查，不看大小。

## 契約卡

- **職責**：單 node 持鎖選舊段、摘要／忘掉、封存原文、替換檔案與留下 log。
- **前置條件**：node 可讀寫；檔案是 md／jsonl；watch 有任務環境；使用 llmcall 時帳任務已運行、grant 允許 holder 與 gateway。
- **保證**：先 archive 再換檔；now 不摘 open 與最近 N 則；pending 原子保存，SIGKILL 後沿同 call 接續，已有 summary 不再叫摘要。只保證持 write.lock 的追加者：最後讀檔到 rename 持共同短鎖，摘要／llmcall 期間不持有；追加尾巴接回，其他改寫則放棄 pending、下次重規劃；未完成的段落觸發留到全部檔成功。events/ 已存在才發布 obs，沿同 event_id 重送。
- **明確不管**：不拿 write.lock 的追加在換檔瞬間可能丟，明確不管；斷電保證、摘要的語意正確性、封存保留期限；refs/、prompt 組裝、events store 都不由本包管理。

合作的追加者先建 compact/，拿同一把鎖再追加（NODE 是 node 絕對路徑）：

```sh
mkdir -p "$NODE/compact"
export NODE
flock "$NODE/compact/write.lock" sh -c 'echo "{\"open\":true,\"text\":\"新待辦\"}" >> "$NODE/notes/journal.jsonl"'
```

資料都留在 `<node>/compact/`：lock、write.lock、state.json、pending.json、archive/、log.jsonl；req／result 在收尾清掉。本機摘要把每則壓成一行取前 60 字，以「；」串接後截短；llmcall 要求繁體中文、保留決定、數字、檔名與未完成事項。這裡整理的是記憶檔，事件只通知 `compact.done`／`compact.forget`。

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

預期成功，30 則變 11 則，帳 inflight 回 0；fake 回本機摘要文字。10-09 實跑 used 245、available 9755、inflight 0。`litellm` 請求格式已預留，但缺少 packs/llmcall/aos7_llmcall_litellm.py 時，選 `litellm` 回 3、保留 pending，不拿假回覆當真模型摘要。每次沿 pending 的 call_id 重跑，非 0 不拿半張回條替換原文；未成功的 pending 留待下次 now／watch 接續。
