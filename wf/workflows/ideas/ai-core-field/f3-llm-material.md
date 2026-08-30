# F3 采風：LLM 當材料（cllm ＋ galtxt ＋ llm_forge）

← [ai-core-field](README.md)｜隊長 Fable，隊員 codex ×3（sol／terra／luna 各讀一個子專案）｜2026-08-30

範圍：`~/repo/ai_core/sub_projs/{cllm,galtxt,llm_forge}` 文件層，外加兩者共同指向的
idea 礦脈 `ai_core/workflows/notes/20260713-0956-galgame台詞生成-第一目標問題-llm_forge.md`
與 `sub_projs/ver_1/try_implement/core_handy/examples/llm_entry.cpp`（aos `llm` 的直系前輩）。
以下路徑一律相對 `~/repo/ai_core/`；aos 側相對 aos repo 根。

## ① 那塊在講什麼（白話）

- **cllm**：把「一次 LLM 往返」收成兩個交付物——`libcllm.so` 唯一 C ABI 入口 `llm_ask`，
  以及建在其上的 `llm` unix filter（prompt 走位置參數＋stdin、答案 stdout、診斷 stderr、
  退出碼 0/1/2/130）。它**不是 agent loop**：tool calling 只是把定義送給模型、把 tool_call 一行一 JSON
  吐出來，「要不要執行、要不要回送」全交呼叫端（`core/bindings/README.md:88`「tools 是單輪」）。
  `apps/`（llme／zhtw／wf／mail 四工具、四種語言）是「LLM 程式被別的程式當 tool 呼叫」的活範例：
  各語言只寫膠水，真正的手是 shell-out 到 `llm`／`claude`／sibling，exit code 透傳。
- **galtxt**：galgame 台詞生成實驗場。結論很硬：**執行期零 LLM**——LLM 只在建材期炸候選、
  人審蓋章入庫，執行期是純程式的「枚舉→護欄剪枝→成本排序→取最小」搜尋機
  （`galtxt/corpus/固化/README.md:42`、`galtxt/一台搜尋機.md`）。階段之間傳結構化 act，不傳半成品文字。
- **llm_forge**：機制之家，目前無程式碼。五個機制：固化階梯（5 自由創作→1 純查表）、
  批次固化先於自動固化、雙錨驗證（語料錨＝粗胚、人錨＝精修，礦是「✗ 的理由」不是 ✓✗）、
  評分級聯（Tier 0 護欄→1 語料→2 校準 judge→3 人工抽查，便宜到貴、短路早退）、
  世界模型（真值）≠ context（LLM 投影）。
- **core_handy `llm_entry.cpp`**：one-shot `stdin prompt → stdout completion`；`--serve <sock>` 長駐、
  循序佇列、跨呼叫共用 RateMeter；`--metadata` 自述九軸（entries／persistent／stateful／resources／
  guarantee／uncertainty）。ai_core 定調「語言中立的縫＝socket 協定＋`--metadata` 文字契約」。

一句話：**前輩把 LLM 收成一支會自述、退出碼可機讀、錯誤不吞的 POSIX filter；再把「呼叫 LLM」
從執行期往建材期趕。**

## ② aos 已承接的

| aos 現況 | 對應前輩 |
|---|---|
| `aos llm`：stdin→stdout、stderr＋非零退出、`AOS_LLM_URL/MODEL/KEY`、`--timeout-ms`（`core/llm/README.md`） | `llm_entry.cpp:3` one-shot 形狀、`AI_CORE_LLM_*` 三個 env 一比一 |
| inst 信封 `argv/env/cwd/stdin/timeout_ms` → `exit/signal/stdout/stderr`（`PROTOCOL.md §2–3`） | 正是 cllm apps「shell-out、exit 透傳」所需的最小 OS 契約 |
| **loop 一律把子行程 stdin 接到暫存檔**（`core/exec/src/start.cpp:59,98`），沒給 `stdin` 就是空檔＝立即 EOF | 躲掉 cllm 最痛的坑「非 TTY 不等於會送 EOF」（`cllm/core/workflows/common/gotchas/backend.md:22`）。**這是設計上做對的，值得寫進 PROTOCOL 當保證** |
| `agents/<name>/tools.json`（name／description／argv 模板）＋回覆末行 JSON 叫工具、工具＝投一條 inst | ai_core「LLM 負責決策、確定函式負責執行」（`docs/kb/knowledge_base/doc_20_taming_framework.md:78`）；每次工具呼叫都落在 `batch/<turn>/`＝天生的 trace 礦堆 |
| `ideas/llm-cpu.md`「LLM CPU 疊在 inst 之上、交接就是 exec」 | 與 cllm apps「不 link libcllm、只 shell-out」是同一個判斷 |
| `--engine pi`：外部 LLM 程式當第二顆 CPU，stdin 餵 prompt、JSONL 收結果 | 實證「LLM 程式本身也是 tool」；pi 的 `-p --mode json` 就是 cllm `--tool` 那種「一行一 JSON 吐 stdout」 |

