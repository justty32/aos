# 任務書：審查 wf／proto5 notes 的 tidy（唯讀）

你是審查員，只讀不改、不 commit、不開任何服務；不碰 LM Studio／lms／ollama（這條線不需要模型）。工作目錄是 repo 根。

## 背景

這一輪只整理文件，沒動程式。改動在 68308fe 之後的 commit（`git diff --stat 68308fe HEAD`），整理報告在 `proto5/notes/2026-09-24-tidy/README.md`。
`proto5/spec/` 另一隊在拆檔，**指向 proto5/spec 的連結刻意不修**，清單在 `proto5/notes/2026-09-24-tidy/spec-links.tsv`。

## 要你查的

1. **連結全綠？** 跑 `bash wf/tools/wf-lint.sh wf proto5 .claude/commands`，把 `BROKEN` 裡不含 `spec/` 的列出來（應該是 0）。再自己抽查：`wf/workflows/ideas/archive/` 被改的連結（`git diff 68308fe -- wf/workflows/ideas/archive`）是不是指到**原本想指的那份**（不只是「檔存在」，而是同名檔沒有指錯層）；`proto5/notes` 裡「`[文字](路徑:行號)` → `[文字:行號](路徑)`」的改法有沒有弄壞文字（例如行號重複、括號錯位、表格欄位被破壞）。
2. **索引有沒有漏檔？** `proto5/notes/README.md` 對 `proto5/notes/` 頂層每個檔與子資料夾；`proto5/notes/2026-09-23-rearch/README.md` 的表對該資料夾每個檔（`lmstudio/` 子資料夾算一列）；`wf/session_logs/README.md` 對 `wf/session_logs/2026-0*.md` 的每個 `## ` 節；`wf/INDEX.md` 的 Repo 佈局表對 repo 頂層資料夾（`ls -d */`）。
3. **SESSION-LOG 的 open 有沒有丟？** 拿 `git show 68308fe:wf/SESSION-LOG.md` 的 09-24 那條對照現在的 `wf/SESSION-LOG.md`：①～⑦ 每一項（fix-r4 已合可以拿掉）、cpu 動態增減 (a)～(f)、LiteLLM／不碰 GPU、每 commit 推，是否都還找得到（SESSION-LOG 一行摘要＋`wf/session_logs/2026-09.md#2026-09-24` 全文）。搬過去的全文是否逐字（只許連結多一層 `../`）。SESSION-LOG 要 ≤ 3000 bytes。
4. **WAIT_USER**：A 段改動（編號說明、A.14(e)、A.9 移 C、A.13 補連結、C 段刪的那段）有沒有丟掉仍 open 的內容或改掉原意。
5. **proto5/README.md** 還有沒有跟 `proto5/cli/* -h` 或現況對不上的敘述（只讀、`-h` 可以跑）。

## 回報

照嚴重度列（真問題／小問題／建議），每條附 `檔案:行號` 與一句理由。沒有就說沒有。中文、精簡。
