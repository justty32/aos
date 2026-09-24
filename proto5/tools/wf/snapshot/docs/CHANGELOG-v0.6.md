# CHANGELOG — v0.6 完整條列與升級判準

[docs](README.md)｜[CHANGELOG](../CHANGELOG.md)

由 [CHANGELOG](../CHANGELOG.md) 拆出（母檔只留每版摘要與去向）。

## skills 進契約

新增頂層 `skills/`，與 `template/`（kernel）、`flavors/`（領域包）平行，是第三種佈局單位：**agent skill 包**。一個 skill＝一個資料夾，內含 `SKILL.md`（YAML frontmatter `name`＋`description`，agent 工具靠 `description` 自動挑技能）與可選的 `references/`／`scripts/`／`assets/`／`agents/openai.yaml`。

skills 與 flavor **無關**：不寫進 `WORKFLOWS.md` 派發表，是獨立的能力包，導入時可裝可不裝、跟選哪個 flavor 無關。8 KB 上限對 `skills/` 一體適用、沒有豁免——技能本體要薄，細節放 `references/`。

清單、逐檔角色、授權見 [skills/README.md](../skills/README.md)（本檔不重複列）。

## vendor effective-html

6 個技能 vendor 自 [effective-html](https://github.com/plannotator/effective-html)（MIT）：`html`（總入口／路由）、`design-artifact`、`html-wireframe`、`html-prototype`、`html-plan`、`html-diagram`。授權全文在 `skills/LICENSES/effective-html.MIT`。

**本 repo 本體是 CC0，`skills/` 讓 repo 變成混合授權**——這 6 個技能連同它們的授權條款一起適用，導入到別的專案時授權跟著走，不是本 repo 自己的 CC0。

另外自有兩個（CC0）：`markdown-html-slides`（Markdown → 自包含 HTML 簡報）、`html-slides-shared-assets`（把一批 deck 抽共用資產瘦身）。

**對 vendor 內容的一個修改**：`skills/html/SKILL.md` 的路由段改成把「簡報／slide deck」交給 `markdown-html-slides`，不再讓 `html` 自己生。原因：`html` 直接生的 deck 不帶 `deck-theme`／`slides-core`／`slides-runtime` 這幾個 element ID，`html-slides-shared-assets` 認的就是這幾個 marker——認不到會**silent failure**（抽不出共用資產、也不報錯），不是明顯的壞掉，容易被忽略。

## external skills（submodule）

不 vendor 的產品向外部技能改掛 git submodule，落在 `skills/external/<name>/`。目前兩個：[`dashi-ppt-skill`](https://github.com/chuspeeism/dashi-ppt-skill)（AGPL-3.0，離線 HTML／PPTX 簡報，Node 20+／Chromium，工作樹約 60 MB，每次任務結束前會連外查版本）、[`archify`](https://github.com/tt-a1i/archify)（MIT，畫架構圖，Node 工具鏈）。

- 授權維持上游，不併進本 repo 的 CC0／MIT 清單。
- **豁免 8 KB 契約**：原樣 upstream 代碼，不受本 repo 大小上限管。
- `wf-init.sh --skills`（含 `all`）**不複製** `skills/external/`——那是 submodule 指標，不是本 repo 要導入的內容。
- 要用的人自己 `git submodule update --init skills/external/<name>`，再照該上游自己的安裝步驟走；不初始化不花任何成本（空目錄）。
- 逐支一行說明、授權、依賴、警語在 [skills/README.md](../skills/README.md) 的「external（submodule）」節。

## wf-init --skills 與適配層

`tools/wf-init.sh` 新增 `--skills a,b|all`：

```
tools/wf-init.sh --target <專案根> --flavor dev --skills html,markdown-html-slides [--non-invasive wf]
```

- 逗號多選；`all`＝`skills/` 底下所有含 `SKILL.md` 的資料夾（不含 `skills/external/`，見下節）。
- 裝一個技能會連它路由到的技能一起裝（transitive closure）：例如要 `html`，`html/SKILL.md` 連到其他五個 effective-html 技能，一併裝進來，不用手動列全。
- 落點：標準佈局 `<專案>/skills/<name>/`；非侵入式 `<專案>/wf/skills/<name>/`。連同 `skills/LICENSES/` 一起複製，`skills/README.md` 不複製（那是本 repo 自己的索引，不是要導進專案的內容）。
- 適配層：在 `<專案>/.claude/skills/<name>/SKILL.md` 產一個**轉址檔**——frontmatter 的 `name`／`description` 照抄來源，正文只有一行相對連結指向真正的 `SKILL.md`。跟既有的 `CLAUDE.md` 轉址、`.claude/commands/` 適配層同一路數，讓 Claude Code 能在專案根自動發現。邏輯拆在同目錄的 `tools/wf-init-skills.sh`（`wf-init.sh` 已頂到 8 KB，`source` 載入，缺檔 `FATAL` 並 `exit 2`，跟 `wf-init-relink.sh` 的拆法一樣）。
- 非 Claude Code 的工具：Codex 可用 `npx skills add` 指向本 repo，或手動複製目錄到自己的 skill 目錄；細節見 [skills/README.md](../skills/README.md)。

## wf-lint

`wf-lint.sh --self` 現在也檢查 `skills/` 底下的連結與 `#錨點`（跟 `template/`／`flavors/` 用同一套檢查）。BIGLIST（超標表／清單）與 `$fmt`／資料檔連結檢查**跳過** `skills/`——skill 的 `references/` 是給 agent 讀的散文參考檔，不是 `wf-table/1` 資料檔，套那套規則沒意義。全 repo 的 8 KB 掃描也會排除 `.gitmodules` 宣告的路徑（即 `skills/external/`），跟 v0.5.1 對 `tools/` 排除 submodule 的做法一致。

## reply-style.md

kernel 新增 `template/workflows/common/reply-style.md`：對話回覆風格，7 條規則（先講結論、一步一動作、結尾給下一步、不岔題、報錯平述、清單上限五條、不開場白不總結），另有「何時打破規則」（使用者要求解釋、動作危險、debug 卡住、歧義代價高、規則會讓答案失去實質內容）與「送出前自檢」兩段。

跟著改的檔：`workflows/common/README.md` 導覽表加一列；`workflows/common/user.md` 的「回覆風格」欄改成指向它（原本沒有專門的通用回覆風格檔，欄位是空的）；兩個 `examples/`（dev、knowledge）合併後同步跟上。

kernel-owned，無佔位，可整檔覆蓋。

## 精簡工作流

語意沒動，只砍「同一段話寫了 N 遍」，依 `STRUCTURE.md` 判定；無改名搬移，11 檔淨減 1631 bytes。kernel：`tidy/README.md` 四條原則改一句＋連 STRUCTURE（−561）、`common/gotchas.md` 補「何時用／Done when」（+330）。flavor：七個 README 的通用導入四步改連 `IMPORT.md`（各包特有規則原地保留，合計 −1615）、heartbeat `tick.md` 的 `Done when` 改可觀察、multi-agent README 補登記 team-model、`team-model.md` 醒鐘規則改連 `wake-policy.md`。**既有專案只需跟 kernel 那兩檔**。已裁示待做：heartbeat README 的 `TZ` 踩坑段下沉到 `workflows/`；`team-model` 升正規 `team-model/README.md`；flavor README 的移除表不抽資料檔。

## 既有專案要不要跟

| 檔案 | 類別 | 怎麼跟 |
|------|------|--------|
| `workflows/common/reply-style.md` | kernel-owned，可整檔覆蓋 | 複製到 `workflows/common/`；`common/README.md` 加一列、`user.md` 回覆風格欄改指向它 |
| `skills/`（整包） | 不是 kernel-owned 覆蓋對象，是**新增的可選項** | 想裝就用 `--skills a,b` 重跑 wf-init，或手動複製到 `<專案>/skills/`＋`.claude/skills/` 轉址；沒指定就不動 |
| `skills/external/`（submodule） | 新增的可選項，不隨 `--skills` 走 | 想用就自己在目標專案 `git submodule add` 該上游，或整份 clone；不需要就不用管，不初始化不花成本 |
| `tools/wf-init.sh`＋新增 `tools/wf-init-skills.sh` | kernel-owned，整包覆蓋 | 跟 v0.5.1 起的規則一樣：`tools/` 拆檔後彼此相依，只能整包覆蓋，不可只挑一支 |
| `tools/wf-lint.sh`＋`wf-lint-checks.sh` | kernel-owned，整包覆蓋 | 覆蓋後對 `skills/` 的連結／錨點檢查自動生效，不用另外設定 |
| `AGENTS.md` 版本戳 | project-owned，手動套 | 改成 `v0.6`；否則下次還是分不出自己是哪一版 |

沒有 `skills/` 的專案（沒裝過、也不打算裝）只要跟 `reply-style.md` 與版本戳，`tools/` 覆蓋是保養性質、不跟也不影響既有行為。
