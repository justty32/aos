# llmcall 任務包（LLM 單次呼叫閘道，fake／LiteLLM）

← [proto7-2](../../README.md)｜細部規則：[spec.md](spec.md)｜凍結介面：[llm2 藍圖](../../notes/blueprint-llm2.md)｜依賴：[budget](../budget/README.md)

**固定 call ID 與請求 → reserve → intent → 送一次 → 存原始回覆 → done → settle → 回條。** intent 後沒有回覆就回 unknown，預留留著；同 C 重跑只接續本地證據。

| 項目 | 內容 |
|---|---|
| 分類 | LLM 任務包，單 node，fake／真 LiteLLM 傳輸 |
| 第一版範圍 | 一端點、一計量、單次非串流呼叫；resource `llm.tokens`、gateway `llm.fake`／`llm.litellm` |
| 職責 | 固定請求、防同 call 重送、保存原始回覆與 usage、交付原文及 token 結算回條 |
| 前置條件 | 已開 budget 帳、帳任務運行、固定 grant 允許 holder／資源／入口、本 node round.json 合法；holder 自報、合作式部署 |
| 保證 | call／adopt 持同 call 鎖，拿不到退出 3；intent 先於傳輸；raw 先於 done；已有 raw 不送、已有 receipt 重印；不查遠端、不自動退款 |
| 計量 | `fake.total_tokens/1`／`litellm.total_tokens/1`，只讀 usage.total_tokens 非負整數（bool 不算）；預算上界 `bound: soft` |
| 識別 | `K = (budget_id, holder, call_id)`；call_id 英數／`_`／`-`、1～64 字；logical 只記錄，attempt 不進 K |
| 保存 | `<node>/llmcall/<budget>/<call_id>/` 的 request／raw／receipt 與 call 鎖；入口證據沿用 budget/gateway；保存到預算退役，未結算不清 |
| 依賴 | 標準庫、核心 `aos7_fs`、只讀 import `aos7_budget`；不需要 daemon／step／author |
| 程式 | `aos7_llmcall.py`（閘道＋CLI）、`aos7_llmcall_fake.py`（假傳輸）、`aos7_llmcall_litellm.py`（標準庫 HTTP 傳輸）、`bin/aos7-llmcall`（薄入口） |
| 範例 | `examples/fake/` 的 grant.json 與 req-ok.json |
| 測試 | `tests/test_llmcall.py`（F01～F04、固定請求、adopt、故障邊界）、`tests/test_llmcall_litellm.py`（本地 HTTP、SIGKILL、真傳輸計量）、`tests/llmcallcase.py`（子程序、人工時鐘、獨立核帳） |

## 第一次跑

從 repo 根目錄照抄整段即可；資料在新建暫存 node，結束只收帳任務，保留檔案供查看。不起 daemon：自己寫 closed round.json 即有 completed_tock。本例 reserve 623、usage 623；reserve 1000 時照部分結算只扣 623。

```sh
P="$(pwd)/proto7-2"
LLMCALL_DEMO="$(mktemp -d /tmp/aos7-llmcall-demo.XXXXXX)"
mkdir -p "$LLMCALL_DEMO/.aos" "$LLMCALL_DEMO/budget/llm"
cp "$P/packs/llmcall/examples/fake/grant.json" "$LLMCALL_DEMO/budget/llm/grant.json"
printf '%s\n' '{"round":5,"open":false}' > "$LLMCALL_DEMO/.aos/round.json"
(
  cd "$LLMCALL_DEMO"
  python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm &
  LLMCALL_LEDGER_PID=$!
  trap 'kill "$LLMCALL_LEDGER_PID" 2>/dev/null || true; wait "$LLMCALL_LEDGER_PID" 2>/dev/null || true' EXIT
  python3 "$P/packs/budget/bin/aos7-budget" init budget/llm
  timeout 10 python3 "$P/packs/llmcall/bin/aos7-llmcall" call budget/llm --holder author --call demo-c1 --logical author/demo --request "$P/packs/llmcall/examples/fake/req-ok.json" --reserve 623 --out result.json
  timeout 10 python3 "$P/packs/llmcall/bin/aos7-llmcall" call budget/llm --holder author --call demo-c1 --request "$P/packs/llmcall/examples/fake/req-ok.json" --reserve 623
  python3 "$P/packs/budget/bin/aos7-budget" status budget/llm
  python3 "$P/packs/llmcall/bin/aos7-llmcall" status budget/llm --holder author --call demo-c1
)
printf '資料保留於 %s\n' "$LLMCALL_DEMO"
```

