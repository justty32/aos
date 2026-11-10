# 02 施工結果 — memory 改名 memory_read、沒有預設庫根、出廠根上移到 knowledge/（11-10 深夜）

← [tool-packs](README.md)

**結論**：記憶庫工具改叫 `memory_read`（`lib/agent/memory_read`），四支 `memory_*` 都**沒有內建預設位置**——叫的人自己給（命令列 `--root DIR`＞工具夾的 `_memory.json`＞`AOS_MEMORY`），都沒給＝`MemoryMissing`、給了不是資料夾＝`MemoryBad`。出廠庫的根上移成 `knowledge/`（新的根表列 `aos/`），範本指這層；節點裡的路徑都改成 `aos/…`。腦（brain.py）與 aos-mcp 遇到「沒給庫」安靜跳過，不吵。gemma 只看根表，12 次第一步都往 `aos/` 走、11 次答對。

## 改了什麼

| 處 | 改法 |
|---|---|
| 工具 | `git mv lib/agent/memory lib/agent/memory_read`；help、錯誤前綴、README、測試跟著改；memory_write／export／sync 說明裡的「memory tool」改 `memory_read` |
| 找根（`lib/agent/memory_fs.py`） | 新 `take_root_flag`：在 tool_io 之前拿走 `--root DIR`／`--root=DIR`（沒值、給兩次＝`ArgumentsBad`）；`memory_root` 優先序 `--root`（相對從 `$AOS_WS`）＞`_memory.json`＞`AOS_MEMORY`；都沒有＝`MemoryMissing`（訊息列三種給法）；不是資料夾＝`MemoryBad`（新代號，四份 tooldef 的 errors 都登記） |
| 15 份 tooldef | `Details: memory X` → `Details: memory_read aos/X` |
| 出廠庫 | 新 `knowledge/_index.json`（`aos/`、`README.md`、`docs/`，後兩格標「給人看、中文、agent 可略」）與 `knowledge/_description.json`（叫 agent 先讀 `aos/`）；`knowledge/aos` 15 份檔的節點文字路徑加 `aos/`、工具名換 `memory_read`（都經 memory_write `--root knowledge` 寫） |
| 範本 | brain.py 與 eca `cli.json` 改 `--memory memory_read`；`tools.json` 兩格 env 指 `{"$env":"AOS_HOME","$path":"/knowledge"}`（tools.json 改由隊長的分包施工一起 commit）；兩份範本 README 加「知識庫指 knowledge/ 這一層」與改指法 |
| brain.py | 工具 stderr 改用管子收；最後一行是 `MemoryMissing` 且退 1＝開場不帶知識、不印、不轉印；其他錯誤照轉印 stderr |
| aos-mcp | 同樣：MemoryMissing 安靜回 None（不給 instructions），其他錯誤照印尾巴 |
| 其他 | kernel fake-demo-memory 劇本（已隨 a5f6626ee 進）、gitignore-check、aos-feedback 範例與測試、agent_def 測試、knowledge README 與 docs/01／02、lib README 與 docs/01／03、proto8 README、templates README 與 docs/01／02、附錄3 舊名列、附錄4、C-42 續與 P-46 註 |

## 驗收（scratchpad/memory/accept，只動 scratch 庫）

- 沒給根：`memory_read: error: MemoryMissing no memory root was given; the tool has no default; give one: --root DIR …`，退 1。
- 指到不存在的夾：`MemoryBad AOS_MEMORY resolves to …/nope, which is not a directory`。
- 指 scratch 庫：memory_write add `notes.json` → memory_read 讀 `notes.json#/a`＝1；`--root` 給同一夾 ls 列得到。
- 指出廠 `knowledge/`：ls 根列 `aos/`、`README.md`、`docs/`；read `aos/errors.json#/codes` 正常。
- 腦安靜：`templates/tests/agent-fsm/test_selfheal.py` 新 `test_no_knowledge_base_given_is_quiet`；aos-mcp 新 `tests/test_memory_root.py`（給了＝有 instructions、沒給＝安靜、不是資料夾＝warning）。
- 單元：四支 memory_* 測試、aos-mcp、aos-feedback、lib/aos/defs、review_round、cmd/aos-eca、`templates/tests/agent-fsm`（57 支）、`templates/tests/test_daily.py`（16 支，2 skip、2 預期失敗）綠。

<details><summary>gemma 實測：開場只帶根表夠不夠</summary>

LM Studio google/gemma-4-e4b，system＝範本 system.txt＋memory_read 印的根（只有 `knowledge/` 那層的表與簡介，不加 aos 簡介），三題各 4 次（錯誤代號是什麼意思、怎麼加工具、怎麼寄信）：

- 第一次叫 memory_read 的路徑：12／12 帶 `aos/`（`ls aos/` 或 `find` 在 `aos/`）。
- 答對：11／12（唯一錯的是「怎麼加工具」一次直接 find `add tool` 沒命中就答）。

所以 brain 開場只帶根就好，不另加 aos 簡介（代定）。腳本 `scratchpad/memory/gemma_probe.py`，不進 repo。

</details>

<details><summary>代定（可翻案）</summary>

- `--root` 只在命令列；登記格（tools.json）不帶 argv（`aos-tools call` 是 `aos-exec 路徑`），所以 agent 用時一律靠 env 或 `_memory.json`。
- 優先序 `--root`＞`_memory.json`＞`AOS_MEMORY`；`--root` 相對從 `$AOS_WS`（沒設＝cwd）。
- 新代號 `MemoryBad`（給了但不是資料夾）；沒給才是 `MemoryMissing`。
- 根表也登記 `README.md` 與 `docs/`（標給人看），agent ls 根時看得到但知道可略。
- brain／aos-mcp 的 `--memory` 只是登記名；腦開場只帶根（見上）。
- 範本 `memory_write` 也指出廠 `knowledge/`：agent 寫了就改 repo 的知識庫（使用者「指knowledge/」）。

</details>

<details><summary>紅的（不是這條線的範圍）</summary>

`lib/agent/agent_def/tests` 的 `test_copy_real_template_then_check`：

```
defs: error: DefBad 1 definition problems found {"problems": [{"path": ".", "reason": "each tool must declare a path"}]}
```

原因：分包後範本 `tools.json` 的記憶兩格只帶 `env`、path 由 `$override` 的 `lib/packs/memory.json` 補，`defs check` 不先合併 `$override`。已轉給隊長。

</details>

<details><summary>試驗場刷新注意</summary>

- 舊 stack 的覆蓋層或舊定義登記了 `memory`（`lib/agent/memory`）＝PathMissing：整份重抄範本，或 `aos-agent tools reset` 後重加。
- 舊定義的 `AOS_MEMORY` 指 `…/knowledge/aos`：還能讀，但節點裡的路徑現在都寫 `aos/…`，會對不上——改指 `…/knowledge`。
- Claude Code 的 aos MCP 出口設定 `~/.cache/aos-mcp-aos/tools.json`（repo 外）：`aos_kb`、`wf_kb` 的 path 已改成 `lib/agent/memory_read`，`aos_kb` 的 `AOS_MEMORY` 改指 `proto8/knowledge`；重開 MCP 才生效。
- `~/code/playground/llm_kernel/def/kernel.json` 若抄過 fake-demo-memory 劇本，裡面的工具名與路徑要換成 `memory_read`、`aos/me.json#/self_tools`。

</details>
