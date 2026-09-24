# skills — agent 工具的獨立能力包

[repo README](../README.md)

## skills 是什麼

一個 agent skill＝一個資料夾，裡面一份 `SKILL.md`（YAML frontmatter 的 `name`＋`description`，後面接指示），可選附 `references/`、`scripts/`、`assets/`、`agents/openai.yaml`。Agent 工具（Claude Code、Codex…）靠 `description` 自動判斷何時該挑用，不用使用者手動點名。

## 跟 `template/` 與 `flavors/` 的關係

三者並列在 repo 頂層，但屬性不同：`template/`（kernel）與 `flavors/` 是**分層工作流文檔**，進 `WORKFLOWS.md` 派發表，套用時整包合併進專案。`skills/` 底下每個能力包**不進派發表**——導入時可選裝，不裝也完全不影響既有工作流；是 agent 工具自己按 description 挑用的獨立單元。

## 逐 skill 一覽

| skill | 一句話 | 來源與授權 |
|-------|--------|-----------|
| [markdown-html-slides](markdown-html-slides/SKILL.md) | 把一或多份 Markdown 變成可直接播放的自包含 HTML 簡報 | 本 repo 自有（CC0）|
| [html-slides-shared-assets](html-slides-shared-assets/SKILL.md) | 一批同源 deck 抽出共用 CSS/JS，整批瘦身 | 本 repo 自有（CC0）|
| [html](html/SKILL.md) | HTML artifact 的總入口，依產物型態路由到下面幾支 | effective-html（MIT）|
| [design-artifact](design-artifact/SKILL.md) | 動手前先定創意方向（配色、字體、版式、主題） | effective-html（MIT）|
| [html-wireframe](html-wireframe/SKILL.md) | 低保真線框，先驗資訊架構與任務流程 | effective-html（MIT）|
| [html-prototype](html-prototype/SKILL.md) | 精緻的高保真 mockup／可互動原型 | effective-html（MIT）|
| [html-plan](html-plan/SKILL.md) | 計畫／提案的可讀 HTML 呈現，保留原始素材可查核 | effective-html（MIT）|
| [html-diagram](html-diagram/SKILL.md) | 關係、流程、拓樸、狀態、階層的圖解 | effective-html（MIT）|

MIT 那六列由 [LICENSES/effective-html.MIT](LICENSES/effective-html.MIT) 涵蓋；本 repo 自身是 CC0（見 [../LICENSE](../LICENSE)），所以 `skills/` 讓這個 repo 變成**混合授權**——沿用時請保留 `LICENSES/` 與各檔原文。

## 導入方式

| 工具 | 怎麼裝 |
|------|--------|
| Claude Code（本 repo 工具鏈）| `tools/wf-init.sh --target <專案根> --skills html,markdown-html-slides`（`all`＝全裝）。複製到 `<專案>/skills/`（非侵入式則 `<專案>/wf/skills/`），並在 `<專案>/.claude/skills/<name>/SKILL.md` 產一份轉址檔，讓 Claude Code 自動發現 |
| Claude Code（手動）| 直接把整個 skill 資料夾複製到 `~/.claude/skills/` 或 `<專案>/.claude/skills/` |
| Codex／其他支援 skills 的工具 | `npx skills add <本 repo 的 git URL>` 指向本 repo，或手動複製目錄 |

## external（submodule）

`skills/external/<name>/` 是 **git submodule**：上游原樣不改、授權歸上游、**不受本 repo 的 8 KB 契約**（`wf-lint --self` 照 `.gitmodules` 跳過這些路徑）、**`wf-init.sh --skills`（含 `all`）不複製它們**。

要用就 `git submodule update --init skills/external/<name>`，再照上游自己的安裝說明裝（多半要 Node／npm，會下載依賴）。不想要就別 init，工作樹留空不影響任何檢查。

不 vendor 的理由：授權跟本 repo 的 CC0 不同、體積大、有執行期相依、有連外行為。

| repo | 一句話 | 授權 | 相依 | 警語 |
|------|--------|------|------|------|
| [dashi-ppt-skill](https://github.com/chuspeeism/dashi-ppt-skill) | 需求整理成 JSON 計畫，12 套預置主題產出離線 HTML 簡報，可再匯出 PPTX／PDF | AGPL-3.0（本 repo CC0）| Node 20+、npm、playwright-core／Chromium；PPTX 匯出要起本機 HTTP 服務 | 工作樹約 60 MB／400+ 檔；`project/assets/unicorn/` 素材帶 Unicorn Studio 商業授權、禁止再散布；每次任務結束前會查 npm registry／raw.githubusercontent.com 版本並要求把結果貼進回覆——跟「外部查詢預設 0」相反 |
| [archify](https://github.com/tt-a1i/archify) | codebase／系統描述編成可互動架構圖：agent 產 typed JSON IR，決定性編譯成自包含 HTML／SVG，另出 PNG／WebM／分享卡 | MIT（Copyright (c) 2026 tt-a1i (Archify)）| Node.js 渲染／驗證系統，要 npm 裝依賴 | repo 很大（docs、benchmarks、examples、`archify.zip`），只裝 skill 本身不夠、要連它的 Node 工具鏈一起跑 |
| [Kami](https://github.com/tw93/Kami) | 文件排版產品——把內容編排成排版精緻的文件成品（agent skill 形態）| MIT | 見上游安裝說明（Node 工具鏈）| repo 約 147 MB；`SKILL.md` 本身約 44 KB，遠超本 repo 的 8 KB 契約（所以只能當 submodule，不能 vendor）；且它每天會連外查版本 |

## 8 KB 約束

`tools/wf-lint.sh --self` 掃全 repo 時 `skills/` 不豁免（`skills/external/` 除外，見上）——每個 skill 都要輕薄，單檔超過 8192 bytes 就把細節拆進 `references/<主題>.md`，並在拆出點留一行相對連結指回去。`--self` 同時對 `skills/` 跑連結檢查，所以 skill 內連結一律寫**相對路徑**；六個 effective-html 目錄彼此平放在 `skills/` 底下，同層互指要用 `../` 開頭（例如 `html/SKILL.md` 連到 `../design-artifact/SKILL.md`）。

## 一句註記

effective-html 的 `html`／`design-artifact` 會叫 agent 去讀專案的 `AGENTS.md`／`CLAUDE.md` 找既有設計語言；本 repo 刻意讓 `AGENTS.md` 保持極薄，那裡通常沒有設計語言可讀——設計偏好請放 `workflows/common/user.md`。
