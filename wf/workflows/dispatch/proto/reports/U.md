# 隊 U 回報：tool 登記表與 agent 通訊錄做進 aos

← [交接書](../proto-U-tools-impl.md)｜[PROTOCOL](../PROTOCOL.md)｜規劃與裁決 [ideas/tools](../../../ideas/tools/README.md)｜[dispatch](../../README.md)

**STATUS：DONE**

commit `bdb3595`（實作）＋ 本報告。分支 main，直接在 working tree 做，沒有 push。

## 做了什麼

新增核心小專案 **`core/tool`**（`aos::tool` → `libaos_tool.so`），掛 `aos tool` 與 `aos contact` 兩條子命令；`core/agent` 改成消費它。

| 產物 | 內容 |
|---|---|
| `core/tool/` | 登記表 `Spec` 的 JSON 邊界、`.aos/tools/` 原子讀寫、`--metainfo` 三級探測、`.aos/contacts.json` 讀寫、兩支 CLI、13 個測試檔／helper |
| `core/agent/` | 白名單化、一行表述、args 三形狀、固定 JSON 結果／錯誤退回、`aos say --to` |
| `.aos/tools/*.json` | repo 根五項範例登記 `sh`／`ls`／`cat`／`git`／`aos`，`.gitignore` 放行 |
| 文件 | `core/tool/README.md`、`core/agent/README.md` 改寫、`wf/workflows/common/code-map.md` 新增 `core/tool` 節並重抓行號、`ideas/tools/README.md` 追加實作註記 |

裁決落點：1 一檔一 tool ✅｜2 必填三欄 ✅｜3 欄位名扁平照九軸 ✅｜4 args 三形狀 ✅｜5 不做具名槽 ✅｜6 `--metainfo`，`--probe metadata` 才試 `--metadata` ✅｜7 `predictability` 不強制 ✅｜8 精簡文字行＋client 驗證 ✅｜9 三回合往返不壓 ✅｜10 固定 JSON 退回、安全不管 ✅｜11 pi 路徑沒動 ✅｜12 世界層通訊錄、`agent init` 不碰 ✅

## 六條驗收的證據

| # | 驗收 | 結果 |
|---|---|---|
| 1 | build＋ctest 全綠 | `cmake --build --preset default` 無 error／warning；`ctest --preset default` → **100% tests passed out of 8**（原 7 個＋新的 `aos_tool_tests`）；另跑 `bash core/agent/tests/smoke.sh` → `smoke OK` |
| 2 | 空資料夾 `W` 的 `aos tool add` | `aos tool add echo --folder $W -- echo` → `echo.json` 有 `name`／`argv`／`description`（`source: header`，因為 `echo --metainfo` 會把旗標印回來，走第 2 級降級）；`aos tool add fake --folder $W -- $W/fake-metainfo.sh` → `description: "假的自述工具：回一段 JSON"`、`source: metainfo`、連帶收下 `predictability: low` |
| 3 | `aos agent init` | 空資料夾 init 後 `.aos/tools/` ＝ `cat.json ls.json sh.json`；`agents/<name>/` 底下**沒有** `tools.json`（白名單缺席＝全部可用）；`aos state` 印出正常 status JSON |
| 4 | 真 LM Studio 三回合 | `aos say "列出目前資料夾的檔案"` → `aos run --step 1` ×5。log.md：turn 1 assistant 寫出 `{"tool":"ls","args":["-la", "."]}`、投遞成 `["ls","-la","."]`；turn 3 tool 訊息是 `{"args":["-la","."],"call_id":"agent-bob-tool-1-0","ok":true,"result":{"exit":0,…,"stdout":"total 0\n…\n.aos\n"},"tool":"ls"}`；turn 3 assistant 引用結果回「目前資料夾內沒有檔案，只有一個名為 `.aos` 的子資料夾」 |
| 5 | 假回覆 `{"tool":"nope","args":[]}` | 測試接縫（注入 completion）：`aos_agent_tests "agent returns tool call errors and resumes thinking next step"` → 15 assertions 全過。history 末項 `role == "tool"`，內容是 `{"call_id":"agent-bob-tool-7-0","tool":"nope","args":[],"ok":false,"result":null,"error":{"type":"unknown_tool","message":"沒有登記工具 nope","retryable":false}}`；**下一個 step** 確實把它送進 LLM（callback 被呼叫且看得到那則 tool 訊息） |
| 6 | contacts 與版控 | `aos contact add bob ../bob --folder-root $W && aos contact ls` 列出 `bob ../bob`；`python3 -m json.tool .aos/contacts.json` 解析成功（頂層陣列）；repo 根 `git check-ignore .aos/tools/ls.json` 回 exit 1（不再被忽略），五個 json 已隨 `bdb3595` 進版控 |

## 隊長裁決

| # | 裁決 | 為什麼 |
|---|---|---|
| 1 | **`aos tool`／`aos contact` 獨立成 `core/tool`**，`core/agent` 公開相依它 | 交接書把這一題留給隊長。登記表是**世界層**的東西，跟「agent 的准入」是兩回事；獨立後 `aos::agent` 公開 API 直接用 `aos::tool::Spec`，agent 不必再自己定義工具型別。`core/CMakeLists.txt` 把 `tool` 排在 `agent` 之前 |
| 2 | 登記項 JSON **扁平**，不用 `registry.md` 範例的 `exec`／`model`／`meta` 三層 | 裁決 3「欄位名照 ai_core 九軸原樣」直接壓過 F3 的分層建議（規劃檔與裁決衝突，以裁決為準） |
| 3 | `.aos/contacts.json` 頂層是**陣列**，不是 `contacts.md` 的 `{"contacts":[…]}` | 交接書寫 `[{"name","folder"}]`，交接書是唯一契約 |
| 4 | 「下一回合要接著想」用 **`history` 末項是 `tool` 訊息**當觸發，不加新欄位 | 驗收 5 要求錯誤退回後模型會再想。不動 `pending.json` schema，順便讓中斷後重跑能接上 |
| 5 | `aos say --to <名字>` **做了**（交接書說「便宜就順手」） | 只是查通訊錄 → 解相對路徑 → 呼叫既有的 `say()`，十幾行 |
| 6 | `aos tool` 只做 `add`／`ls`／`rm`，**不做** `registry.md` 建議的 `probe` 子命令 | 最小原型；`add` 本來就會探測並把結果印出來 |
| 7 | 登記項的 `stdin` 欄位**存而不用**；`timeout_ms` 為 0 時 agent 投遞仍用 30000 ms | 邊緣狀況跳過，欄位先留位 |
| 8 | 未知工具連續錯下去會每回合燒一次 LLM，**不設上限** | 邊緣狀況，原型先不管；要管就是加重試預算 |

## 沒做的（留給下一棒）

- `aos tool export --format openai|mcp`、`aos llm --tools` 原生 tool calling（裁決 8 說「實測後再升」）。
- 多工具並行（末行 JSON array 投 `-0,-1…`）、`stdin` 消費、`exit_codes` 自動重投、危險工具 `confirm`。
- pi 事件回填 `batch/`（裁決 11 已明示先接受這個洞）。
