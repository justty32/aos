← [notes 索引](README.md)｜[工具大開發時代](2026-09-24-tool-era/README.md)｜[plan.md 隊 4](2026-09-24-tool-era/plan.md)

# 第一波第 4 隊：記憶與紀錄（報告）

2026-09-24。做 T-events、T-context、T-compact（機械版＋自動＋申請）、T-notes、`aos-agent history --archive`；另外接上第 1 隊的 `aos-agent init --template`。
規範新檔：[spec/agent/events.md](../spec/agent/events.md)、[spec/agent/compact.md](../spec/agent/compact.md)、[spec/aos-agent/cli-memory.md](../spec/aos-agent/cli-memory.md)；既有規範只加了標「（09-24 第 4 隊補）」的句子。
astra 唯讀審查：任務書 [review-memory-task.md](2026-09-24-tool-era/review-memory-task.md)、結果 [review-memory-astra.md](2026-09-24-tool-era/review-memory-astra.md)。

## 1. 做了什麼（白話）

| 工具 | 一句話 | 程式 |
|---|---|---|
| 事件紀錄 | 每個 agent 家 `log/events.jsonl`：收件、每批開始／結束（成敗、kernel 回音的毫秒）、壓縮；`aos-llm call` 另把端點回的 token 用量寫進 `log/usage.jsonl`，帶批 id 對得起來 | `lib/aos_agent_events.py`；掛在 `aos_agent_batch.py`（送出、收回、結清）、`aos_agent_inputs.py`（收件）、`aos_llm_call.py` |
| `aos-agent context` | 送給模型的東西多大（人格、記憶、工具、合計，token 粗估），`--by-round` 每輪一行、找出最胖的工具結果；有用量紀錄就順便印端點算的真數字。**talk 的 `/context` 改叫同一個函式** | `lib/aos_agent_context.py` |
| `aos-agent compact` | 機械壓縮：舊的輪只留原話＋最後回話，中間換成一行說明；還太大就整輪封存；原文存 `prompts/archive/<sha>.json`。`--dry-run` 不寫任何檔 | `lib/aos_agent_compact.py` |
| 自動壓縮 | `info.json` 加 `"compact": {"max_tokens": X}`：tick 在 idle、沒輸入等著時，在**同一把 tick 鎖**裡直接叫同一個函式 | `aos_agent.py` idle 那一步（4 行） |
| compact 申請 | 模型寄 `kind: "compact"` 的申請 → 郵差叫處理函式 → 投進成員家的 `compact-req/` → 成員下次 idle 時 tick 縮、搬走申請 | `aos_agent_compact.on_request`，登記在 `aos_team_requests.KINDS` |
| `history --archive` | 列 archive、看一份（每則帶編號，跟說明行寫的對得上）、`--grep` 找字 | `aos_agent_compact.archive_main` |
| `events` | 印事件（去重）、`--usage` 印 token 用量 | `aos_agent_events.show` |
| `note` 工具＋`notes ls/show` | 長期筆記（add 同 key 更新／find 關鍵字＋tag／get／rm），存 `wf-table/1` 的 `notes.json`，flock 防同一批平行寫；人用 `aos-agent notes` 看 | `proto5/tools/notes/`、`lib/aos_agent_notes.py`（Sonnet 做的骨架，我改了關牢時的預設路徑） |
| `init --template` | 接第 1 隊的 `init_from_template()`，印它回的幾行 | `aos_agent_cli.py` |

### 鎖與恢復怎麼設計的（這隊最難的地方）

