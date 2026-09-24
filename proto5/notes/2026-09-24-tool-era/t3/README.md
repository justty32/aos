← [工具大開發時代](../README.md)｜[notes 索引](../../README.md)

# 第一波第 3 隊：檔案＋workflows 工具（2026-09-24）

做了兩個給模型用的工具包、兩支人用的指令。**全部純機械、不叫模型**，只用 Python 標準庫。

| 東西 | 一句話 | 說明在 |
|---|---|---|
| `tools/files/`：`json_edit`、`md_section` | 按 JSON Pointer 改 JSON 的一格、按標題改 md 的一節 | [files README](../../../tools/files/README.md) |
| `tools/wf/`：`wf_doc`、`wf_init`、`wf_lint`、`wf_residue`、`wf_table` | 把 workflows 手冊導入專案、檢查導得乾不乾淨、讀寫資料表；自帶固定版本快照 | [wf README](../../../tools/wf/README.md) |
| `cli/aos-json` | 人用的 JSON Pointer 改檔，`--check-directives` 解不過不寫 | [tools-files.md](../../../spec/aos-agent/tools-files.md) |
| `cli/aos-directives` | 人格（system prompt）按標題分節：列、看、改一節、加一節、刪、匯出 md 用編輯器改、存版本、還原；另有 `resolve`／`check` 解指示詞 | 同上 |
| [review-task.md](review-task.md)／[review-astra.md](review-astra.md) | astra 唯讀審查 | |

裝：`aos-agent tools add files --target 家`、`aos-agent tools add wf --target 家`（T1 的 worker 模板已掛這兩包）。關牢、不關牢都跑得起來。

## 幾個做法（跟 catalog 不完全一樣的地方）

- **根目錄**：兩包的 `_common.py` 是 base 那份**逐字複製**（裝進 agent 家時找不到 base），測試 `test_common_is_base_copy` 守著一致：L2 改了 base 那份，這條會紅，照訊息再複製一次就好。`_common.py` 沒改任何一行。
- **信任資料**（json_edit、md_section 都擋）：沒關牢時照家裡 `info.json` 的實際設定算（人格、記憶、access、工具檔與程式、`$ref` 一路追、硬連結）；用了 `$env`／`$fmt` 算不出來就整個拒寫。關牢時交給牆（牢裡本來寫不到）。
- **防互蓋**：讀、比 `expect_sha`、改、寫整段持資料夾 flock（三支共用）；同一個請求重送一定 `Conflict`，不會多做。
- **md_section 的清單**：照 catalog 一律 `- [工作流] 狀態 → 下一步`；`SESSION-LOG.md`、`WAIT_USER.md` 預設保護（書記在寫），`config.json` 可改。
- **wf_init 的 staging 放在專案裡**（`.wf-staging-<id>/`），不是 catalog 寫的「複製整個專案再整個換過去」：關牢時專案是掛載點，換不過去。做法：在空 staging 跑 `wf-init.sh` → 寫 `commit.json` → 一個個搬進專案（`AGENTS.md` 最後搬、被蓋的舊檔進 `.wf-backup-<id>/`）；重跑會把做一半的做完或丟掉。`commit.json` 當不可信資料驗；兩個同時跑，後來的回 `Busy`。
- **快照**：`~/repo/workflows` commit `2021d9b`（kernel v0.6）用 `git archive` 取 136 檔、約 0.9 MB（那邊工作樹有未提交改動，沒抄）；`update-snapshot.sh` 重做。
- **aos-directives 兩種意思都做**：任務書說是「人格編輯器」，catalog T-directive 說是「解／驗 `$env`／`$ref`」，我兩個都放在同一支指令（見要拍的第 1 題）。

## 真跑

**files 在 bwrap 牢裡**（`aos-jail --mount ws=… --chdir ws`）：`json_edit set` 成功；`md_section append_item` 成功；格式不對回 `BadItem`；改 `SESSION-LOG.md` 回 `Protected`；讀 `../../info.json`、讀家的絕對路徑都回 `OutsideRoot /work/ws`。

**wf_lint（strict）對 `~/repo/workflows` 副本**：

```
FAIL (exit 1)
TOTAL broken=207 residue=258 oversize=0 biglist=23 querycmd=1
SUMMARY .: broken=207 oversize=0 biglist=23 biglist_links=10 querycmd=1 residue={{=199 模板說明=37 導入判斷=22 inbox_pending=0
BROKEN flavors/dev/COMMON.dev.md -> conventions.md
BROKEN flavors/dev/workflows/analysis.md -> ../WORKFLOWS.md
…（前 50 條，全文存 .wf-lint.log）
```

一共抓到 **241 條問題行**：BROKEN 207、BIGLIST 23、BIGLIST-LINKS 10、QUERYCMD 1。207 條壞連結全在 `flavors/` 的片段裡：模板 repo 本來要用 `--self` 檢查，片段要合進專案後連結才對。所以這是「把模板 repo 當專案檢查」的正常結果，不是 workflows 壞了。

**wf_residue 對同一份副本**：`residue total=258 ({{=199 導入判斷=22 模板說明=37) unreadable=0`，跟 lint 的 residue 對得上。

**空專案導入 heartbeat**（非侵入式 `wf`）：導入 38 個檔；殘留 `total=32 ({{=24 導入判斷=3 模板說明=5)`；非 strict lint `PASS`、`broken=0`。牢裡跑 `wf_init`、`wf_residue`、`wf_lint` 都正常。

**穩定度與量測**：每支同一輸入跑 10 次都是 10/10、結果一樣。這台沒有 `/usr/bin/time`，cpu 秒改用 `wait4` 的 rusage 量。