兩次 call 都退出 0，stdout 最後一行相同；answered、used 623、billing final，帳 initial 1000、available 377、inflight 0、used 623。`result.json` 內容與 receipt.json 相同。帳的 patience 計的是完成回合，時鐘停住時不會因牆鐘超時；範例用外層 timeout 防帳未啟動時一直等。

## 真模型一次

[examples/litellm/](examples/litellm/) 提供 grant、req 與 run.sh；從 repo 根執行 `bash proto7-2/packs/llmcall/examples/litellm/run.sh ./evidence`。先啟動自己的 LiteLLM，設定 `AOS7_LITELLM_URL`（預設 `http://localhost:4000/v1`），需要驗證才設 `AOS7_LITELLM_KEY`。腳本開暫存 node／帳任務，reserve 1000000，保存 stdout 回條、status、raw 到指定目錄並印路徑；不在測試套裡跑。

請求頂層 `litellm` 是 OpenAI chat completions body，含字串 model 與 list messages，禁止 stream true、不可與 fake 並存。body 原樣送出，範例不設 max_tokens，閘道也不加任何上限；grant gateway 必須 llm.litellm。完整 HTTP 對應見 [spec](spec.md#傳輸-llmlitellm)。

## 人手指令

在 node 目錄執行（`budget/<id>` 是預算目錄）：

- `aos7-llmcall call budget/<id> --holder H --call C --request req.json --reserve R [--logical L] [--deadline D] [--patience 5] [--out f]`：deadline 是傳輸秒數（0 < deadline ≤ 86400）；未給時 fake＝60、LiteLLM＝86400；patience 是帳回條耐心回合數。
- `aos7-llmcall status budget/<id> --holder H --call C`：唯讀顯示 request、raw 是否存在與 raw_sha、入口、帳上 K、receipt。
- `aos7-llmcall adopt budget/<id> --holder H --call C --raw f`：人工遲到回覆檔為 `{"call_id":"C","req_sha":"request.json 的雜湊","reply":{"status":"ok","billed":true,"body":"原文","usage":{"total_tokens":623}}}`。只收同 C、同雜湊、intent 且無 raw 的回覆；接回後同 C 重跑 call 才算 done、結帳。

## 退出碼與界線

| 碼 | 意義 |
|---|---|
| 0 | answered＋final，內容已交付、已結帳；adopt 成功／status 成功也回 0 |
| 1 | 終局 failed／rejected／denied／cancelled＋final，或 reserve 拒絕、conflict、adopt 不合 |
| 2 | 壞輸入，未送請求 |
| 3 | 未完整交付：busy、intent 無回覆、傳輸逾時／例外、帳未回、讀寫故障 |
| 4 | 已交付但帳未清：usage 未知（pending）或超出預留（overrun） |

usage 未知仍交 text，used／settle 為 null、不送 settle、不寫 receipt，R 留著。U>R 結算 R、另記 U−R overrun，軟預算不宣稱硬上限、不自動停准入。部分結算、overrun 帳累計及不可查回 intent 的 budget cancel 守門（llm.fake 的 intent 下 `aos7-budget cancel` 退出 3、不改入口）靠 budget 的 B2 新語意（`PARTIAL_SETTLE`）；本包只讀 import、不修改 budget。intent 無回覆時唯一的人手出路是 `adopt` 遲到回覆。

支援真 LiteLLM；沒有串流、多端點、價格帳、隱藏重試、遠端查回、llmcall cancel、pending 自動補帳或未結算清理。只驗證程序 SIGKILL 中斷，不承諾斷電持久性。

```sh
python3 proto7-2/tests/run_all.py packs/llmcall/tests -v
```
