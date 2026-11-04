# IMPORT — 讓 agent 代勞導入（照這份做）

使用者把本 repo 路徑給你、說「照這套模板幫我的專案建立工作流」時照本檔做。**Done when**：目標專案裡 `{{` 為 0、〔模板說明〕為 0、〔導入判斷〕為 0、`tools/wf-lint.sh --strict <專案根>` 結束碼 0。

## 0. 只問這些（一次問完）

1. 專案根路徑。
2. flavor：`dev` / `knowledge` / `teaching` / `research` / `ops` / `heartbeat` / `multi-agent`（可多選；定位見 [README](README.md) 的表）。使用者沒指定就依專案內容建議，不要全裝。
3. **要不要裝 skills**（`--skills a,b`，`all` 全裝，省略＝不裝）：可選的 agent skill 包，與 flavor 無關、不進派發表；清單見 [skills/README.md](skills/README.md)。使用者沒指定就不要裝。
4. 佈局：既有專案預設**非侵入式**（`--non-invasive wf`，頂層只留 `AGENTS.md` / `CLAUDE.md` / `.claude/`，見 [docs/non-invasive-import.md](docs/non-invasive-import.md)）；新專案用標準佈局。
5. **用哪個 agent 工具**：`AGENTS.md` 是中立入口，多數工具直接讀；不讀的就用 `--redirect <該工具的指示檔名>` 產一行轉址（Claude Code 的 `CLAUDE.md` 預設就有；Gemini CLI 用 `GEMINI.md`，Copilot 用 `.github/copilot-instructions.md`）。適配表見 [README](README.md) 的「不只 Claude」。
6. 專案一句話、驗證指令（測試 / build / lint）、時區、分支慣例——這四個是 `{{}}` 最常要的專案事實。

## 1. 跑 wf-init

```bash
bash <本 repo>/tools/wf-init.sh --target <專案根> --flavor <a,b,c> [--non-invasive wf] [--redirect GEMINI.md] [--skills <a,b>]
```

腳本會：複製 kernel（含 `tools/` 的 `wf-lint.sh`、`wf-lint-checks.sh` 與各支 `.py`）→ 合入各包 `workflows/` 與頂層項目（`inbox/`、`.claude/commands/`）→ 把各包片段貼進 `AGENTS.md` / `WORKFLOWS.md` / `INDEX.md` / `workflows/common/README.md` 的 `<!-- wf-insert:… -->` 標記前 → 非侵入式時改寫斷掉的連結 → 有 `--skills` 就把整個技能目錄複製到 `<wfroot>/skills/`，並在目標專案根 `.claude/skills/<name>/SKILL.md` 產轉址檔（frontmatter 抄來源、正文連回真正的 `SKILL.md`）供 Claude Code 自動發現 → 印殘留清單並跑 lint。目標已有 `AGENTS.md` 時腳本拒絕執行（不覆蓋既有導入）。`--redirect` 逗號可多個，把 `CLAUDE.md` 的轉址內容另存成各工具的檔名。

## 2. 逐檔填 `{{}}`

`grep -rn '{{' <專案根> --include='*.md'`。每個佔位符要一個專案事實：能從 repo 查到的（目錄結構、測試指令、語言）自己查，查不到的問使用者。**不要留佔位符、也不要瞎猜填。**

## 3. 逐段處理〔導入判斷〕

`grep -rn '〔導入判斷〕' <專案根>`。每段格式固定「條件 → 動作。同步：檔案清單」，決定後**刪那段並照「同步」改對應檔**。常見判斷：

| 在哪 | 判斷 | 刪掉後要同步 |
|------|------|-------------|
| `WORKFLOWS.md` 派發表佔位行 | wf-init 已自動處理；手動導入才會看到 | — |
| dev `testing.md` 測試分類段、`dev-env.md` 跨機段 | 有沒有特殊環境 | feature-dev 驗證步驟、WAIT_USER 用法 |
| knowledge `writing.md` 繁簡條款 | 是不是繁中專案 | 刪 `writing/zh-tw.md` 與連結 |
| heartbeat `routines.md` 範例分區 | 換成自己的時機 | 無 |
| multi-agent `ROSTER.md` 範例列 | 填實際往來對象 | 無 |
| 各包 README「可選工作流菜單」 | 要哪幾個 | **不要的工作流＝刪檔＋刪派發表該列**（INDEX / README 提到它的列一併刪），wf-lint 抓漏 |

## 4. 刪〔模板說明〕

`grep -rn '〔模板說明〕'`。純解說，讀過刪整段（一段＝連續的 `> ` 行）。

## 5. 驗收

```bash
bash <專案根>/tools/wf-lint.sh --strict <專案根>      # 非侵入式：<專案根>/wf/tools/wf-lint.sh
```

0 BROKEN 且殘留 0 才算完成。最後把「導入哪些包、做了哪些判斷、填了哪些事實」回報使用者一次；commit 由使用者決定。

## 附：kernel-owned vs project-owned（升級用）

kernel 改版時（見 [CHANGELOG.md](CHANGELOG.md)；版本戳在 `AGENTS.md` 尾端 `<!-- wf-kernel vX.Y -->`）：

| 類別 | 檔案 | 升級方式 |
|------|------|---------|
| **kernel-owned**（無佔位、可整檔覆蓋）| `STRUCTURE.md`、`workflows/TEMPLATE.workflow.md`、`workflows/common/data-files.md`、`workflows/common/data-files-fmt.md`、`workflows/common/reply-style.md`、`workflows/tidy/`（整夾）、`.claude/commands/wf-lint.md`、`tools/wf-lint.sh`＋`tools/wf-lint-checks.sh`、`tools/*.py`（含 `tools/check_anchors.py`）、`tools/fmt-vars.json`（專案自加變數放 `tools/fmt-vars.local.json`，project-owned）；flavor 的 `TEMPLATE.*`、`quality-gates.md`、`PROTOCOL.md`、`workflows/inbox/wake-policy.md`、`tools/inbox_*.sh`、`tools/inbox_team.sh`、`tools/test_inbox.sh`、`tools/notify_watch.sh`、`workflows/dispatch/driving-cli-agents.md`、`workflows/dispatch/lessons.md` | 從新版直接覆蓋；**`tools/` 要整包覆蓋**（拆檔後彼此相依，只挑一支會 `FATAL`／ImportError）|
| **project-owned**（填過佔位、貼過片段）| `AGENTS.md`、`INDEX.md`、`WORKFLOWS.md`、`SESSION-LOG.md`、`WAIT_USER.md`、`workflows/common/user.md`、各工作流清單（routines、ROSTER、planning 表、team-model 分級表與逐模型指揮心得表…）| 讀 CHANGELOG 該版那幾行手動套 |