## ③ aos 漏掉／走偏的（附兩邊證據）

1. **退出碼只有 0/1，錯誤不分類、不標可重試。** aos：`core/llm/README.md`「連線、HTTP、JSON 或回應格式錯誤…回傳 exit code 1」。
   前輩：cllm `cli-manual.md:128` 三段分流「1 用法錯／2 請求失敗／130 取消」；core_handy 錯誤封套
   `type ∈ bad_json/bad_request/…/timeout`＋「timeout 可重試、bad_request 不該重試」
   （`docs/kb/knowledge_base/code_02_prototype_tools.md:181`）。aos 的 loop 與 agent 拿到 `exit=1` 無法決定重投還是放棄。
2. **後端 error JSON 沒被當成一等錯誤。** aos `core/llm/src/llm.cpp:160-167`：回應沒有 `choices` 就丟
   「LLM 回應缺少 choices[0].message.content」——不吞成空（好），但 HTTP 狀態碼與 `error.message` 都丟了。
   前輩：`gotchas/backend.md:10`「後端錯誤就被吞成空字串、還報成功——對『笨模型＋護欄』這正是最該堵的洞」，
   對策 `guard_backend_error(status, raw)`：HTTP≥400 或含 `{"error":{"message"}}` 先攔、帶狀態碼＋body 片段。
3. **tools.json 的表述太薄，且程式不自述。** aos `core/agent/src/tools.cpp:29-36`：`{name, description, argv:["ls","{args}"]}`，
   `args` 是一個字串、由 agent 手寫進 system prompt；程式本身沒有任何自述入口。
   前輩：cllm 送模型看的是 `name/description/parameters(JSON Schema)`（`c-abi-input.md:101`），
   core_handy 每支程式回應 `--metadata` 吐九軸 JSON（`core_handy/notes/00_index.md`「lib 的存在意義就是產出會正確回應 `--metadata` 的 shell 程式」）。
   **aos 的登記表現在是「agent 對 tool 的看法」，不是「tool 對自己的宣告」**——多一隻 agent 就多一份真相。
4. **結構化輸出走自定協定，沒接後端能力。** aos 用「回覆最後一行獨立 JSON」（`core/agent/README.md`）；
   `aos llm` 沒有 `--schema`／`--tool`。前輩：`backend-structured-output.md` 15 後端矩陣——
   LM Studio（aos 預設）支援 json_schema→GBNF，tool calling 是最通用的一條，且結論是
   「別把可靠性押在後端 strict schema 上，最通用＝tool calling＋client 端 schema 驗證＋retry/guard」。
   aos 的末行 JSON 是 client 端驗證那一半，缺的是前一半。
5. **pi 引擎繞過 inst＝繞過礦堆。** aos `pi-cpu.md`：「pi 的工具動作不是 inst，不會出現在 `batch/<turn>/`…世界裡有一段 aos 看不見的行為，這是最大取捨」。
   前輩：llm_forge 整套飛輪靠 trace（`docs/kb/kb-ext/ext_07_observability_and_provenance.md:6`
   「這些紀錄是『固化引擎』進行學習的原始素材」）。pi 一回合做完很快，但**沒有任何東西可固化**；
   pi 若要留，至少把 `tool_execution_start/end` 事件轉存進 `batch/<turn>/out/`（pi-cpu.md 已示範怎麼取）。
