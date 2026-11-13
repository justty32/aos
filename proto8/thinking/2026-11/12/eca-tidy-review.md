# eca_tidy 產出抽查結果（11-12 晚）：產出可以用、命中約九成；十條值得處理的發現還沒修，等使用者說修哪些

← [11-12 日索引](README.md)｜[2026-11](../README.md)｜來源 [playground-home § eca_tidy](playground-home.md#用-eca-唯讀整理-proto8eca_tidy11-12-21302134)

## 使用者原文

- 「喔他那個已經跑好了，有out」（11-12 晚，逐字）

## 結論

**這批產出可以用。** 頂層派 opus 唯讀抽查（11-12 晚），抽查約 22 條具體敘述，對照快照 `026210d4a`：完全對 20 條、半對 1 條、數字小偏差 1 條。最有價值的是幾條指出文件跟程式對不上的發現，wf 裡都沒記過；thinking 那部分大半在核對 README 份數與狀態標記，用處較小。它守住了唯讀。

產出在 `~/code/playground/tidy/out/`（不在 repo 裡）：`proto8-top-level.md`（英文，2 KB）、`survey/A～E`、`thinking/`（README、index 三份、findings 三份）、`index/README.md`，共 14 份約 186 KB，除頂層那份外都是繁體中文。

錯得最明顯的一條：C-impls H1 說 `impls/build/` 沒被 .gitignore 蓋到；其實 repo 根 `.gitignore` 第 1 行 `build/` 就蓋到了，只有 `build-asan/` 真的沒蓋（它看不到根目錄、自己有註明，但仍列成「高」）。數字小偏差：11-04 它說 9 個題目，合併同名檔與夾是 8。

## 表現

- `tidy/` 下除 `out/` 外沒有檔比 `SNAPSHOT.txt` 新。
- 開了 8 個子 agent 分區做；使用者中途說「先做 thinking、別做今天的」它就改範圍。
- 子 agent 存 findings 被 Claude Code 內建規則擋下、由主 agent 代存並在檔頭標明。
- 沒有 shell，所以沒全量查連結、沒 build、沒跑測試。
- 預告的 `out/SUMMARY.md` 沒產出。

## 最值得看的十條

出處路徑在 `~/code/playground/tidy/out/` 底下；抽查的幾條在 11-12 晚的 main 上仍沒修。

| # | 白話 | 出處 |
|---|---|---|
| 1 | 知識樹正文大約 66 處指標穿過 `$ref`，agent 用 `json_get` 讀會撞 `PointerMissing`，而會跟 `$ref` 走的 `jsonx` 工具範本都沒掛 | `survey/B-knowledge.md:24` |
| 2 | 知識樹說 `self_state` 有 10 個 parts，程式有 11 個（多了 `system`），同一棵樹裡的 `cli/agent.json` 也寫 11 個 | `survey/B-knowledge.md:65` |
| 3 | 範本 judge-llm 預設的 endpoint `judge` 在 llm-kernel 的 `kernel.json` 裡沒有，兩個範本直接搭配會失敗 | `survey/E-kernel-templates-misc.md:79` |
| 4 | `aos-mcp-launch` 不走 `aos_flags`，啟動失敗時錯誤行會進 stdout，而 stdout 是 MCP 協定通道（只影響啟動那一刻，抽查者推測實害不大） | `survey/D-cmd-py-lib.md:23` |
| 5 | `kernel/docs/01`、`02` 還教人用相對 lib 路徑和 `sed` 改，實際早已改成 `$AOS_HOME` | `survey/E-kernel-templates-misc.md:27` |
| 6 | `aos-daemon/README.md:36` 說旗標放在設定檔後面會報錯，程式從 11-11 起已經收了 | `survey/C-impls.md:42` |
| 7 | 頂層 README 的條號範圍還停在 C-73、P-41，cmd 清單少 `aos-mcp-launch`、`aos-mcp-import`，資料夾表沒有 `feedback/` | `survey/A-docs-thinking-notes.md:22`、`survey/D-cmd-py-lib.md:17`、`survey/E-kernel-templates-misc.md:16` |
| 8 | `feedback/*.jsonl` 每筆都帶家目錄絕對路徑並進了 git，跟「家目錄、帳號名算外洩」的政策矛盾；`gitignore-check/check.py:187`、`templates/tests/test_daily.py:31` 寫死含帳號名的 `/mnt/c` 路徑 | `survey/E-kernel-templates-misc.md:36` |
| 9 | thinking 月表份數與排序錯（11-04 排在 11-05 後；份數寫 6／15／2 與 11／1／1／1／2，實際 9／16／12 與 12／6／5／16／16），11-04、11-10 日 README 漏列五個題目（aos-agent、four-elements、eca-claude-dir；self-tools、sweeper） | `thinking/findings-2026-11b.md:28`、`thinking/findings-2026-11a.md:32` |
| 10 | 已被推翻的決定原處沒標作廢：月 README 的 N-45 說法跟現行條文相反；`os-concepts` 還寫「C-76／N-65 暫稱」（實際落成 C-83／N-67）；C-86、C-89～C-92 在來源夾沒回標條號 | `thinking/findings-2026-10.md:15`、`thinking/findings-2026-11a.md:41`、`thinking/findings-2026-11b.md:48` |

## 已知或半已知

- 「agent 不知道知識樹在哪」：[ops-notes-to-aos](ops-notes-to-aos.md) 已寫。
- 「指標不穿過 `$ref`」原則在 [ref-index-unify](ref-index-unify.md) 講過，但上面第 1 條的實際後果沒記。

## 未定

- 十條修了九條（下節）；第 8 條使用者選項框選「明天再說」；第 1 條留下「範本要不要掛 `jsonx`」甲乙丙一題待裁（見下節第 1 條末）。
- **第 8 條裁定（11-13）＝選 A：把路徑改成不含家目錄的寫法（例如相對路徑），寫死的兩處改讀環境變數。** 使用者回覆原文：「eca-8:A*」（11-13 待裁頁 `wu-1113-top`；回覆整行見[回覆檔](../13/decide_20261113_wu-top.reply.txt)，裁定後待施工見[裁定落地-1113](../13/裁定落地-1113.md)）。還沒施工。
- **第 1 條剩的那題裁定（11-13）＝選 A（甲）：範本掛 `jsonx` 工具。** 使用者回覆原文：「eca-1:A*」（出處同上）。還沒施工。

## 修了哪些（11-12 晚）

- 第 9 條：已修。[2026-11 月表](../README.md) 11-04 移到 11-05 前；份數照日 README 列數改成 04＝9、05＝16、06＝12、07＝12、08＝6、09＝5、10＝16、11＝16、12＝34（11-12 仍在寫，以修時為準）；[thinking/README](../../README.md) 2026-11 那列改成 142 份、11-01～11-12；11-04 日 README 補列 aos-agent、four-elements、eca-claude-dir，11-10 補列 self-tools、sweeper；其他日 README 逐夾掃過，沒有別的漏列。2026-10 月表份數本來就對。月表 11-06～11-11 那幾列的一句話只講到一兩個題目，沒改。
- 第 10 條：已修。2026-10 月表與 10-15 日 README 的「沒有指示詞可用（N-45）」改成以現行 N-45 為準（`$env`、`$ref`，`$ref` 可帶 `$at`）；os-concepts README 與其 10 號檔的「C-76／N-65 暫稱」標上已落成 C-83／N-67（草稿本文不動）；C-86、C-89～C-92 在來源夾（10 tonight-rulings、10 aos-tools-cli、07 agent-diversity、10 self-family、11 goal）的 README 導覽列補「條文：」連結。
- 另：`2026-11/08/alt-fable/out2/v4.md` 全文只有一行用量上限錯誤，使用者「廢檔可以刪。」已刪（`93bd79289`）。
- 第 2 條：已修。`knowledge/aos/me.json` 的 `self_state` 段「The ten parts」改成 eleven、列舉補上 `system`（以 `cli/agent.json` 與 `aos-agent ctl state` 的 11 個為準）。
- 第 3 條：已修。使用者 11-12 晚選項框答覆：問「預設值要怎麼辦」選「kernel.json 加一個 judge」，問「judge 指到哪個模型」選「同 smart-high（haiku）」。`kernel/llm-kernel/kernel.json` 的 `endpoints` 加 `judge`（設定照抄 `smart-high`，summary 註明給 judge-llm 範本用）；`templates/judge-llm/README.md` 改成出廠已有 `judge`、直接搭就能跑、換模型改 kernel.json 那格；`kernel/docs/01` 能力包表補 `judge` 一列、LiteLLM 包共用數改五個；`impls/aos-llm-kernel/docs/01` 的「範本三個 LiteLLM 包」改成不寫數。judge.json 預設不變。
- 第 4 條：已修。`cmd/aos-mcp-launch` 四處 `tool_io.die` 加 `echo=False`，錯誤行只走 stderr；`lib/agent/tests/test_cli_external_mcp.py` 原有的 PackBad／ArgumentsBad 兩處補 stdout 為空的斷言，另加一例 CommandMissing。
- 第 5 條：已修。`kernel/docs/01` 的檔案樹與起來步驟改成 `$AOS_HOME` 指示詞（拿掉兩行 `sed`，改成先 `export AOS_HOME=<repo>/proto8`；LiteLLM 包共用數改成四個）；`02` 的「改成自己的」改說判官路徑是 `AOS_HOME` 指示詞、搬出 repo 不用改，跑法開頭補 `export AOS_HOME`。
- 第 6 條：已修。`impls/aos-daemon/README.md` 改成旗標放設定檔後面也收（11-11 起，見 aos-loop `config.cpp` loop_cli），多給位置參數才 `ArgumentsBad`。只改 README。
- 第 7 條：已修。`proto8/README.md` 條號改 C-01～C-92、P-05～P-48（兩處 C、一處 P），cmd 清單補 aos-mcp-launch、aos-mcp-import，資料夾表加 `feedback/`。
- 第 1 條：正文部分已修，範本掛 `jsonx` 沒動（設計選擇）。對 11-12 晚的 main 實測（掃 `knowledge/` 全部 `.json`、`.md` 裡的 `aos/….json#/…`，逐一不跟 `$ref` 走）：315 條指標，穿過 `$ref` 的 68 條，只有一種型態——走到 `aos/me.json`、`agents.json`、`errors.json` 根上那 9 個 `{"$ref": "子夾/x.json"}` 之一再往下（`#/self_hook/…` 等）。其中 66 條在 `aos/` 正文（32 個檔，`tools/*.json` errors 段 41 條、拆出去的那 9 份檔 19 條（18 條指自己）、`mailbox`／`clock`／`agents`／`cli/hook` 6 條），一律改成指到被 `$ref` 的那份檔：`aos/me.json#/self_hook/handler` → `aos/me/self_hook.json#/handler`、`aos/errors.json#/common/files` → `aos/errors/common.json#/files`，以此類推（合「指標不穿過 `$ref`」定案、樹裡照舊寫 `aos/…` 路徑）；改完重掃 0 條穿過，改後的 16 個不同指標用 `aos-json get`（不加 `--follow`）逐一讀得到。剩 2 條是 `README.md`、`docs/01` 示範 `--follow` 的那行，刻意留著；另有 `docs/01` 一條 `aos/packs.json#/look/_index` 是假設例子、本來就指不到，沒動。沒改 `aos/me.json`（`self_state` 那段另一個 agent 在改，該檔沒有穿過的指標）。沒動的設計題：(甲) 範本掛 `jsonx`——agent 能直接讀穿過的路徑，但多一組工具、小模型要分 `json_get`／`jsonx_get`；(乙) `_description.json` 加一句「讀到 `{"$ref": …}` 就去讀那份檔」——不加工具，日後新寫的穿過指標仍會壞；(丙) 什麼都不加、靠 wf-lint 類的檢查擋穿過指標——今晚這種回歸能抓到，但 agent 讀到別處（非出廠）的 `$ref` 仍得自己跟。給使用者定。測試（空暫存目錄起跑）：`templates/tests/test_paths_move.py` OK、`test_daily.py` 16 支 OK（2 skip、2 預期失敗）、`lib/tests/test_*.py` 15 檔全 OK。