- **誰能寫記憶**：只有持 `.tick.lock` 的一方。人跑 `compact` 自己非阻塞拿鎖，被佔＝退 101、不動檔；tick 本來就持著，自動壓縮**不再拿第二次**（同一個行程對同一檔另開 fd 拿 flock 會被自己擋住，那才是死鎖）。郵差處理申請時**不碰記憶**，只投一個申請檔。
- **只在 idle、沒 batch、沒 intake 時縮**：這時記憶的尾巴一定是完整的一輪，`batch.base_len`、`intake.base_len` 都不會指到被縮掉的位置。
- **每步可重跑**：①讀記憶 bytes、算 sha → ②寫 `archive/<sha>.json`（原樣 bytes，已在就略過）→ ③記事件 → ④暫存檔＋rename 換記憶。永遠不「先搬走舊的」，崩在哪裡記憶檔都是完整的舊版或新版；`plan()` 是純函式、同樣輸入同樣輸出，舊版重跑算出同一份新版；縮過再縮是空轉（不動點）。
- **事件「至少一次」**：每個事件都在提交那一步之前寫，崩了重做會多寫一行同 `ev`＋`id` 的，讀的人去重；不會「做了沒記」。寫不進去只丟那一行，不擋 tick。
- **自動壓縮不空轉**：縮不動（還是超過、或驗不過）就把「記憶 sha＋選項」寫進 `log/compact-skip`，同一份記憶不再每格重算。

## 2. 驗收 8 條

| # | 驗收 | 怎麼證明 | 結果 |
|---|---|---|---|
| ① | `context` 數字與 talk `/context` 一致 | 同一個函式 `aos_agent_context.lines`；`test_context_equals_talk` 比兩邊整段輸出一字不差 | 過 |
| ② | `events.jsonl` 每批起訖與成敗；`usage.jsonl` 真跑有 token | 單元測試 think／act／失敗三種；真跑 deepseek：11 次問模型每次都有 `prompt/completion/total`（§3） | 過 |
| ③ | `compact --dry-run` 不改檔 | `test_dry_run_changes_nothing` 比整棵資料夾的內容＋mtime（連鎖檔都不建）；真跑前後 sha256 一樣 | 過 |
| ④ | 縮完照 §3.2 驗得過、成對、archive 在、低於上限 | `test_compact_valid_archive_under_limit`：`aos_agent_info.load` 驗、`check_pairs`、`aos_llm_call.build_request` 組得起來、archive＝原檔 bytes、token < `--max-tokens` | 過 |
| ⑤ | 還沒 done 的任務那幾輪原樣 | `test_unfinished_task_rounds_kept`：假團隊資料夾，t-0001 working 那輪原樣、t-0002 done 那輪縮了、讀不到的單也留；上限壓到 100 也不封存沒做完的 | 過 |
| ⑥ | 寫 archive 後、換 history 前 KILL，重跑一樣、history 從不缺 | 子行程真的 `SIGKILL` 自己（`_hook('compact.archive')`）：記憶還是原檔 bytes、archive 在；重跑結果＝沒崩的副本；另測 KILL 在換完之後、KILL 在 tick 自動壓縮裡 | 過 |
| ⑦ | 鎖被佔退 101、`batch` 不是 null 拒絕；自動壓縮同一把鎖不死鎖 | 測試拿住 flock → `compact`（含 dry-run）退 101、不動檔；think／有 batch／intake 做到一半 → `NotIdle`；tick 內自動壓縮（同行程、另開子行程各一條）退 0 且縮了 | 過 |
| ⑧ | 真模型壓縮後再問一句，回話正常不 400 | LiteLLM `deepseek-chat` 真跑 10 次（§3）：壓縮後問「我最喜歡的水果」10/10 答「芒果」、0 次 EngineFailed | 過 |

## 3. 真跑（LiteLLM `http://localhost:4000/v1`，`deepseek-chat`；沒碰 LM Studio／ollama）

腳本在 scratchpad（`t4mem/live.sh`）：daemon＋kernel（cpu 0、1、llm）、`aos-agent init`＋`tools add base`（L2 之後工具都關牢），四輪問答（date、read 一個 40 行的檔、記住芒果、再 read 第 20 行）→ `context --by-round` → `compact --dry-run` → `compact --keep-rounds 1` → 再問兩句 → 改 `info.json` 開自動壓縮（上限 150）→ 等一格 → 再問。