6. **「LLM 只在建材期」這條方向 aos 完全沒有。** galtxt `gen_v0/README.md:21`「編譯期 LLM 炸候選＋人審入庫、執行期只查」；
   aos 的 agent 每回合有新訊息就打 LLM。這不是 bug，是 aos 目前只有「消費期」沒有「工廠期」概念——
   tool 登記表若不區分 `stage: build|runtime`，之後固化出來的表／模板沒地方放。
7. **驗證形狀。** aos `core/llm/tests/test_llm.cpp`＋agent 測試注入固定回覆（全離線），沒有黑箱 smoke、沒有「髒／失敗回應」fixture。
   前輩：`cllm/core/test/cli_smoke.sh` 45 case 真 spawn binary 驗 stdout／退出碼，fixture 走 `file://`；
   且 `gotchas/backend.md:8`「fixture 只投影成功、從不投影失敗…新接口一定要對真後端打一次」。
8. **C ABI：不要。** cllm 要 C ABI 是因為十語言 binding 都想「不碰 CMake/vcpkg」（`bindings/README.md:5`）；
   aos 的多語言縫是 POSIX exec（`llm-cpu.md`、cllm apps 也是這麼選的）。`aos::llm` 留 C++ 內部庫、對外只有 `aos llm` 子命令就夠。
   同理 **daemon／RateMeter 先不做**：`llm-cpu.md` 列它為開放問題，core_handy 的 `--serve` 是 socket 協定「懸、先不選」（礦脈 §9.3），cllm 自己也沒有 daemon。
   等多隻 agent 真的打爆本機 LM Studio 再說。

## ④ 對 tool 登記表與表述的具體建議

**原則**：tool＝任何 POSIX 可呼叫的程式，`aos llm`、`pi`、`sh` 都是 tool，**同一張表**。表分兩層：
`exec`（給 loop／OS 看，怎麼呼叫）與 `model`（給 LLM 看，就用 cllm 已驗的 `name/description/parameters` 三欄，不發明第二套）。
登記檔放世界層 `.aos/tools/<name>.json`（一檔一 tool，跟 inbox 同款、同樣 tmp＋rename），agent 的 `tools.json` 降成「這隻 agent 允許用哪些 name」的白名單。

```json
{
  "name": "llm",
  "exec": {
    "argv": ["aos", "llm", "--system", "{system}"],
    "stdin": "text",
    "stdout": "text",
    "stderr": "diagnostic",
    "exit_codes": {"0": "ok", "1": "usage", "2": {"meaning": "backend_or_transport", "retryable": true}},
    "timeout_ms": 120000,
    "env": ["AOS_LLM_URL", "AOS_LLM_MODEL", "AOS_LLM_KEY"]
  },
  "model": {
    "name": "llm",
    "description": "把 stdin 的文字丟給本機 LLM，stdout 回答案。慢、不確定，能查表就別用。",
    "parameters": {"type": "object", "required": ["stdin"],
                   "properties": {"stdin": {"type": "string"}, "system": {"type": "string"}}}
  },
  "meta": {"nondeterministic": true, "network": true, "stateful": false,
           "stage": "runtime", "verified_with": ["LM Studio qwen/qwen3.5-9b"], "as_of": "2026-08-30"}
}
```

逐欄為什麼（每條都有前輩證據）：
- `exec.argv` 模板改成**具名槽 `{param}`**，槽名對應 `model.parameters.properties`；`{args}` 單字串保留為退化情形。
  理由：cllm tool_call 的 `arguments` 本來就是 schema 約束的物件（`cli-manual.md:121`），單字串等於把解析責任丟回 LLM。
- `exec.stdin`：`none|text|json`。loop 已保證 EOF（②），登記表只需說「吃不吃」。
- `exec.exit_codes` 帶 `retryable`：抄 core_handy 錯誤封套；`aos llm` 自己先照 cllm 分成 0/1/2/130。
- `exec.stdout`：`text|jsonl|json|paths`——cllm 三種 stdout 模式（文字／一行一 JSON／落檔路徑）證明「stdout 只有文字」撐不了 LLM 程式；pi 的 JSONL 也是 `jsonl`。
- `meta`：只抄九軸裡對 aos 有消費者的四個（`nondeterministic`／`network`／`stateful`／`stage`），其餘進 `extra` 逃生艙
  （core_handy「先進 extra，夠格再升」）。`stage: build|runtime` 是為 galtxt 那條「固化物」留位子。