| 工具 | 中位數 | cpu 秒 | 記憶體 |
|---|---|---|---|
| json_edit、md_section | 20 ms | 0.02 | 20 MB |
| aos-directives ls、aos-json get | 22～24 ms | 0.02 | 18～20 MB |
| wf_doc、wf_residue | 20 ms | 0.02 | |
| wf_table | 35 ms | 0.035 | |
| wf_init | 88 ms | 0.11 | |
| wf_lint（小專案／整份 workflows） | 105／493 ms | 0.14／0.82 | |

**描述字數**（description＋參數說明／整段 JSON）：json_edit 505／992、md_section 429／961、wf_doc 118／432、wf_init 240／633、wf_lint 186／469、wf_residue 106／322、wf_table 127／736。**七支合計 1711 字元**，低於 3000，有測試守著。

## 六軸自評（照 [axes.md](../axes.md)；穩定度都跑滿 10 次）

| 工具 | L | S | R | F | H | B | 最弱兩軸與原因 |
|---|---|---|---|---|---|---|---|
| json_edit | 5 | 5 | 5 | 5 | 4 | 3 | B：路徑由模型挑，只擋在根目錄與信任資料外；H：還沒派新手試玩 |
| md_section | 5 | 5 | 5 | 5 | 4 | 3 | 同上 |
| wf_doc | 5 | 4 | 5 | 5 | 5 | 5 | S：唯讀、沒有崩潰情境可測；其餘滿分 |
| wf_residue | 5 | 4 | 5 | 5 | 5 | 5 | 同上 |
| wf_lint | 5 | 4 | 5 | 4 | 5 | 4 | S：沒有崩潰測試；F：大專案接近 0.5 s；B：會寫 `.wf-lint.log` |
| wf_table | 5 | 4 | 5 | 5 | 4 | 3 | B：會改資料檔，沒有 `expect_sha`；H：op 多 |
| wf_init | 5 | 5 | 5 | 5 | 4 | 3 | B：寫整個專案（有 staging、備份、鎖）；H：要懂 staging 與備份 |
| aos-directives | 5 | 4 | 5 | 5 | 4 | 4 | S：沒有 KILL 測試；H、B：人用，會改人格（有版本可還原） |
| aos-json | 5 | 4 | 5 | 5 | 4 | 4 | S：同上；B：人用，不擋信任資料 |

- **S=5 的依據**：json_edit、md_section 是 10/10、錯誤一律最後一行 JSON、殘檔模擬 KILL 窗口、6 個寫者並行只成功 1 個、重送不多做。wf_init 則是兩個窗口真的 SIGKILL 後重跑都收得回來。
- **B 軸是第一波的上限**：第一波的整體前提是工人的 bash 沒關，所以團隊層級的 B 要等第二波重評。

## 數字

- 測試：1470 → **1551**，新增 81 條：files 36、aos-directives／aos-json 16、wf 29。rebase 到 main（f74cc06，含 T1）後 **1579 條全綠**。
- astra 審查：**必修 8 條，全修**；建議 3 條，做了 S3（跑快照程式前隔離環境），S1、S2 寫進文件。
  1. M1：信任資料會跟著 `$ref` 解；解不出來就拒寫。
  2. M2：寫入整段加資料夾鎖。
  3. M3：`commit.json` 當成不可信資料來驗。
  4. M4：`wf_init` 加專案鎖，第二個執行者回 `Busy`。
  5. M5：清單格式一律檢查。
  6. M6：指令遇到檔案錯誤只印一行。
  7. M7：`revert` 整段在鎖內做。
  8. M8：lint 分成 pass、fail、error 三種結果。

## 給收尾隊（照 plan，這些共用檔我沒改）

- `proto5/README.md` 指令表加兩列：`aos-json`、`aos-directives`。
- `lib/README.md` 加 `aos_json_cli.py`、`aos_directives_edit.py` 兩列，模組數＋2，測試數照實跑。
- `tools/README.md`：「現在只有 base」改成列出 base、files、wf 三包。
- `spec/aos-agent/README.md` 加 [tools-files.md](../../../spec/aos-agent/tools-files.md) 一列。
- 給 T2 驗收員的 Python 介面：`_wf.residue(p)`、`_wf.lint(p, strict)`，回傳裡有 `status`（見 wf README）。

## 沒做的

- `wf_init` 不支援 `--skills`（快照沒帶 skills 本體）。
- `wf_table` 沒有 `expect_sha`。
- 新手試玩沒派，所以 H 軸最高只給 4。
- 模型沒真的用過這些工具：第一波的真模型驗收在收尾隊。
- 程式碼區塊以外的 setext 標題（底線式）不算標題。

## 要使用者拍的

| # | 題目 | 預設 |
|---|---|---|
| 1 | `aos-directives` 要當「人格編輯器」（任務書的意思）還是「解指示詞」（catalog 的意思）？ | 兩個都放同一支，子命令分開 |
| 2 | `md_section` 的清單只收 `- [工作流] 狀態 → 下一步`，一般條列只能用 `replace` | 照 catalog 只收這種 |
| 3 | 沒關牢、`info.json` 又用了 `$env`／`$fmt`：files 工具整個拒寫 | 拒寫（寧可擋）；L2 讓工具一律關牢後就不會碰到 |
| 4 | `wf_init` 被蓋掉的舊檔放在專案裡的 `.wf-backup-<id>/`，會被 wf-lint 掃到 | 留在專案裡，讓人看過再刪 |
| 5 | `wf_residue` 照 IMPORT.md 掃所有 `.md`；wf-lint 會跳過 archive／inbox 這類封存區，兩邊數字可能不同 | 照 IMPORT |
| 6 | 每次 `tools add wf` 都複製一份 0.9 MB 的快照進 agent 家 | 接受 |