節錄（最後一次）：

```
history 14 則，4028 字，約 1184 token，4 輪（user 4／assistant 7／tool 3）
tools  8 個，5267 字，約 1326 token：read, write, edit, bash, grep, find, ls, date
上一次問模型，端點回報 prompt 3169 token
輪  則        字數   token  工具  開頭
2   5-8        3609   1024     1  用 read 讀 long.txt，告訴我總共幾行、最後一行…  最胖：read 3511 字（第 7 則）
（dry-run，沒寫）記憶 14 則、約 1184 token → 13 則、約 238 token；原文 …/prompts/archive/<sha>.json
dry-run 前後 history sha 一樣
compacted：記憶 14 則、約 1184 token → 13 則、約 238 token
=== 壓縮後再問 → 芒果
compact  <sha>  auto=True reason=auto keep_rounds=1 max_tokens=150 before={"count": 19, "tokens": 283} after={"count": 10, "tokens": 144}
usage：壓縮前最後一問 prompt 3171 token → 壓縮後第一問 1966 token
```

- **真的省了**：記憶從約 1184 token 縮到 238，端點回報的 prompt 從 3171 掉到 1966（剩下的大多是 8 個工具的描述，約 1326 token 粗估）。
- **粗估 vs 真數字**：deepseek 回報的 prompt token 約是粗估合計的 1.15～1.3 倍（包裝與工具 schema），所以 `context` 多印一行真數字。
- **第一次真跑抓到的**：只叫一次 `date` 的輪，說明行比換掉的東西還長，縮了反而 129→199 token。改成「換掉的比說明行短就不換」，說明行也縮短（`[aos 已壓縮 4 則：read×2；原文 … 第 2～5 則]`）。
- **封存會丟資訊**：自動壓縮封存了「讀 long.txt」那輪之後問「long.txt 幾行」，模型答 21（原本 40），沒說不知道。這是封存的本質；要找回原文是二波 T-recall（模型）或人 `history --archive --grep`。寫進 compact.md〈保證外〉。
- 穩定：同一段連跑 10 次，見 §4 S 軸。

## 4. 六軸自評（[axes.md §5](2026-09-24-tool-era/axes.md)；每軸 1～5，不加總）

量測（`scratchpad/t4mem/bench.py`）：4000 則、3.4 MB 的記憶，`context` 0.07 s；`compact` 0.80 s（封存 316 輪、每封一輪重組一次，O(輪數²)）；再縮一次空轉 0.00 s；峰值 RSS 43 MB。cpu 秒只在這支基準量，事件裡的 `ms` 是經過時間。

**事件紀錄（T-events＋usage）**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 不叫模型 |
| 2 穩定 | 10/10 | 真跑 10 次每批都有起訖；至少一次＋去重、寫不進去不擋 tick 有單元測試 |
| 3 資源 | 4 | 每批 2 行、每問 1 行（約 200 bytes）；**檔不輪替**，長跑會一直長 |
| 4 快 | 5 | 一次 `O_APPEND` write |
| 5 人易懂 | 4 | `aos-agent events` 一行一件；欄位是英文鍵（`ev`、`ms`） |
| 6 邊界 | 5 | 只寫自己家的 `log/`；usage 只寫 agent 家 |

最弱兩軸：資源（不輪替）→ 之後加 `events --prune` 或按月切檔；人易懂 → `aos-team score` 彙整時翻成白話。

**`context`**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 不叫模型 |
| 2 穩定 | 5 | 唯讀、不拿鎖；跟 talk 同一個函式 |
| 3 資源 | 5 | 4000 則 0.07 s |
| 4 快 | 5 | 同上 |
| 5 人易懂 | 4 | token 是粗估（比真數字少 15～30%）；已加印端點回報的真數字 |
| 6 邊界 | 4 | 人用、唯讀；模型用的 `context` 工具是二波（要牆映射） |

