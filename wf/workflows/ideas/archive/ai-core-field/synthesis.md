> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# synthesis — 三份采風的合成（2026-08-30，隊 T）

← [ai-core-field](README.md)｜規劃成品 [ideas/tools](../tools/README.md)

只合成 F1／F2／F3 的 ③④⑤ 段；每列都標出處（F1 ③2＝f1-origin.md 第 ③ 段第 2 條）。
術語：ai_core 的 `nondeterministic` 軸在 aos 一律改稱**可預期性**（`predictability`，「結果是否符合人類預期」，不是「同輸入同輸出」）——見對照表第 3 列。

## 一、起源對照表

| ai_core 主張 | aos 現況 | 差距（→ 落點） | 出處 |
|---|---|---|---|
| 工具必須 `--metadata`／`--metainfo` 自述 | `tools.json` 只有 `name/description/argv`，程式不自述 | 登記表要能**代答**，自述是加分不是門票 → registry | F1 ③1–2、F2 ③3、F3 ③3 |
| CLI＝Lisp 呼叫，argv 是 list | `{args}` 單字串代入，只有 `sh -lc` 吃得下 | 登記表是全系統唯一把 list 壓回字串的地方 → description | F1 ⑤ cli_spec、F2 ③1 |
| LLM 留白要宣告 nondeterministic、憑證准入、可撤 | `aos llm` 與 `ls` 同級、無任何標記 | 改名為**可預期性**：語意從「同輸入同輸出」變「符合人類預期」，證書那層先不做 → registry | F1 ①b、③3、④3；F3 ④ meta |
| 世界持有 tool；個體的 `.json` 只記「我能用哪些」 | `tools.json` 住 `agents/<name>/`，`init` 硬寫三項 | 搬到世界層，agent 的檔退成白名單（三隊一致） | F1 ④6、F2 ③2 ④、F3 ④ |
| 錯誤分類＋`retryable`；缺口要變成動作 | exit 只有 0/1；未知工具靜默忽略 | 結構化退回一則 tool 訊息 → call-loop | F2 ③5、F3 ③1–2 |
| Hub 匯出 MCP／OpenAI tools；tool calling 最通用 | 末行 JSON 自訂協定，`aos llm` 無 `--tools` | 表述分兩份：模型一行、機器 JSON；匯出照映射表 → description | F1 ④5 ⑤ doc_13、F3 ③4 |
| trace＝固化飛輪的礦；append-only | `batch/<turn>/` 帳本存在，但 pi 的工具動作繞過 | pi 事件回填 `batch/` → call-loop | F1 ③6–7、F3 ③5 |
| lifecycle 只有 one_shot／persistent | 回合內只跑 one_shot，persistent 靠 `every/` 模擬 | 登記 `lifecycle: persistent` 的程式不當回合內 tool | F1 ③4、F2 ④ traits |
| PATH 交給 shell，指定資料夾下的才登記 | default tools 就是 `sh/ls/cat` | **不掃 PATH**；`aos tool add` 逐個登記 | F2 ① 08-06、④3 |
| 大內容走路徑（entries＝filepath）、stdout 有多種模式 | stdout/stderr 整段內嵌 `out/<id>.json` | 先不做，記在登記表 `stdout` 欄留位 | F2 ③6、F3 ④ exec.stdout |
| env 白名單、fail-closed | env 只加不減 | 登記項可選 `env_allow` | F1 ③5、④7 |

## 二、三隊在登記表形狀上的分歧與相容點

| | F1（起源） | F2（handy） | F3（cllm） |
|---|---|---|---|
| 住哪 | 世界層單檔 `.aos/tools.json` | 一資料夾一 tool `.aos/tools/<name>/{tool.json,metainfo.json,help.txt}` | 一檔一 tool `.aos/tools/<name>.json`（與 inbox 同款） |
| 欄位命名 | 照 ai_core 九軸子集，不另創詞 | `args: list\|string\|none`、`stdin`、`source`、`traits` | 兩層 `exec`／`model`＋`meta`（`exit_codes.retryable`、`stdout` 模式、`stage`） |
| 來源 | registry 覆寫 > 自述 > 預設 | 三級降級：自述 JSON → 檔頭第一行 → 手填 | aos 子命令自述、第三方手寫 |
| loop 現在只消費 | `guarantee`／`state`／`resources.time` | `lifecycle: persistent` 拒收、`interruptible` 決定 SIGTERM | `exit_codes.retryable`、`timeout_ms` |
| args 形狀 | 沿用 `{args}`，之後升 positionals＋flags | **list 逐項接在固定前綴後**，`string` 只留給 `sh` | 具名槽 `{param}` 對應 `parameters` |

**相容點（可直接定案的底）**：世界層、agent 檔退白名單、`name/argv/description` 必填、自述可選不強制、LLM 類工具要標記、loop 只消費少數欄位其餘先存不用、不回頭抄 tooljson。
**真分歧（要拍板）**：檔案粒度（1 檔／N 檔／N 資料夾）；args 是 list 還是具名槽；欄位名跟 ai_core 還是自創；LLM 類標記是一欄布林還是 `meta` 四欄。

## 三、值得抄的交集（三隊至少兩隊點名）

| ai_core 路徑 | 抄什麼 | 點名 |
|---|---|---|
| `spec/lib_spec/register-intercept-lifecycle-state.md`＋`handy/util/metainfo/README.md` | 自述攔截規則：`prog [sub] --metadata` 純 JSON、宣告不執行、排在驗證前退出 0 | F1 ⑤、F2 ⑤ |
| `handy/try_impl/metainfo.md`＋`spec/lib_spec/s6-guarantee.md` | 最小／標準兩級＋`guarantee`——降級登記與「能不能自動重跑」的依據 | F1 ⑤、F2 ⑤ |
| `spec/cli_spec.md` §2.0＋`handy/try_0802/sh.janet` | argv＝list、旗標＝keyword；`@{:cmd :status :out :err}` 結果封套 | F1 ⑤、F2 ⑤ |
| `docs/kb/kb-ss/doc_13_arch_hub.md`＋`kb-ext/ext_04_interoperability_mcp.md` §2 | `aos tool ls/export` 的功能規格與欄位映射表 | F1 ⑤、F3 ③4 |
| `cllm/core/workflows/common/gotchas/backend.md`＋`handy/try/v1/README.md` | 「fixture 只投影成功」「prompt 說過不等於模型會做」——結構化退回的實證依據 | F2 ⑤、F3 ⑤ |
| `docs/kb/knowledge_base/code_02_prototype_tools.md` | 錯誤封套 `type`＋`retryable` | F1 ③6、F3 ⑤ |
| `handy/notes/2026-08-06.md` | 使用者最新 tool 觀：翻譯器、PATH vs 指定資料夾、`.json` 記 tool 與權限、複製人四級 | F2 ⑤（F1 ④8 同向） |

**不抄**（兩隊以上明講）：tooljson 的 OpenAI schema＋position/flag 綁定（F2 ④、F3 ③8 同判）；C ABI、daemon／RateMeter（F3 ③8）；`recovery.json` 工具級恢復、`resources` 細欄位（F1 ⑤）；組合模式／環境模式進 metadata（F1 ④2）。
