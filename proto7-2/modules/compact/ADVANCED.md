# compact 進階

← [README（第一次用）](README.md)

## 接著試：人手忘掉幾則

接著 README「第一次跑」的同一個 shell（`N`、`P` 還在）。先 dry-run 看第 1 則（就是剛才那則摘要）的前 80 字，再真的忘掉；原文仍另存一份到 archive：

```sh
python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1 --dry-run
python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1
```

## 三個指令

- `now <node> [--dry-run] [--force]`：現在檢查一次，需要就整理。`--dry-run` 只看不寫；`--force` 不管檔大小硬整理（原因會印「強制整理（--force）」）。
- `forget <node> --file <路徑> --from A --to B [--dry-run]`：刪掉第 A～B 則（1 起算、含頭尾）；範圍含 open 項會拒絕，要加 `--include-open`。
- `watch`：讓 aos 每回合自動跑 `now`，見下面「常駐：watch」。

每個指令都有 `--help`。

## 設定與觸發

node 裡沒有 `compact.json` 就用這份預設；壞 JSON 或不合設定退出 2：

```json
{"files":["wf/SESSION-LOG.md","wf/handoffs/*/STATE.md","notes/journal.jsonl"],"max_bytes":2048,"keep_recent":5,"on_stage_change":true,"stage_similarity":0.2,"summary_max_chars":1200,"llm":null,"events":false}
```

- `files`：要整理的記憶檔，不存在的略過；含 `*` 的樣式展開成 node 內現有的檔（STATE.md 每天一份）。`keep_recent`：最後幾則原樣保留。`llm` 為 null 用本機摘要，給物件才經 llmcall 問模型（見下）。
- `events`：布林，預設關；開了才在整理完寫一筆 compact.done／compact.forget 到 `<node>/events/`。pending 已清才發布；寫不出只記在 compact/log.jsonl、不算整理失敗，stdout 結果加 `event: "ok"` 或 `"failed"`，主整理 log 欄位不變。
- 觸發有三種，dry-run 與結果行都印出原因：檔超過 `max_bytes`（大小超過 N）、`--force`（強制整理）、段落切換。少於兩則可摘就不動；大小觸發時，可摘的舊則合計不到 `max_bytes` 一半也先不動（免得每回合都整理，設了 llm 就是每回合花錢）。
- 預設門檻的依據（2026-10-09 長任務，12 封信 29 回合）：journal 真 AI 長到 6.5 KB、假 AI 3.0 KB，STATE 2.8／2.2 KB；舊預設 16384 永遠不觸發。2048 bytes 約 700 token，約 brain 一次提示的六分之一，這種長度的任務兩個檔都會整理到。
- 段落切換：現役段取 files 第一個 md 的第一個 `## ` 到下一個 `## `；清空只記結段；下次出現新則，以去空白、小寫的字元 bigram Jaccard 比較新舊原文，低於 `stage_similarity`（0～1）才讓全部記憶檔檢查，不看大小。state 保存 stage_last／stage_ended／stage_due，內容沒變就不寫（只有 jsonl、沒有現役段的 node 不會出現 state.json）；dry-run 只預覽、不寫 state。SESSION-LOG 的現役段是進行中的工作，不摘要。

## 細規則

jsonl 每個 LF 分隔的非空行算一則；open 是物件 `open: true`／`status: "open"`，或字串值含 `- [ ]`；壞 JSON 行算一則但不摘要，原樣保留。md 每個第 0 欄 `- `／`* ` 項加縮排續行算一則；open 是第一行以 `- [ ]`／`* [ ]` 開頭；標題、段落、空行、表格是骨架，留在原位。舊摘要也算普通一則，可再摘要。

`ref://compact/<id>` ＝ `<node>/compact/archive/<id>.<原副檔名>`。jsonl 摘要帶 ref，md 行尾帶原文 ref；forget 不留則，log／事件帶 `<job>-forget` 的 ref。舊段在檔中連續（中間沒有骨架、open、最近則）時，把摘要則換回 archive 即逐字還原；不連續時內容一字不缺，但位置不還原。細部契約與共同寫鎖見 [spec.md](spec.md)。

## 退出碼與出錯時