最弱兩軸：人易懂（粗估不準）、邊界（模型版還沒有）。

**`compact`（手動＋自動＋申請）**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 機械版不叫模型 |
| 2 穩定 | 10/10 | 真跑 10 次都縮成、壓縮後問答正常；KILL 窗口 4 條、不動點、決定性有測試 |
| 3 資源 | 4 | archive 全留（每縮一次多一份舊記憶）；`--prune-archive` 要人跑 |
| 4 快 | 4 | 4000 則 0.8 s；封存是 O(輪數²)，上萬輪會慢 |
| 5 人易懂 | 4 | 輸出一行前後對比＋各輪怎麼處理；說明行寫明原文在哪第幾則；**封存後模型會亂答**要人知道 |
| 6 邊界 | 4 | 只寫自己家（記憶、archive、log）；申請只有 human 能替別人申請；`compact-req/` 在家裡（信任資料），工具碰不到 |

最弱兩軸：人易懂（封存丟資訊、模型不會說不知道）→ 二波 T-recall；資源（archive 不自動清）→ 使用者拍預設保留天數。

**`note` 工具＋`notes ls/show`**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 工具本身不叫模型 |
| 2 穩定 | n/10 | 沒真模型跑；單元 36 條（含 20 個平行 add 全在） |
| 3 資源 | 5 | 單檔、上限 500 筆×4000 字 |
| 4 快 | 5 | flock＋整檔讀寫 |
| 5 人易懂 | 4 | 描述 672 字元（英文）；筆記檔在哪要看 access.json（關牢時在牢裡 `/work/notes`） |
| 6 邊界 | 4 | 關牢時要人先 `access set notes <資料夾> --rw` 才能用（不然回 ConfigInvalid 說怎麼掛）；不關牢時寫在自己家 |

最弱兩軸：人易懂（路徑規則有兩種）、邊界（要團隊模板幫忙掛 `notes`）。

**`history --archive`、`events` 命令列**：唯讀、不拿鎖，L5 S5 R5 F5 H4 B5（沒另外量）。

## 5. 跟共用格式不合、或要別隊接的

1. **事件放哪**：catalog 寫成員家 `log/events.jsonl`，spec/team/layout.md 列了 `team/events/<名>.jsonl`（「也可能放在成員家的 log/」）。我放**成員家 `log/`**：寫的人是持 tick 鎖的那方，它只知道自己的家。`Layout.events()` 那格建議改指 `members/<名>/log/events.jsonl`，或拿掉（隊 1）。
2. **筆記放哪**：layout.md 寫 `team/notes/<名>/`。工具關牢時預設 `/work/notes/notes.json`，所以**團隊模板要多掛一個 `notes` → `team/notes/<名>/`（rw）**；人看的 `aos-agent notes` 從 `access.json` 的 `notes` 掛載找回主機路徑。要隊 1（或收尾隊）在 worker／lead 模板的 `mounts` 加這一格、工具清單加 `{"pack": "notes"}`。
3. **compact 申請**：處理函式登記好了（`KINDS['compact']`），但模板的 `may` 沒有 `compact`，也還沒有模型用來寄這種申請的工具（`team_say` 不帶 kind）。要：模板 `may` 加 `compact`；寄申請的工具由隊 1（task 包）或隊 2 加一支 `compact_me` 之類，或讓 `team_say` 能寄 kind。
4. **申請檔落在成員家 `compact-req/`**：這是新位置（layout.md 的「一份資料一個寫的人」表要加一列：郵差建、tick 搬走）。
5. `Layout.notes()`／`events()` 兩個路徑函式目前沒人用（見 1、2）。

## 6. README／索引要加的列（收尾隊加）