- `verified_with/as_of`：「OpenAI 相容」只保證 wire format、不保證能力面（`backend-structured-output.md:44`），能力要標實測對象與日期。
- **自述**：所有 `aos` 子命令回應 `--metadata` 吐上面這份 JSON（core_handy 的 `intercept` 形狀：命中就吐＋exit，否則續跑）；
  第三方程式（`ls`、`pi`）由人手寫登記檔。這樣 `aos tools`（列表指令）＝掃 `.aos/tools/*.json`＋對可執行檔試 `--metadata`。
- **給 LLM 的表述**只渲染 `model` 三欄（name／description／parameters），跟現在 system prompt 列表一樣薄；
  `exec`／`meta` 永遠不進 prompt。description 寫「代價」（慢／要錢／不確定），這是 galtxt「能查表就別問 LLM」的入口。

## ⑤ 值得直接抄的檔案

| 路徑（相對 `~/repo/ai_core/`） | 為什麼 |
|---|---|
| `sub_projs/cllm/core/docs/cli-manual.md` | 一支 LLM filter 的完整契約範本：prompt 來源表、stdout/stderr 分流、退出碼三段＋130、config 三層——`aos llm` README 照這個結構重寫 |
| `sub_projs/cllm/core/workflows/common/gotchas/backend.md` | 四個必踩坑（stdin EOF、空成功、`required`、靜默忽略能力）＋「fixture 只投影成功」方法論；aos 的 testing.md 該轉錄 |
| `sub_projs/cllm/apps/HANDY-PORT-SPEC.md` | 最接近「tool 呼叫 tool」的現成 ABI：shquote、exit 透傳、stdin 只在非 TTY 讀、sibling 解析＋env 覆寫、`LLME_LLM=echo` dry-run 測法 |
| `sub_projs/cllm/core/docs/backend-structured-output.md` | 15 後端 × 3 種結構化輸出矩陣；決定 `aos llm --schema/--tool` 要送哪一種、對 LM Studio 走 json_schema |
| `sub_projs/cllm/core/docs/c-abi-reference.md` | 不抄 ABI，抄「回傳值三分（取消<0／成功 0／錯誤>0）」與「所有權：庫不配置要呼叫端釋放的東西」兩條原則 |
| `sub_projs/cllm/core/test/cli_smoke.sh` | 黑箱 smoke 的形狀：真 spawn、`file://` fixture、驗 stdout＋退出碼；aos 缺這一層 |
| `sub_projs/ver_1/try_implement/core_handy/examples/llm_entry.cpp` | `aos llm` 的直系前輩：`--metadata` 自述、one-shot、`--serve` 佇列＋RateMeter——後兩者是之後 daemon 題的起點 |
| `sub_projs/ver_1/try_implement/core_handy/defs/axes.hpp` | 九軸 `Meta` 的最終形狀（固定欄位＋單一 `extra`）；④ 的 `meta` 段從這裡挑欄位 |
| `docs/kb/knowledge_base/code_02_prototype_tools.md` | 錯誤封套 `type`＋`retryable`、「單一執行檔多種 lifecycle」、「另起 process 會讓 rate 不累計」三個 Gap 的修法 |
| `sub_projs/galtxt/corpus/固化/README.md` | build／runtime 分層＋「執行期零 LLM」的論證；tool 表 `stage` 欄的出處 |
| `sub_projs/galtxt/gen_v1/00_設計.md` | 階段間傳結構化 act、「讀處處可讀、寫只有兩道門」——agent history 記事實不記字面的範本 |
| `workflows/notes/20260713-0956-galgame台詞生成-第一目標問題-llm_forge.md` §二、§四 | 固化階梯與評分級聯原文；aos 若要做「LLM judge 當 tool」，Tier 表就是它的登記表雛形 |

**隊長裁決（三句）**：`aos llm` 該長成 cllm 那種 filter（退出碼分流、error JSON 一等、`--schema/--tool`），
**不要** C ABI、**先不要** daemon；tool 登記表兩層＋自述 `--metadata`，LLM 程式與 `ls` 同表；
pi 留著但必須把工具事件回填 `batch/`，否則跟 llm_forge 的飛輪斷線。
