# 任務：把 tool 登記表與 agent 通訊錄做進 aos（`.aos/tools/*.json`、`aos tool`、`aos contact`）

> 交接書是唯一契約。規劃與**使用者 12 條裁決**在 [ideas/tools/README](../../ideas/tools/README.md)（裁決段**壓過**規劃檔裡的建議），細節在同資料夾 `registry.md`／`description.md`／`call-loop.md`／`contacts.md`；協定 [PROTOCOL](PROTOCOL.md)；現況 `core/agent/src/tools.cpp`、`step.cpp`、`core/agent/README.md`。

## 背景與唯一目標

tool＝任何 POSIX 可呼叫的程式；要有登記列表與表述。**唯一目標**：agent 的工具從 agent 層 `tools.json` 改成世界層 `.aos/tools/<name>.json`（欄位照 ai_core 九軸、必填三欄、`args` 依登記 `list|string|none`），`aos tool add/ls/rm` 可登記（含 `--metainfo` 探測），LLM 看到精簡文字行、呼叫錯誤以固定 JSON 退回；另加 `.aos/contacts.json`＋`aos contact add/ls/rm`。最小原型、邊緣狀況跳過。

## 團隊（你是 Opus 隊長）

工作量押給 codex（`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；sol／terra／luna 皆可，最多 4 條、量力而為）。建議：① registry 讀寫＋`aos tool` CLI（含 `--metainfo` 探測與三級降級）；② `step.cpp`／`tools.cpp` 改走新登記表、表述行、args 形狀、錯誤 JSON 退回；③ `contacts.json`＋`aos contact` CLI；④ 測試＋README＋code map＋`.gitignore` 例外（`!.aos/tools/`、`!.aos/contacts.json`）。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。**直接在 main working tree 做**（沒有別隊同時碰 core/）。

## 工作

1. 讀上面列的規劃檔與裁決表；有規劃檔與裁決衝突處**以裁決為準**，記進隊長裁決。
2. `core/agent`（或新小專案 `core/tool`，你裁——判準：`aos tool`／`aos contact` 是否該獨立成小專案；獨立的話 agent 相依它）：
   - 登記項 JSON：九軸欄位名照 ai_core（`registry.md` 有範例；`predictability` 取代 nondeterministic），必填 `name`／`argv`／`description`，選填 `args: list|string|none`（預設 list）、`stdin`、`cwd`、`timeout_ms`、其餘九軸欄位。
   - `aos tool add <name> [--description …] -- <argv…>`：先跑 `<argv> --metainfo` 探測（JSON → 直接取；非 JSON → 取第一行當 description；失敗 → 只用手填），寫 `.aos/tools/<name>.json`；`ls`（給人看的表）；`rm`。`--metadata` 只在 `--probe metadata` 時試。
   - `aos agent init` 改成：若 `.aos/tools/` 空就預設登記 `sh`（string）、`ls`、`cat`（list）；agent 層 `tools.json` 退成**白名單**（存在就過濾，不存在＝全部）。
   - `step`：表述＝每個 tool 一行 `name — description (args: list|string|none, stdin: …)`；呼叫格式 `{"tool":"…","args":[…]|"…"}`；client 驗證（未知工具／型別不符）→ 下一回合以固定 JSON tool 訊息退回 LLM（形狀照 `call-loop.md`）。三回合往返不動。
   - `.aos/contacts.json`：`[{"name","folder"}]` 最少兩欄（可加 `note`）；`aos contact add <name> <folder>`／`ls`／`rm`；`agent init` **不碰**它。`aos say --to <name> …` 若便宜就順手做（往通訊錄那個資料夾投 say），不便宜就不做、記裁決。
3. engine=pi 的路徑不動（裁決 11）。
4. `.gitignore` 加 `!.aos/tools/`、`!.aos/contacts.json`；本 repo 根的 `.aos/tools/` 順手登記 `sh`／`ls`／`cat`／`git`／`aos` 五項當範例並 commit。
5. 測試（登記讀寫、探測降級、args 三形狀、錯誤退回、contacts 增刪）不 sleep、不連外；README、code map。
6. commit 到 main。

## 硬性限制

- **禁區**：`core/exec`、`core/wire`、`core/loop`、`core/llm`、`core/tick`（只讀）、`reference/`、`app/`、`wf/` 除 code-map、本資料夾、`ideas/tools/`（只可追加「實作註記」）之外。
- `git add` 只加明確路徑（working tree 有使用者未提交的 wf 改動）；不 push；不取鎖、不開 GUI、不 load／unload LM Studio、不用 wf-lint（有 bug）。
- 邊緣狀況跳過；小裁決記「隊長裁決」；只有裁決表自相矛盾才 BLOCKED。

## 交付

| 產物 | 路徑 |
|---|---|
| 登記表與 CLI | `core/agent/`（或 `core/tool/`） |
| 範例登記 | `.aos/tools/*.json`、`.gitignore` |
| 回報 | `wf/workflows/dispatch/proto/reports/U.md` |

## 驗收（就這 6 條）

1. build＋ctest 全綠。
2. 空資料夾 `W`：`aos tool add echo -- echo` → `.aos/tools/echo.json` 有 `name/argv/description`；`aos tool add fake -- ./fake-metainfo.sh`（測試用腳本回一段 JSON）→ description 來自 `--metainfo`。
3. `aos agent init` → `.aos/tools/` 有 `sh`／`ls`／`cat` 三檔；`aos agent state` 正常。
4. `aos say "列出目前資料夾的檔案"` → 跑 3 回合（真 LM Studio）→ log.md 出現 `{"tool":"ls","args":[…]}` 形式的呼叫與結果引用。
5. 手動投一條 `{"tool":"nope","args":[]}` 的假回覆（用測試接縫）→ 下一回合 history 出現固定 JSON 錯誤退回訊息。
6. `aos contact add bob ../bob && aos contact ls` 列出；`.aos/contacts.json` 可被 `python3 -m json.tool` 解析；本 repo 根 `git status` 顯示 `.aos/tools/` 已追蹤。

## 回報

最後一則訊息＝ `reports/U.md` 摘要（≤ 30 行）＋STATUS。

## 隊長裁決

（隊長追加）