- 0 做到（含不需要）。
- 1 做不到（目前只有 forget 撞上未完成的舊整理，接完後這次沒忘掉任何則）。
- 2 你給的不對（參數、設定或範圍不合；什麼都沒動）。
- 3 不確定（鎖忙、摘要沒拿到、讀寫故障或未預期錯誤；已有 pending 留著，照原樣再跑一次會接續）。鎖忙時等目前的整理完成再跑。

出錯時 stdout 仍有一行 JSON，stderr 一行人話：`aos7-compact: <發生什麼>。<怎麼辦>`；退 3 以 `aos7-compact: 不確定：` 開頭。成功時 stderr 為空。共通規則見 [blueprint-errors](../../notes/blueprint-errors.md)。

整理中斷會留 pending，下次 `now`／`watch` 先接完；forget 同指令重跑會回報上次結果，不再刪一次，若接完的是別的 pending 則退出 1，先用 --dry-run 重看再指定範圍。

## 常駐：watch

`watch [--rounds N]` 是 aos keep 任務：每收到一次自己的 tock 就跑一次 `now`；不給 rounds 持續跑。tasks.json 項目：`{"name":"compact","mode":"keep","argv":["python3","<proto7-2>/modules/compact/aos7-compact","watch"]}`（路徑換成絕對路徑）。

## 模組資料

| 項目 | 內容 |
|---|---|
| 分類 | 記憶整理模組，單 node |
| 接法 | A keep 任務 `watch`；C 工具 `now`、`forget` |
| 預設 | 關，不裝就不存在；裝後預設本機摘要 |
| 依賴 | Python 標準庫、核心 `aos7_fs`、工具包任務端函式；選配 [llmcall](../../packs/llmcall/README.md)／[events](../events/README.md) |
| 程式 | `aos7-compact`、`aos7_compact.py`、examples/（本機示範、真 AI 準備） |
| 測試 | `python3 proto7-2/tests/run_all.py modules/compact/tests -v` |

## 用 AI 摘要：先用假帳試（llmcall fake）

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

預期成功，30 則變 6 則，帳 inflight 回 0；fake 回本機摘要文字。每次沿 pending 的 call_id 重跑，非 0 不拿半張回條替換原文；未成功的 pending 留待下次 now／watch 接續。

## 用真 AI 摘要

先開自己的 LiteLLM，設定 `AOS7_LITELLM_URL`（例如 `http://localhost:4000/v1`）；需要驗證才設 `AOS7_LITELLM_KEY`。從 repo 根執行：

```sh
bash proto7-2/modules/compact/examples/real_ai.sh ./compact-evidence
```

腳本建暫存 node 與大額帳，整理 60 則開發紀錄、保留 5 則 open；預設 model `chatgpt-gpt-6-sol-high`，不設 max_tokens，一次只花 1 次呼叫，不進測試。輸出資料夾保留 journal 前後、log、llmcall receipt／raw 與 stdout，最後印路徑；暫存 node 也保留。

## 契約卡


- **職責**：單 node 持鎖選舊段、摘要／忘掉、封存原文、替換檔案與留下 log。
- **前置條件**：node 可讀寫；檔案是 md／jsonl；watch 有任務環境；使用 llmcall 時帳任務已運行、grant 允許 holder 與 gateway。
- **保證**：先 archive 再換檔；now 不摘 open、最近 N 則與 files 第一個 md 的現役段（第一個 `## ` 到下一個 `## `，進行中的工作）；pending 原子保存，SIGKILL 後沿同 call 接續，已有 summary 不再叫摘要。STATE.md（`wf/handoffs/` 下）換檔時另持 `wf/handoffs/.state.lock`，跟 `aos7-wfnode state` 的追加互斥。只保證持 write.lock（STATE 為 .state.lock）的追加者：最後讀檔到 rename 持共同短鎖，摘要／llmcall 期間不持有；追加尾巴接回，其他改寫則放棄 pending、下次重規劃；未完成的段落觸發留到全部檔成功。compact.json events 為 true 才發布 obs，發不出只記 log。
- **明確不管**：不拿 write.lock 的追加在換檔瞬間可能丟，明確不管；斷電保證、摘要的語意正確性、封存保留期限；refs/、agent 的 prompt 組裝、events store 都不由本包管理。