- `proto5/README.md` 指令表：
  - `aos-agent context [--by-round] [--json]`｜送給模型的東西多大（人格、記憶、工具，token 粗估＋上一次端點回報的真數字）；talk 的 `/context` 同一份
  - `aos-agent compact [--keep-rounds N] [--max-tokens X] [--dry-run]`｜機械壓縮記憶，原文存 `prompts/archive/`；`info.json` 的 `compact` 開自動
  - `aos-agent events [--last N] [--usage]`｜事件紀錄（每批起訖、成敗、毫秒）與 token 用量
  - `aos-agent history --archive [SHA] [--grep 字]`｜看壓縮前的原文
  - `aos-agent notes ls｜show KEY`｜看 `note` 工具寫的長期筆記
  - `aos-agent init --template NAME`｜照模板生家（第 1 隊）
- 規範表：spec/agent 那列補「事件紀錄 events.md、記憶壓縮 compact.md」；spec/aos-agent 那列補「cli-memory.md（context／compact／events／history／notes）」。
- `lib/README.md`：模組表加 `aos_agent_events.py`、`aos_agent_context.py`、`aos_agent_compact.py`、`aos_agent_notes.py`；測試表加 `test_agent_memory.py`（49 條）、`test_agent_notes.py`（36 條）；總數 **55 檔 1725 條**（rebase 到 0e8a3c5 後）。
- `tools/README.md`：工具包加 `notes/`（`note`：add／find／get／rm，`wf-table/1`；關牢時要掛 `notes`）。
- `notes/README.md`：加這份報告與 `2026-09-24-tool-era/review-memory-{task,astra}.md`。

## 7. 改到別人的檔（合併時注意）

- `lib/aos_agent_cli.py`：五個子命令＋`init --template`（這波只有我改）。
- `lib/aos_agent.py`：idle 那一步多 4 行（叫 `aos_agent_compact.auto`）。
- `lib/aos_agent_batch.py`：`send` 結尾記 `*_start`、`collect` 記 `calls[].ms/ok`、`settle` 記 `*_end`、think inst 多 `envs.AOS_LLM_BATCH`。
- `lib/aos_agent_inputs.py`：intake 提交前記事件（2 行）。
- `lib/aos_llm_call.py`：`_post`／`_post_http` 多一個可省的 `seen` 參數、`call` 寫 usage。
- `lib/aos_agent_talk.py`：`/context`、`_brief` 改叫 `aos_agent_context`。
- `lib/aos_team_requests.py`：`KINDS` 加一行 `compact`。
- `lib/test/test_agent_fix_storage.py`：一行 `mkdir(exist_ok=True)`（tick 現在會先建 `log/` 寫事件）。

## 8. 要使用者拍的

1. **自動壓縮預設開不開**：現在 `info.json` 沒寫 `compact` 就不自動（不改既有 agent 的行為）。要不要讓 `init`／團隊模板預設寫 `"compact": {"max_tokens": …}`？多少合適（deepseek 的 context 很大，但 token 是錢）？
2. **說明行用 `user` 角色**：放 `assistant` 模型會學著自己寫「[aos 已壓縮…]」；放 `user` 模型可能以為是人說的。現在用 `user`、內容開頭一律 `[aos `。可以接受嗎？
3. **封存會讓模型亂答**（真跑看到 40 行答成 21）：要不要在封存行多加一句「這段內容你已經看不到，問到就說不記得」？這是人格／規則層的事，我沒自己加。
4. **archive 保留多久**：現在全留、人跑 `compact --prune-archive 天數` 才清（而且記憶還指著的不清）。要不要自動清？
5. **「沒做完的任務」**：現在 `done`、`cancelled` 算結束，`failed` 算沒結束（因為 `reassign` 可以把它拉回來），讀不到的單也算沒結束（寧可多留）。這樣對嗎？
6. **事件檔不輪替**：一直長。要不要定一個上限（例如留 30 天）？
