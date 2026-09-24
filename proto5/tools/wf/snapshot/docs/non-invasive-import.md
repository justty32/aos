# 非侵入式導入：頂層只留入口，其餘收進 `wf/`

[docs](README.md)｜標準導入流程見 [repo README](../README.md)

把模板引進**既有專案**時，kernel 直接攤在專案根目錄會讓頂層冒出一堆 `.md`。非侵入式佈局：頂層只留 agent 的入口與只能放在根的適配層（Claude Code 為例：`CLAUDE.md`、`.claude/`），其餘收進單一子資料夾。

## 目標佈局

```
你的專案/
  AGENTS.md            ← 入口（薄路由器），向下連結已改成 wf/…
  CLAUDE.md            ← 轉址檔（Claude Code 為例；其他工具用 --redirect 產自己的檔名）
  .claude/commands/    ← slash 指令適配層（可選）；Claude Code 只讀專案根的這個目錄，故留根
  .claude/skills/      ← 有裝 --skills 才有；每個技能一個轉址 SKILL.md 供自動發現，故留根
  inbox/               ← 只有合 multi-agent 包才有；它是對外介面（別的 agent 往這投遞），留根
  wf/                  ← 其餘全部（名稱自取：wf、.workflow、ops…）
    WORKFLOWS.md  INDEX.md  STRUCTURE.md  SESSION-LOG.md  WAIT_USER.md
    workflows/    tools/（wf-lint.sh、wf-lint-checks.sh、tabledb.py、tabledb_links.py、find_big_lists.py、fix_moved_links.py）
    skills/       ← 有裝 --skills 才有；技能本體整包在這裡，轉址檔在根 .claude/skills/
  …（專案原本的檔案不動）
```

## 怎麼做

```bash
tools/wf-init.sh --target <專案根> --flavor <a,b> --non-invasive wf [--skills <a,b>]
```

腳本做三件事，手動導入就照著做：

1. **分家**：`AGENTS.md`、`CLAUDE.md`、`.claude/` 與各 flavor 包的頂層項目（`inbox/`）放專案根；其餘進 `wf/`。有 `--skills` 時技能本體進 `wf/skills/`，轉址檔（每個技能一份 `SKILL.md`）另外放根層 `.claude/skills/<name>/`，因為 Claude Code 只認專案根那層。
2. **改寫斷掉的連結**：搬家後解析不到的相對連結，若在另一邊找得到就改寫（根檔往 `wf/` 指、`wf/` 內指回根的 `.claude/`、`inbox/`）。kernel 與 flavor 內部**本來就不向上連 `AGENTS.md`**，`wf/` 內部彼此的連結因此全不受影響；實際會被改寫的只有三類：`AGENTS.md` / `CLAUDE.md` 的向下連結、`.claude/commands/*.md` 指向 `workflows/` 的連結、`workflows/inbox/` 指向根 `inbox/` 的連結。
3. **改 AGENTS.md 開場那行的路徑**（`grep -c '^- \[' wf/SESSION-LOG.md wf/WAIT_USER.md`——它是 code span 不是連結）。

做完跑 `bash wf/tools/wf-lint.sh <專案根>`，0 BROKEN 才算完成。

## 是否 git ignore

不想把工作流納入專案版控就整組 ignore，想納入就不 ignore。`inbox/` 信件量大時可只 ignore 頂層、commit `done/`（見 multi-agent 包 README）。

```gitignore
/AGENTS.md
/CLAUDE.md
/.claude/
/wf/
```

## 升級

`wf/` 內 kernel-owned 的檔（`STRUCTURE.md`、`workflows/TEMPLATE.workflow.md`、`workflows/common/data-files.md`、`workflows/tidy/`、`tools/wf-lint.sh`、`tools/*.py`）可整檔覆蓋，其餘讀 [CHANGELOG](../CHANGELOG.md) 手動套；分類見 [IMPORT.md](../IMPORT.md)。
