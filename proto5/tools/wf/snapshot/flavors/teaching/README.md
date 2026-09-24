# 教學 flavor 包 — 把知識做成給別人學的教材

← [repo README](../../README.md)（導航中樞）

把「我懂的東西」變成「別人學得會的東西」。搭配 [`template/`](../../template/) 這個**共用 kernel** 一起用：kernel 提供分層樹骨架，本包提供兩條產線——把陌生主題**講成零基礎讀得懂的文字**（plain-explain），以及把知識**做成可操作的互動網頁課程**（study-site）。

兩條線共用同一套方法：名詞與概念分開教、術語繁中英文對照、每個結論沿因果鏈推、每個說法給得出可觀察證據、先教會才准考。差別只在產物是一份文字還是一個網站。

## 與 knowledge 包的分工

| | knowledge 包的 write / learn | 本包 |
|---|---|---|
| 產物給誰看 | **給自己看**的筆記、摘要、成品文章 | **給別人學**的教材 |
| 成功標準 | 我讀得懂、找得回來 | **零基礎的他**讀得懂、做得出來 |
| 硬性要求 | 出處齊全、文風一致 | 不假設未聲明的先備知識；名詞／概念分開；有可觀察證據 |
| 典型入口 | `write` / `learn` / `digest` | `plain-explain` / `study-site` |

材料還沒讀懂就要教別人 → 先走 knowledge 包的 digest / learn，再回來。兩包都導入時，產出文字仍過一遍 `common/writing.md` 的文風自檢；本包不重述文風規則。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.teaching.md](WORKFLOWS.teaching.md) | 派發表片段（貼進 kernel 的 `WORKFLOWS.md`）|
| [workflows/plain-explain.md](workflows/plain-explain.md) | **單檔型**：把陌生技術主題講成零基礎讀得懂的文字 |
| [workflows/study-site/](workflows/study-site/README.md) | **資料夾型**：把知識做成可操作的互動網頁課程 |
| [workflows/study-site/foundations-first.md](workflows/study-site/foundations-first.md) | 零基礎課程剖面：多頁結構、先教後操作、自由實驗、可延續性 |
| [workflows/study-site/quality-gates.md](workflows/study-site/quality-gates.md) | 品質關卡 checklist ＋可複製的驗收指令 |
| [workflows/study-site/build-with-agents.md](workflows/study-site/build-with-agents.md) | 分層派工產線：四層 token 階梯、單一作者、獨立驗收 |
| [workflows/study-site/enrich-existing.md](workflows/study-site/enrich-existing.md) | 只加厚既有課的文字，不動互動與版面 |
| [workflows/study-site/publish.md](workflows/study-site/publish.md) | 發布契約：只發成品、單一入口、驗 HTTP 200 |
| [workflows/study-site/TEMPLATE.project-brief.md](workflows/study-site/TEMPLATE.project-brief.md) | `PROJECT-BRIEF.md` 骨架 |
| [workflows/study-site/TEMPLATE.build-spec.md](workflows/study-site/TEMPLATE.build-spec.md) | `BUILD-SPEC.md` 骨架 |

## 怎麼合進 kernel

```sh
bash tools/wf-init.sh --target <專案> --flavor teaching
```

通用步驟見 [IMPORT.md](../../IMPORT.md)（多個 flavor 就多帶幾個 `--flavor`，派發表依序插入）。本包特有：只有一個片段檔 [WORKFLOWS.teaching.md](WORKFLOWS.teaching.md)；併進 `workflows/` 的是 `plain-explain.md` 與 `study-site/` 整個資料夾；佔位符以 `{{讀者基線}}` 為主。

## 移除某工作流要動的地方

| 移除 | 刪什麼 | 同步改什麼 |
|------|--------|-----------|
| plain-explain | `workflows/plain-explain.md` | 專案 `WORKFLOWS.md` 派發表該列；`workflows/study-site/foundations-first.md` 的「語言與名詞契約」連結改成內嵌一段（契約原文在 plain-explain）|
| foundations-first 剖面 | `workflows/study-site/foundations-first.md` | `study-site/README.md` 流程說明與內容表該列；`study-site/quality-gates.md` 的「零基礎加驗」段；`plain-explain.md` 不受影響 |
| enrich-existing | `workflows/study-site/enrich-existing.md` | 派發表該列；`study-site/README.md` 交接段 |
| publish | `workflows/study-site/publish.md` | 派發表該列；`study-site/README.md` 流程第 6 步與內容表 |
| study-site（整條）| `workflows/study-site/` 整個資料夾 | 派發表 study-site 相關各列；`workflows/plain-explain.md` 交接段那句 |

改完跑 `tools/wf-lint.sh`（Claude Code 可用 `/wf-lint`）確認沒有指向已刪檔的連結。
