← [入口](../02-設計.md)｜涵蓋：agent 定義表、確定性工具表、shell→專屬三階段、四個確定性數字｜上一份 [01-庫](01-庫.md)｜下一份 [03-kernel與git](03-kernel與git.md)

# 窄領域 agent 分工樹與工具樹（結論）

原則（使用者 11-07）：領域越窄→能工具化的越多→模型越便宜。所以先問「這步要不要腦」，不要腦的一律腳本。

## agent 定義（都從 `templates/agent-fsm` 複製，只改 `system.txt`、`tools.json`、`llm.json`）

| 定義（`~/code/playground-ak/agents/`） | 腦 | 做一件事 | 工具（第一輪） | 輪 |
|---|---|---|---|---|
| `writer-places` | gpt-luna-low | 收一封信「讀 A 寫到 B」，讀 `lore/places/A.md`，照 01 的節點格式寫 `kb-ak/ak/places/B.md`，回「done B」或「skip 原因」 | read、write、memory、bash（記錄用）、clock | 1 |
| `writer-factions`、`writer-characters`、`writer-operators`… | gpt-luna-low | 同上，一類一隻；characters 多一條「超 2 KB 就寫成資料夾＋子節」 | 同上＋`ak_src` | 2～3 |
| `reviewer` | gpt-sol-low | 收一封信「審 B」，對照 `sources:` 的原文行，答 `ok`／`reject 理由`（寫進 `work/rejects.md` 由腳本做） | read、memory、`ak_src` | 2 |
| `merger` | gpt-sol-low | 把同一人的 characters／deep_dive／relationship_map 三節融成一節 | memory、memory_write、`ak_src` | 4 |
| `writer-local` | lm-／ollama 小模型 | 跟 `writer-places` 同定義、換腦，比確定性 | 同 writer | 3 |

- 每隻一次只做一封信、做完 idle；批次腳本一次 `say` 多封（luna 便宜、slots 管並發）。
- 子 agent：第一輪不開 `agents` 工具（`max_children: 0`）——窄領域不需要生子；要並行＝多掛幾隻同定義（`aos-agent ctl add --name writer-places-2 …`）。
- `thought` 工具第二輪給 reviewer（「去原文查這句是否成立」一次性 helper，不污染 history）。

## 確定性工具（腳本，無 LLM；放 `~/code/playground-ak/defs/<name>/`，資料夾＝程式：`_entry`＋`_tooldef.json`＋`README.md`）

| 工具 | 做什麼 | 誰叫 |
|---|---|---|
| `ak_slug` | `<class> <zh>` → slug（查 `names.tsv`；沒命中退 `NameMissing`） | batch.py |
| `batch.py`（指令，不是 agent 工具） | 列下一批（`lore/<class>/` 裡還沒有對應節點的檔）、算路徑、逐封 `aos-agent say`、`listen` 收齊、寫 `work/batches/<n>.json` | 隊長／cron |
| `kb_lint` | 掃 `kb-ak/ak/`：段名、第 1 行 `# `、第 2 行摘要、≤ 2 KB、`[[…]]` 目標存在、`sources:` 路徑存在；印 `path: code` 行、退 0／1 | batch.py（commit 前閘）、agent（第二輪起當工具自檢） |
| `kb_split` | 超 2 KB 的葉→資料夾＋子節（按 `## ` 切） | batch.py |
| `kb_dedupe` | sha256 整檔重複、同 slug 不同類 | batch.py |
| `kb_index` | 生 `ak/index/aliases.json`（標題中文、別名→路徑） | batch.py |
| `ak_src` | `{"path", "lines"?}` 讀 `ws/corpus/` 一段（取代 bash `sed -n`／`grep`） | writer、reviewer（第二輪） |
| `tool_stats.py` | 從 `ws/.stack/procs/*/history` 抽 bash 指令、算首字頻次 top 10 | round_report.py |
| `round_report.py` | 一輪報告：stopped 原因、lint 錯誤類型頻次、bash top 10、人工次數、token／節點、重跑 diff 率 | 隊長 |
| `watch.sh` | 每 30 s 記 load、mem%、aos proc 數到 `run/watch.log`；超 80% 印一行 | 隊長 |

## shell → 謹慎 → 全專屬（三階段，使用者原話）

| 階段 | bash 給不給 | 怎麼收 |
|---|---|---|
| 1（第一輪） | 給，不限（範本 `lib/base/bash`），但 system.txt 說「prefer read/write」 | `tool_stats.py` 列 bash 指令 top 10 → 每個出現 ≥ 5 次的動作提案成專屬工具（`ak_src` 預期第一個） |
| 2（第二輪） | bash 的 `_metainfo.json` 加白名單（只准 `grep`、`sed -n`、`wc`）或改掛 `defs/bash_ro`（唯讀包裝） | 再一次 top 10；剩下的收完 |
| 3（第三輪起） | `tools.json` 拔掉 bash | 新需求＝新專屬工具，不再回頭開 shell |

## 確定性怎麼量（每輪四個數，寫 `runs/<n>/stats.json`＋[得失](../得失.md)）

1. **重跑 diff 率**：同一批輸入跑兩次（第二次寫到 `kb-ak-rerun/`），`kb_lint --diff A B` 逐節點比（去掉空白後相同）→ 相同數／總數。目標第一輪 ≥ 80%，之後每輪 ≥ 上輪。
2. **lint 首次通過率**：writer 寫完、未經修的節點 lint 退 0 的比例。
3. **人工次數**：reviewer 退件數＋隊長手改檔數＋agent `stopped` 要人起的次數。
4. **token／節點**：隊 kernel `used.json` 的 tokens ÷ 本輪節點數（K1 做完才準）。

哪個數變差＝下一輪提案要改的目標（03 的演化迴圈以此為輸入）。
