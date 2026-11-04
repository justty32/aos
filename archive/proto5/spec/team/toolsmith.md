← [team](README.md)｜目錄 [catalog E 節 T-toolsmith](../../notes/2026-09-24-tool-era/catalog.md#t-toolsmith)｜報告 [w3a](../../notes/2026-09-24-tool-era/w3a/README.md)｜測工具 [tools-dev.md](../aos-agent/tools-dev.md)

# 模型造工具：`tool_draft` → 牢裡測 → 人批 → `aos-team tool approve`

第三波 W3-1，2026-09-24 第 1 版。程式：[`lib/aos_team_toolsmith.py`](../../lib/aos_team_toolsmith.py)、工具 [`tools/task/tool_draft`](../../tools/task/tool_draft)。

成員（內建只有工人）遇到「同一種機械的事一直做、又沒現成工具」，可以寫一支 Python 小工具草稿。**測是郵差自動做，裝要人**。

```text
工人 tool_draft {"name","description","parameters","code","cases",…}
   ├─ 寫 /work/outbox/tools-staging/<名>/（draft.py、tool.json：給自己看、改）
   └─ 寄 kind: tool_draft 申請（整份草稿在申請裡），這輪結束
郵差 on_tool_draft：驗格式 → 用申請內容生包 team/tool-drafts/d-0001/<名>/（記每檔 sha256）
       → aos-agent tools test <包> --json（關牢；每次執行逾時 5 秒；整個再包 90 秒）
   ├─ 沒過：退一封 FAILED 給工人，附沒過的那幾條；工人改好再交一次（同名）
   └─ 過了：開一題「[工具] …」；同一人同名的舊版題目收掉（只裝最新一版）
人 aos-team tool ls／wait ls 看到；先看 team/tool-drafts/d-0001/<名>/draft.py
   ├─ 批准：aos-team tool approve q-NNNN
   │     最新一版？sha256 對得上？→ aos-agent tools add <包> --target <工人的家> → 回覆工人
   └─ 不要：aos-team answer q-NNNN 不要
```

## 草稿（`kind: tool_draft`）

| 鍵 | 必填 | 意思 |
|---|---|---|
| `name` | 是 | 工具名＝包名，`[a-z][a-z0-9_]{0,39}` |
| `description` | 是 | 給模型看的一句話（英文、越短越好），≤ 600 字 |
| `parameters` | 是 | `{"type": "object", "properties": {…}, "required": […]}`；參數 ≤ 8 個，每個 `type` 是 string／integer／number／boolean／array／object，另可 `description`、`enum`、`items`、`minimum`、`maximum` |
| `code` | 是 | Python 原始碼，≤ 20000 字，要有頂層 `def main(args, root)`（語法錯先擋） |
| `cases` | 是 | 1～5 條例子，**至少一條 `expect: "ok"`**：`{"args", "expect": "ok" 或錯誤代號, "contains"?, "files"?: {相對路徑: 內容}}` |
| `lang` | 否 | 只收 `"py"` |

為什麼一定要例子：`tools test` 自己生的正例只看「照契約回話」，程式每次都丟例外也算過（回 `PythonError` 是合法回話），沒有真的例子測不出它會不會做事。
誰能寄：模板 `may` 有 `tool_draft` 的（內建只有 `worker`）。

## 生出來的包（固定外殼）

| 檔 | 內容 |
|---|---|
| `<名>.json` | 一支工具：`description`、`parameters` 照抄；`_meta.argv` `tools/<名>/<名>`；`_timeout_ms` 5000；沒寫 `_jail`＝關牢 |
| `<名>` | 固定外殼：照 `parameters` 驗參數（多的、缺必填、型別、`enum` 不對＝`BadArguments`）→ 叫 `draft.main(args, root)` → 字串原樣回、其他 `json.dumps`（不行＝`ResultNotJSON`）；任何例外＝`PythonError`，不噴 Traceback |
| `draft.py` | 模型寫的 `code` 原樣 |
| `_common.py` | base 包逐字副本（`fail`、`resolve` 可以用） |
| `config.json`、`cases.json` | `{"root": "workspace"}`；`cases` 加上 `tool` |

`root`＝工作根目錄，牢裡是 `/work/ws`（專案）。

## 保證與保證外

- **不在主機上直接跑模型寫的程式**：郵差先確認 `aos-jail` 跑得起來，不行＝`NoJail` 退件；`tools test` 的報告說沒關牢也不算。
- **測的就是裝的**：包是郵差用申請內容生的，放在成員碰不到的 `team/tool-drafts/`；staging 只是給模型自己看，改了不影響。`approve` 前核 sha256，對不上＝`Tampered` 不裝。
- **只裝最新一版**：同一人同名的新草稿一到，舊題目收掉；拿舊版去 `approve`＝`Superseded`。
- **不蓋別人的工具**：同名的包只有「上次也是 `tool_draft` 裝的」（包裡有 `.toolsmith.json`）才 `--force` 重裝；撞到 base、task 這種內建的名字或工具名，`tools add` 拒絕，什麼都不動。
- 裝好的工具跟其他工具一樣**在成員自己的牢裡跑**，碰得到的就是成員碰得到的（專案、自己的 outbox…）。
- **保證外**：程式邏輯對不對只有例子與人看；郵差測的時候會同步卡住最多約 90 秒（這段時間別的信晚一輪）；專案裡的檔（例子的 `files` 寫在拋棄式 workspace，不碰真的專案）。

## 紀錄 `team/tool-drafts/d-NNNN/draft.json`（只有郵差寫）

`{"_metainfo": {"_type": "aos_team_tool_draft", "_version": 1}, "id", "request", "from", "name", "description", "at", "sha256": {檔: 值}, "test": {"passed", "total", "failed", "note"}, "q", "effects"}`。
冪等：同一份申請（看 `request`）再來＝回同一份動作，不重測。

## 人的指令

- `aos-team tool ls [--json]`：一份草稿一行（`d-0002  q-0004  worker-1 的 count_md_words  測試 6/6  等你批`；已裝、測試沒過、你不要、舊版都標出來）。
- `aos-team tool approve q-NNNN|d-NNNN`：上圖那串；回覆方式同 [spawn.md](spawn.md)（題目開著寄 answer、已答過寄信、重跑不重寄）。
- 拿掉：`aos-agent tools rm <名> --target <家>`（既有）。
